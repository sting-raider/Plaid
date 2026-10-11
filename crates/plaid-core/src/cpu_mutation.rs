//! Source-bound replay for finite CPU executable-mutation histories.
//!
//! This module deliberately separates semantic byte effects from observer callback
//! topology. The initial verified cause surface is COP1 `SWC1`/`SDC1`; capture
//! completeness, ultimate FPR ancestry, later cache writeback, executable lifetime,
//! and hardware transaction atomicity remain independent proof obligations.

use crate::{
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-cpu-mutation-history-v0";
const RDRAM_SIZE: u32 = 8 * 1024 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CpuEndian {
    Big,
    Little,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CachePolicy {
    Cached,
    Uncached,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MutationLocation {
    CacheResident,
    Backing,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Cop1StoreKind {
    Swc1,
    Sdc1,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FprLane {
    Low32,
    High32,
    Full64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FprSelection {
    pub register: u8,
    pub lane: FprLane,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuMutationWitness {
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub store: Cop1StoreKind,
    pub endian: CpuEndian,
    pub fr: bool,
    pub ft: u8,
    pub source: FprSelection,
    pub destination: PhysicalAddr,
    pub location: MutationLocation,
    pub bytes: Vec<u8>,
    pub effect_ordinals: Vec<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuMutationReport {
    pub format: String,
    pub source_sha256: String,
    pub instruction_contexts: usize,
    pub successful_mutations: usize,
    pub faulted_contexts: usize,
    pub witnesses: Vec<CpuMutationWitness>,
    pub mutation_coverage_certified: bool,
    pub fpr_ancestry_certified: bool,
    pub executable_lifetime_certified: bool,
    pub hardware_atomicity_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    begins: Vec<Begin>,
    effects: Vec<Effect>,
    ends: Vec<End>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Begin {
    ordinal: u64,
    context: u64,
    pc: GuestVirtualAddr,
    word: u32,
    endian: CpuEndian,
    fr: bool,
    fpr: [u64; 32],
    destination: Option<PhysicalAddr>,
    cache: Option<CachePolicy>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Effect {
    ordinal: u64,
    context: u64,
    location: MutationLocation,
    address: PhysicalAddr,
    bytes: Vec<u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Outcome {
    Success,
    Fault,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct End {
    ordinal: u64,
    context: u64,
    outcome: Outcome,
}

struct Active<'a> {
    begin: &'a Begin,
    effects: Vec<&'a Effect>,
}

enum Event<'a> {
    Begin(&'a Begin),
    Effect(&'a Effect),
    End(&'a End),
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn decode_cop1_store(word: u32) -> Result<(Cop1StoreKind, usize), String> {
    let store = match word >> 26 {
        0x39 => Cop1StoreKind::Swc1,
        0x3d => Cop1StoreKind::Sdc1,
        _ => return Err("unsupported CPU mutation cause".into()),
    };
    Ok((store, ((word >> 16) & 31) as usize))
}

fn payload_and_source(begin: &Begin) -> Result<(Cop1StoreKind, u8, FprSelection, Vec<u8>), String> {
    let (store, ft) = decode_cop1_store(begin.word)?;
    let (selection, bytes) = match store {
        Cop1StoreKind::Swc1 => {
            let (register, lane, value) = if begin.fr {
                (ft, FprLane::Low32, begin.fpr[ft] as u32)
            } else {
                let register = ft & !1;
                if ft & 1 == 0 {
                    (register, FprLane::Low32, begin.fpr[register] as u32)
                } else {
                    (
                        register,
                        FprLane::High32,
                        (begin.fpr[register] >> 32) as u32,
                    )
                }
            };
            let bytes = match begin.endian {
                CpuEndian::Big => value.to_be_bytes(),
                CpuEndian::Little => value.to_le_bytes(),
            };
            (
                FprSelection {
                    register: register as u8,
                    lane,
                },
                bytes.to_vec(),
            )
        }
        Cop1StoreKind::Sdc1 => {
            let register = if begin.fr { ft } else { ft & !1 };
            let value = begin.fpr[register];
            let bytes = match begin.endian {
                CpuEndian::Big => value.to_be_bytes(),
                CpuEndian::Little => value.to_le_bytes(),
            };
            (
                FprSelection {
                    register: register as u8,
                    lane: FprLane::Full64,
                },
                bytes.to_vec(),
            )
        }
    };
    Ok((store, ft as u8, selection, bytes))
}

fn expected_location(cache: CachePolicy) -> MutationLocation {
    match cache {
        CachePolicy::Cached => MutationLocation::CacheResident,
        CachePolicy::Uncached => MutationLocation::Backing,
    }
}

fn replay_success(active: &Active<'_>) -> Result<CpuMutationWitness, String> {
    let begin = active.begin;
    let destination = begin
        .destination
        .ok_or("successful CPU mutation missing destination")?;
    let cache = begin
        .cache
        .ok_or("successful CPU mutation missing cache policy")?;
    let (store, ft, source, payload) = payload_and_source(begin)?;
    let end = destination
        .0
        .checked_add(payload.len() as u32)
        .ok_or("CPU mutation destination overflow")?;
    require(
        end <= RDRAM_SIZE,
        "CPU mutation outside bounded RDRAM scope",
    )?;

    let location = expected_location(cache);
    let mut covered = vec![false; payload.len()];
    let mut effect_ordinals = Vec::with_capacity(active.effects.len());
    for effect in &active.effects {
        require(
            effect.location == location,
            "CPU mutation location disagrees with cache policy",
        )?;
        require(!effect.bytes.is_empty(), "empty CPU mutation effect")?;
        let start = effect
            .address
            .0
            .checked_sub(destination.0)
            .ok_or("CPU mutation effect precedes destination")? as usize;
        let stop = start
            .checked_add(effect.bytes.len())
            .ok_or("CPU mutation effect range overflow")?;
        require(
            stop <= payload.len(),
            "CPU mutation effect exceeds semantic store range",
        )?;
        for (index, byte) in effect.bytes.iter().enumerate() {
            let offset = start + index;
            require(!covered[offset], "overlapping CPU mutation effects")?;
            require(*byte == payload[offset], "CPU mutation payload mismatch")?;
            covered[offset] = true;
        }
        effect_ordinals.push(effect.ordinal);
    }
    require(
        covered.into_iter().all(|covered| covered),
        "incomplete CPU mutation byte effects",
    )?;

    Ok(CpuMutationWitness {
        context: begin.context,
        pc: begin.pc,
        store,
        endian: begin.endian,
        fr: begin.fr,
        ft,
        source,
        destination,
        location,
        bytes: payload,
        effect_ordinals,
    })
}

/// Replay a complete, externally authenticated finite CPU mutation capture.
///
/// The expected digest must come from a separately trusted complete-source receipt.
/// Successful replay proves only that this captured history is internally consistent.
/// It does not prove that every CPU/RSP/DMA mutation was sensed.
pub fn inspect_cpu_mutation_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<CpuMutationReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "CPU mutation source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported CPU mutation history format",
    )?;

    let mut events: Vec<_> = history
        .begins
        .iter()
        .map(|event| (event.ordinal, Event::Begin(event)))
        .chain(
            history
                .effects
                .iter()
                .map(|event| (event.ordinal, Event::Effect(event))),
        )
        .chain(
            history
                .ends
                .iter()
                .map(|event| (event.ordinal, Event::End(event))),
        )
        .collect();
    events.sort_by_key(|event| event.0);

    let mut active: Option<Active<'_>> = None;
    let mut contexts = 0usize;
    let mut faults = 0usize;
    let mut witnesses = Vec::new();
    for (index, (ordinal, event)) in events.into_iter().enumerate() {
        require(
            ordinal == index as u64 + 1,
            "noncontiguous CPU mutation source ordinals",
        )?;
        match event {
            Event::Begin(begin) => {
                require(active.is_none(), "nested CPU mutation context")?;
                require(
                    begin.context == begin.ordinal && begin.pc.0.is_multiple_of(4),
                    "invalid CPU mutation begin context",
                )?;
                decode_cop1_store(begin.word)?;
                active = Some(Active {
                    begin,
                    effects: Vec::new(),
                });
            }
            Event::Effect(effect) => {
                let context = active.as_mut().ok_or("unscoped CPU mutation effect")?;
                require(
                    effect.context == context.begin.context,
                    "CPU mutation effect context mismatch",
                )?;
                context.effects.push(effect);
            }
            Event::End(end) => {
                let context = active.take().ok_or("CPU mutation end without begin")?;
                require(
                    end.context == context.begin.context,
                    "CPU mutation end context mismatch",
                )?;
                contexts += 1;
                match end.outcome {
                    Outcome::Success => witnesses.push(replay_success(&context)?),
                    Outcome::Fault => {
                        require(
                            context.effects.is_empty(),
                            "faulted CPU mutation emitted a byte effect",
                        )?;
                        require(
                            context.begin.destination.is_none() && context.begin.cache.is_none(),
                            "faulted CPU mutation retained successful destination metadata",
                        )?;
                        faults += 1;
                    }
                }
            }
        }
    }
    require(active.is_none(), "truncated CPU mutation context")?;

    Ok(CpuMutationReport {
        format: FORMAT.into(),
        source_sha256: digest,
        instruction_contexts: contexts,
        successful_mutations: witnesses.len(),
        faulted_contexts: faults,
        witnesses,
        mutation_coverage_certified: false,
        fpr_ancestry_certified: false,
        executable_lifetime_certified: false,
        hardware_atomicity_certified: false,
        native_complete: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};

    const F0: u64 = 0x1122_3344_5566_7788;
    const F1: u64 = 0x99aa_bbcc_ddee_ff00;

    fn fprs() -> Vec<u64> {
        let mut fpr = vec![0; 32];
        fpr[0] = F0;
        fpr[1] = F1;
        fpr
    }

    fn word(op: u32, ft: u32) -> u32 {
        (op << 26) | (ft << 16)
    }

    fn history(begin: Value, effects: Vec<Value>, end: Value) -> Vec<u8> {
        serde_json::to_vec(&json!({
            "format": FORMAT,
            "begins": [begin],
            "effects": effects,
            "ends": [end]
        }))
        .unwrap()
    }

    fn inspect(source: &[u8]) -> Result<CpuMutationReport, String> {
        inspect_cpu_mutation_history(source, &sha256(source))
    }

    fn begin(
        word: u32,
        endian: &str,
        fr: bool,
        destination: Option<u32>,
        cache: Option<&str>,
    ) -> Value {
        json!({
            "ordinal": 1,
            "context": 1,
            "pc": 0x80001000u64,
            "word": word,
            "endian": endian,
            "fr": fr,
            "fpr": fprs(),
            "destination": destination,
            "cache": cache
        })
    }

    fn success_end(ordinal: u64) -> Value {
        json!({"ordinal": ordinal, "context": 1, "outcome": "success"})
    }

    #[test]
    fn fr0_odd_swc1_selects_paired_high_lane() {
        let source = history(
            begin(word(0x39, 1), "big", false, Some(0x1000), Some("uncached")),
            vec![json!({
                "ordinal": 2,
                "context": 1,
                "location": "backing",
                "address": 0x1000,
                "bytes": [0x11, 0x22, 0x33, 0x44]
            })],
            success_end(3),
        );
        let report = inspect(&source).unwrap();
        assert_eq!(report.successful_mutations, 1);
        let witness = &report.witnesses[0];
        assert_eq!(witness.store, Cop1StoreKind::Swc1);
        assert_eq!(witness.source.register, 0);
        assert_eq!(witness.source.lane, FprLane::High32);
        assert_eq!(witness.bytes, vec![0x11, 0x22, 0x33, 0x44]);
        assert!(!report.mutation_coverage_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn sdc1_accepts_fragmented_callback_topology() {
        let source = history(
            begin(word(0x3d, 1), "big", false, Some(0x2000), Some("uncached")),
            vec![
                json!({
                    "ordinal": 2,
                    "context": 1,
                    "location": "backing",
                    "address": 0x2000,
                    "bytes": [0x11, 0x22, 0x33, 0x44]
                }),
                json!({
                    "ordinal": 3,
                    "context": 1,
                    "location": "backing",
                    "address": 0x2004,
                    "bytes": [0x55, 0x66, 0x77, 0x88]
                }),
            ],
            success_end(4),
        );
        let report = inspect(&source).unwrap();
        assert_eq!(report.witnesses[0].effect_ordinals, vec![2, 3]);
        assert_eq!(report.witnesses[0].source.register, 0);
        assert_eq!(report.witnesses[0].source.lane, FprLane::Full64);
    }

    #[test]
    fn little_endian_payload_is_normalized_from_selected_bits() {
        let source = history(
            begin(word(0x39, 1), "little", true, Some(0x3000), Some("cached")),
            vec![json!({
                "ordinal": 2,
                "context": 1,
                "location": "cache_resident",
                "address": 0x3000,
                "bytes": [0x00, 0xff, 0xee, 0xdd]
            })],
            success_end(3),
        );
        let report = inspect(&source).unwrap();
        assert_eq!(report.witnesses[0].source.register, 1);
        assert_eq!(report.witnesses[0].bytes, vec![0x00, 0xff, 0xee, 0xdd]);
    }

    #[test]
    fn equal_value_wrong_generation_does_not_select_a_source() {
        let mut begin = begin(word(0x39, 1), "big", false, Some(0x1000), Some("uncached"));
        begin["fpr"][1] = json!(0x0000_0000_1122_3344u64);
        let source = history(
            begin,
            vec![json!({
                "ordinal": 2,
                "context": 1,
                "location": "backing",
                "address": 0x1000,
                "bytes": [0x11, 0x22, 0x33, 0x44]
            })],
            success_end(3),
        );
        let report = inspect(&source).unwrap();
        assert_eq!(report.witnesses[0].source.register, 0);
        assert_eq!(report.witnesses[0].source.lane, FprLane::High32);
    }

    #[test]
    fn rejects_wrong_equal_length_payload() {
        let source = history(
            begin(word(0x39, 1), "big", false, Some(0x1000), Some("uncached")),
            vec![json!({
                "ordinal": 2,
                "context": 1,
                "location": "backing",
                "address": 0x1000,
                "bytes": [0x55, 0x66, 0x77, 0x88]
            })],
            success_end(3),
        );
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn rejects_overlap_or_missing_byte_effects() {
        let overlap = history(
            begin(word(0x39, 0), "big", false, Some(0x1000), Some("uncached")),
            vec![
                json!({"ordinal": 2, "context": 1, "location": "backing", "address": 0x1000, "bytes": [0x55, 0x66]}),
                json!({"ordinal": 3, "context": 1, "location": "backing", "address": 0x1001, "bytes": [0x66, 0x77, 0x88]}),
            ],
            success_end(4),
        );
        assert!(inspect(&overlap).is_err());

        let missing = history(
            begin(word(0x39, 0), "big", false, Some(0x1000), Some("uncached")),
            vec![
                json!({"ordinal": 2, "context": 1, "location": "backing", "address": 0x1000, "bytes": [0x55, 0x66, 0x77]}),
            ],
            success_end(3),
        );
        assert!(inspect(&missing).is_err());
    }

    #[test]
    fn rejects_backing_effect_for_cached_store() {
        let source = history(
            begin(word(0x39, 0), "big", false, Some(0x1000), Some("cached")),
            vec![json!({
                "ordinal": 2,
                "context": 1,
                "location": "backing",
                "address": 0x1000,
                "bytes": [0x55, 0x66, 0x77, 0x88]
            })],
            success_end(3),
        );
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn rejects_effect_from_faulted_attempt() {
        let source = history(
            begin(word(0x39, 0), "big", false, None, None),
            vec![json!({
                "ordinal": 2,
                "context": 1,
                "location": "backing",
                "address": 0x1000,
                "bytes": [0x55, 0x66, 0x77, 0x88]
            })],
            json!({"ordinal": 3, "context": 1, "outcome": "fault"}),
        );
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn accepts_fault_without_mutation_but_certifies_nothing_broader() {
        let source = history(
            begin(word(0x3d, 1), "big", false, None, None),
            vec![],
            json!({"ordinal": 2, "context": 1, "outcome": "fault"}),
        );
        let report = inspect(&source).unwrap();
        assert_eq!(report.faulted_contexts, 1);
        assert!(report.witnesses.is_empty());
        assert!(!report.fpr_ancestry_certified);
        assert!(!report.hardware_atomicity_certified);
        assert!(!report.executable_lifetime_certified);
    }

    #[test]
    fn rejects_deleted_or_forged_source_history() {
        let source = history(
            begin(word(0x39, 0), "big", false, Some(0x1000), Some("uncached")),
            vec![json!({
                "ordinal": 3,
                "context": 1,
                "location": "backing",
                "address": 0x1000,
                "bytes": [0x55, 0x66, 0x77, 0x88]
            })],
            success_end(4),
        );
        assert!(inspect(&source).is_err());

        let valid = history(
            begin(word(0x39, 0), "big", false, Some(0x1000), Some("uncached")),
            vec![json!({
                "ordinal": 2,
                "context": 1,
                "location": "backing",
                "address": 0x1000,
                "bytes": [0x55, 0x66, 0x77, 0x88]
            })],
            success_end(3),
        );
        assert!(inspect_cpu_mutation_history(&valid, &"0".repeat(64)).is_err());
    }
}
