//! Source-bound replay for finite COP1 mutation histories.
//!
//! The canonical `cpu_mutation` module verifies one independently observed completed
//! SWC1/SDC1 effect. This layer authenticates and replays a finite ordered source,
//! groups one-or-many lower-observer fragments into one semantic completed effect,
//! and delegates the architectural source/destination/payload checks to that
//! canonical primitive.
//!
//! A successful replay proves only internal consistency of the supplied authenticated
//! history. It does not prove capture completeness, physical mapping truth, ultimate
//! FPR ancestry, later dirty-line writeback, executable lifetime, hardware transaction
//! atomicity, mutation census completeness, or native completeness.

use crate::{
    cpu_mutation::{
        CompletedCop1StoreEffect, Cop1MutationWitness, CpuMutationDomain, decode_cop1_store,
        verify_cop1_store_effect,
    },
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-cpu-mutation-history-v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MutationOutcome {
    Success,
    Fault,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuMutationHistoryWitness {
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub fragment_ordinals: Vec<u64>,
    pub mutation: Cop1MutationWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuMutationHistoryReport {
    pub format: String,
    pub source_sha256: String,
    pub instruction_contexts: usize,
    pub successful_mutations: usize,
    pub faulted_contexts: usize,
    pub witnesses: Vec<CpuMutationHistoryWitness>,
    pub capture_completeness_certified: bool,
    pub physical_mapping_certified: bool,
    pub fpr_ancestry_certified: bool,
    pub dirty_writeback_certified: bool,
    pub hardware_atomicity_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum Event {
    Begin(BeginEvent),
    Effect(EffectEvent),
    End(EndEvent),
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct BeginEvent {
    ordinal: u64,
    context: u64,
    pc: GuestVirtualAddr,
    instruction_word: u32,
    gpr: [u64; 32],
    raw_fprs: [u64; 32],
    fr: bool,
    cu1: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct EffectEvent {
    ordinal: u64,
    context: u64,
    virtual_address: GuestVirtualAddr,
    physical_address: PhysicalAddr,
    domain: CpuMutationDomain,
    payload: Vec<u8>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct EndEvent {
    ordinal: u64,
    context: u64,
    outcome: MutationOutcome,
}

struct Active<'a> {
    begin: &'a BeginEvent,
    effects: Vec<&'a EffectEvent>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn coalesce_effect(
    active: &Active<'_>,
    completion_ordinal: u64,
) -> Result<(CompletedCop1StoreEffect, Vec<u64>), String> {
    let first = active
        .effects
        .first()
        .ok_or("successful CPU mutation has no concrete effect")?;
    require(!first.payload.is_empty(), "empty CPU mutation fragment")?;

    let mut payload = Vec::new();
    let mut fragment_ordinals = Vec::with_capacity(active.effects.len());
    let base_virtual = first.virtual_address;
    let base_physical = first.physical_address;
    let domain = first.domain;

    for effect in &active.effects {
        require(!effect.payload.is_empty(), "empty CPU mutation fragment")?;
        require(
            effect.domain == domain,
            "CPU mutation fragments cross mutation domains",
        )?;

        let offset = payload.len();
        let expected_virtual = base_virtual
            .0
            .checked_add(offset as u64)
            .ok_or("CPU mutation virtual fragment range overflow")?;
        let expected_physical = base_physical
            .0
            .checked_add(offset as u32)
            .ok_or("CPU mutation physical fragment range overflow")?;
        require(
            effect.virtual_address.0 == expected_virtual,
            "CPU mutation virtual fragments are missing, overlapping, or reordered",
        )?;
        require(
            effect.physical_address.0 == expected_physical,
            "CPU mutation physical fragments are missing, overlapping, or reordered",
        )?;

        payload.extend_from_slice(&effect.payload);
        fragment_ordinals.push(effect.ordinal);
    }

    Ok((
        CompletedCop1StoreEffect {
            effect_ordinal: completion_ordinal,
            virtual_destination: base_virtual,
            physical_destination: base_physical,
            domain,
            payload,
        },
        fragment_ordinals,
    ))
}

/// Replay an externally complete, SHA-bound finite COP1 mutation history.
///
/// The digest must come from a separately trusted complete-source receipt. The
/// replay deliberately derives the semantic completed-effect identity from the
/// source `end` ordinal instead of lower-observer callback count, so one 8-byte
/// callback and two ordered 4-byte callbacks can represent the same SDC1 semantic
/// mutation without asserting anything about hardware transaction atomicity.
pub fn inspect_cpu_mutation_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<CpuMutationHistoryReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "CPU mutation history source receipt mismatch",
    )?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported CPU mutation history format",
    )?;

    let mut active: Option<Active<'_>> = None;
    let mut instruction_contexts = 0usize;
    let mut faulted_contexts = 0usize;
    let mut witnesses = Vec::new();

    for (index, event) in history.events.iter().enumerate() {
        let ordinal = match event {
            Event::Begin(event) => event.ordinal,
            Event::Effect(event) => event.ordinal,
            Event::End(event) => event.ordinal,
        };
        require(
            ordinal == index as u64 + 1,
            "noncontiguous CPU mutation history ordinals",
        )?;

        match event {
            Event::Begin(begin) => {
                require(active.is_none(), "nested CPU mutation instruction context")?;
                require(
                    begin.context == begin.ordinal,
                    "CPU mutation context identity is not its begin ordinal",
                )?;
                require(
                    begin.pc.0.is_multiple_of(4),
                    "unaligned CPU mutation instruction PC",
                )?;
                require(
                    decode_cop1_store(begin.instruction_word).is_some(),
                    "unsupported CPU mutation instruction cause",
                )?;
                active = Some(Active {
                    begin,
                    effects: Vec::new(),
                });
            }
            Event::Effect(effect) => {
                let context = active.as_mut().ok_or("unscoped CPU mutation fragment")?;
                require(
                    effect.context == context.begin.context,
                    "CPU mutation fragment context mismatch",
                )?;
                context.effects.push(effect);
            }
            Event::End(end) => {
                let context = active.take().ok_or("CPU mutation end without begin")?;
                require(
                    end.context == context.begin.context,
                    "CPU mutation end context mismatch",
                )?;
                instruction_contexts += 1;

                match end.outcome {
                    MutationOutcome::Fault => {
                        require(
                            context.effects.is_empty(),
                            "faulted CPU mutation emitted a concrete effect",
                        )?;
                        let witness = verify_cop1_store_effect(
                            context.begin.instruction_word,
                            &context.begin.gpr,
                            &context.begin.raw_fprs,
                            context.begin.fr,
                            context.begin.cu1,
                            None,
                        )?;
                        require(
                            witness.is_none(),
                            "faulted CPU mutation unexpectedly produced a witness",
                        )?;
                        faulted_contexts += 1;
                    }
                    MutationOutcome::Success => {
                        let (effect, fragment_ordinals) = coalesce_effect(&context, end.ordinal)?;
                        let mutation = verify_cop1_store_effect(
                            context.begin.instruction_word,
                            &context.begin.gpr,
                            &context.begin.raw_fprs,
                            context.begin.fr,
                            context.begin.cu1,
                            Some(&effect),
                        )?
                        .ok_or("successful CPU mutation did not produce a witness")?;
                        witnesses.push(CpuMutationHistoryWitness {
                            context: context.begin.context,
                            pc: context.begin.pc,
                            fragment_ordinals,
                            mutation,
                        });
                    }
                }
            }
        }
    }

    require(active.is_none(), "truncated CPU mutation instruction context")?;

    Ok(CpuMutationHistoryReport {
        format: FORMAT.into(),
        source_sha256: digest,
        instruction_contexts,
        successful_mutations: witnesses.len(),
        faulted_contexts,
        witnesses,
        capture_completeness_certified: false,
        physical_mapping_certified: false,
        fpr_ancestry_certified: false,
        dirty_writeback_certified: false,
        hardware_atomicity_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};

    fn swc1(ft: u32) -> u32 {
        (0x39 << 26) | (1 << 21) | (ft << 16)
    }

    fn sdc1(ft: u32) -> u32 {
        (0x3d << 26) | (1 << 21) | (ft << 16)
    }

    fn gprs() -> Vec<u64> {
        let mut gpr = vec![0; 32];
        gpr[1] = 0xffff_ffff_a000_2000;
        gpr
    }

    fn fprs() -> Vec<u64> {
        let mut fpr = vec![0; 32];
        fpr[0] = 0x1122_3344_5566_7788;
        fpr[1] = 0x99aa_bbcc_ddee_ff00;
        fpr
    }

    fn begin(word: u32, fr: bool, cu1: bool) -> Value {
        json!({
            "type": "begin",
            "ordinal": 1,
            "context": 1,
            "pc": 0xffff_ffff_8000_1000u64,
            "instruction_word": word,
            "gpr": gprs(),
            "raw_fprs": fprs(),
            "fr": fr,
            "cu1": cu1
        })
    }

    fn effect(
        ordinal: u64,
        virtual_address: u64,
        physical_address: u32,
        domain: &str,
        payload: &[u8],
    ) -> Value {
        json!({
            "type": "effect",
            "ordinal": ordinal,
            "context": 1,
            "virtual_address": virtual_address,
            "physical_address": physical_address,
            "domain": domain,
            "payload": payload
        })
    }

    fn end(ordinal: u64, outcome: &str) -> Value {
        json!({
            "type": "end",
            "ordinal": ordinal,
            "context": 1,
            "outcome": outcome
        })
    }

    fn source(events: Vec<Value>) -> Vec<u8> {
        serde_json::to_vec(&json!({"format": FORMAT, "events": events})).unwrap()
    }

    fn inspect(source: &[u8]) -> Result<CpuMutationHistoryReport, String> {
        inspect_cpu_mutation_history(source, &sha256(source))
    }

    #[test]
    fn fragmented_sdc1_delegates_one_semantic_completed_effect() {
        let source = source(vec![
            begin(sdc1(1), false, true),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x11, 0x22, 0x33, 0x44],
            ),
            effect(
                3,
                0xffff_ffff_a000_2004,
                0x2004,
                "backing",
                &[0x55, 0x66, 0x77, 0x88],
            ),
            end(4, "success"),
        ]);
        let report = inspect(&source).unwrap();
        assert_eq!(report.successful_mutations, 1);
        assert_eq!(report.witnesses[0].fragment_ordinals, vec![2, 3]);
        assert_eq!(report.witnesses[0].mutation.effect_ordinal, 4);
        assert_eq!(
            report.witnesses[0].mutation.payload,
            vec![0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]
        );
        assert!(!report.hardware_atomicity_certified);
        assert!(!report.capture_completeness_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn one_and_two_fragment_topologies_normalize_to_same_mutation() {
        let single = source(vec![
            begin(sdc1(1), false, true),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88],
            ),
            end(3, "success"),
        ]);
        let split = source(vec![
            begin(sdc1(1), false, true),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x11, 0x22, 0x33, 0x44],
            ),
            effect(
                3,
                0xffff_ffff_a000_2004,
                0x2004,
                "backing",
                &[0x55, 0x66, 0x77, 0x88],
            ),
            end(4, "success"),
        ]);
        let single = inspect(&single).unwrap();
        let split = inspect(&split).unwrap();
        assert_eq!(single.witnesses[0].mutation.kind, split.witnesses[0].mutation.kind);
        assert_eq!(single.witnesses[0].mutation.source, split.witnesses[0].mutation.source);
        assert_eq!(single.witnesses[0].mutation.domain, split.witnesses[0].mutation.domain);
        assert_eq!(single.witnesses[0].mutation.payload, split.witnesses[0].mutation.payload);
        assert_ne!(
            single.witnesses[0].fragment_ordinals,
            split.witnesses[0].fragment_ordinals
        );
    }

    #[test]
    fn equal_value_wrong_fr_source_is_rejected_by_canonical_primitive() {
        let source = source(vec![
            begin(swc1(1), true, true),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x11, 0x22, 0x33, 0x44],
            ),
            end(3, "success"),
        ]);
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn rejects_missing_overlapping_or_reordered_fragments() {
        let missing = source(vec![
            begin(sdc1(1), false, true),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x11, 0x22, 0x33, 0x44],
            ),
            end(3, "success"),
        ]);
        assert!(inspect(&missing).is_err());

        let overlap = source(vec![
            begin(sdc1(1), false, true),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x11, 0x22, 0x33, 0x44],
            ),
            effect(
                3,
                0xffff_ffff_a000_2002,
                0x2002,
                "backing",
                &[0x55, 0x66, 0x77, 0x88],
            ),
            end(4, "success"),
        ]);
        assert!(inspect(&overlap).is_err());
    }

    #[test]
    fn rejects_cross_domain_fragment_join() {
        let source = source(vec![
            begin(sdc1(1), false, true),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "cache_resident",
                &[0x11, 0x22, 0x33, 0x44],
            ),
            effect(
                3,
                0xffff_ffff_a000_2004,
                0x2004,
                "backing",
                &[0x55, 0x66, 0x77, 0x88],
            ),
            end(4, "success"),
        ]);
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn faulted_attempt_must_have_no_effects() {
        let clean = source(vec![begin(swc1(0), false, false), end(2, "fault")]);
        let report = inspect(&clean).unwrap();
        assert_eq!(report.faulted_contexts, 1);
        assert!(report.witnesses.is_empty());

        let forged = source(vec![
            begin(swc1(0), false, false),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x55, 0x66, 0x77, 0x88],
            ),
            end(3, "fault"),
        ]);
        assert!(inspect(&forged).is_err());
    }

    #[test]
    fn cu1_disabled_success_is_rejected() {
        let source = source(vec![
            begin(swc1(0), false, false),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x55, 0x66, 0x77, 0x88],
            ),
            end(3, "success"),
        ]);
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn rejects_deleted_reordered_cross_context_and_forged_sources() {
        let gap = source(vec![
            begin(swc1(0), false, true),
            effect(
                3,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x55, 0x66, 0x77, 0x88],
            ),
            end(4, "success"),
        ]);
        assert!(inspect(&gap).is_err());

        let cross_context = serde_json::to_vec(&json!({
            "format": FORMAT,
            "events": [
                begin(swc1(0), false, true),
                {
                    "type": "effect",
                    "ordinal": 2,
                    "context": 99,
                    "virtual_address": 0xffff_ffff_a000_2000u64,
                    "physical_address": 0x2000,
                    "domain": "backing",
                    "payload": [0x55, 0x66, 0x77, 0x88]
                },
                end(3, "success")
            ]
        }))
        .unwrap();
        assert!(inspect(&cross_context).is_err());

        let valid = source(vec![
            begin(swc1(0), false, true),
            effect(
                2,
                0xffff_ffff_a000_2000,
                0x2000,
                "backing",
                &[0x55, 0x66, 0x77, 0x88],
            ),
            end(3, "success"),
        ]);
        assert!(inspect_cpu_mutation_history(&valid, &"0".repeat(64)).is_err());
    }
}
