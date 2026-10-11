//! Source-bound replay for the validated cached BEV=0 general exception root.
//!
//! This module composes an already-derived architectural exception root with a
//! finite observed backing/fill/invalidation/fetch chronology. It intentionally
//! does not infer resident code from current backing bytes or equal payloads and
//! does not claim mutation-census, reachability, lifetime, or whole-ROM closure.
use crate::{
    exception_roots::{
        ExceptionClass, ExceptionRootInput, ExceptionRootReceipt, ExceptionVectorClass,
        KernelAddressMode, resolve_exception_root,
    },
    program::PhysicalAddr,
    rom::sha256,
};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-exception-root-generation-history-v0";
pub const POLICY: &str = "identity_rdram_cached_bev0_general_word";
const ROOT_PHYSICAL: PhysicalAddr = PhysicalAddr(0x0000_0180);

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    policy: String,
    events: Vec<Event>,
}

#[derive(Debug, Clone, Copy, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    BackingWrite {
        ordinal: u64,
        physical: PhysicalAddr,
        word: u32,
    },
    Fill {
        ordinal: u64,
        physical: PhysicalAddr,
        word: u32,
    },
    Invalidate {
        ordinal: u64,
        physical: PhysicalAddr,
    },
    RootFetch {
        ordinal: u64,
        input: ExceptionRootInput,
        physical: PhysicalAddr,
        word: u32,
    },
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::BackingWrite { ordinal, .. }
            | Self::Fill { ordinal, .. }
            | Self::Invalidate { ordinal, .. }
            | Self::RootFetch { ordinal, .. } => *ordinal,
        }
    }

    fn physical(&self) -> PhysicalAddr {
        match self {
            Self::BackingWrite { physical, .. }
            | Self::Fill { physical, .. }
            | Self::Invalidate { physical, .. }
            | Self::RootFetch { physical, .. } => *physical,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BackingGeneration {
    pub write_ordinal: u64,
    pub word: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "kind")]
pub enum RootWordOrigin {
    Resident {
        fill_ordinal: u64,
        backing_write_ordinal: u64,
    },
    Unknown,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExceptionRootWordWitness {
    pub fetch_ordinal: u64,
    pub architectural_root: ExceptionRootReceipt,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub current_backing: Option<BackingGeneration>,
    pub origin: RootWordOrigin,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExceptionRootGenerationReport {
    pub format: String,
    pub policy: String,
    pub source_sha256: String,
    pub records: usize,
    pub root_fetches: usize,
    pub witnesses: Vec<ExceptionRootWordWitness>,
    pub reachability_certified: bool,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone, Copy)]
struct ResidentGeneration {
    fill_ordinal: u64,
    backing_write_ordinal: u64,
    word: u32,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn require_validated_root(input: ExceptionRootInput) -> Result<ExceptionRootReceipt, String> {
    require(
        input
            == ExceptionRootInput {
                class: ExceptionClass::General,
                bev: false,
                exl: false,
                kernel_mode: KernelAddressMode::Bits32,
            },
        "exception root fetch is outside the validated BEV=0 general-root scope",
    )?;
    let receipt = resolve_exception_root(input);
    require(
        receipt.vector_class == ExceptionVectorClass::General
            && receipt.root.0 == 0xffff_ffff_8000_0180,
        "exception root resolver disagrees with validated cached root",
    )?;
    Ok(receipt)
}

/// Replay one externally source-bound finite root chronology.
///
/// Event ordinals are causal identities, not presentation counters: every
/// successful backing write advances backing identity even when its bits are
/// unchanged, and every fill advances resident identity. A backing write never
/// silently refreshes an existing resident line. If a root fetch has no captured
/// resident/fill witness, its origin remains `Unknown` even when current backing
/// contains identical bits.
pub fn inspect_exception_root_generation_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<ExceptionRootGenerationReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "exception root generation source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported exception root generation format",
    )?;
    require(
        history.policy == POLICY,
        "unsupported exception root generation policy",
    )?;

    let mut backing: Option<BackingGeneration> = None;
    let mut resident: Option<ResidentGeneration> = None;
    let mut witnesses = Vec::new();

    for (index, event) in history.events.iter().enumerate() {
        require(
            event.ordinal() == index as u64 + 1,
            "noncontiguous exception root generation ordinals",
        )?;
        require(
            event.physical() == ROOT_PHYSICAL,
            "exception root generation event targets an unsupported physical word",
        )?;
        match *event {
            Event::BackingWrite { ordinal, word, .. } => {
                backing = Some(BackingGeneration {
                    write_ordinal: ordinal,
                    word,
                });
            }
            Event::Fill { ordinal, word, .. } => {
                let source = backing.ok_or("cache fill lacks a captured backing generation")?;
                require(
                    word == source.word,
                    "cache fill payload differs from its captured backing generation",
                )?;
                resident = Some(ResidentGeneration {
                    fill_ordinal: ordinal,
                    backing_write_ordinal: source.write_ordinal,
                    word,
                });
            }
            Event::Invalidate { .. } => resident = None,
            Event::RootFetch {
                ordinal,
                input,
                word,
                ..
            } => {
                let architectural_root = require_validated_root(input)?;
                let origin = match resident {
                    Some(resident) => {
                        require(
                            word == resident.word,
                            "root fetch payload differs from captured resident generation",
                        )?;
                        RootWordOrigin::Resident {
                            fill_ordinal: resident.fill_ordinal,
                            backing_write_ordinal: resident.backing_write_ordinal,
                        }
                    }
                    None => RootWordOrigin::Unknown,
                };
                witnesses.push(ExceptionRootWordWitness {
                    fetch_ordinal: ordinal,
                    architectural_root,
                    physical: ROOT_PHYSICAL,
                    word,
                    current_backing: backing,
                    origin,
                });
            }
        }
    }

    Ok(ExceptionRootGenerationReport {
        format: history.format,
        policy: history.policy,
        source_sha256: digest,
        records: history.events.len(),
        root_fetches: witnesses.len(),
        witnesses,
        reachability_certified: false,
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_exception_root_generation_report(
    report: &ExceptionRootGenerationReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_exception_root_generation_history(source, expected_sha256)?,
        "exception root generation report differs from complete source replay",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};

    fn input() -> Value {
        json!({
            "class": "general",
            "bev": false,
            "exl": false,
            "kernel_mode": "bits32"
        })
    }

    fn history(events: Vec<Value>) -> Vec<u8> {
        serde_json::to_vec(&json!({
            "format": FORMAT,
            "policy": POLICY,
            "events": events
        }))
        .unwrap()
    }

    fn inspect(events: Vec<Value>) -> Result<ExceptionRootGenerationReport, String> {
        let bytes = history(events);
        inspect_exception_root_generation_history(&bytes, &sha256(&bytes))
    }

    fn write(ordinal: u64, word: u32) -> Value {
        json!({"kind":"backing_write","ordinal":ordinal,"physical":384,"word":word})
    }

    fn fill(ordinal: u64, word: u32) -> Value {
        json!({"kind":"fill","ordinal":ordinal,"physical":384,"word":word})
    }

    fn invalidate(ordinal: u64) -> Value {
        json!({"kind":"invalidate","ordinal":ordinal,"physical":384})
    }

    fn root(ordinal: u64, word: u32) -> Value {
        json!({
            "kind":"root_fetch",
            "ordinal":ordinal,
            "input":input(),
            "physical":384,
            "word":word
        })
    }

    #[test]
    fn backing_rewrite_does_not_steal_resident_root_generation() {
        let report = inspect(vec![write(1, 1), fill(2, 1), write(3, 2), root(4, 1)]).unwrap();
        let witness = &report.witnesses[0];
        assert_eq!(
            witness.origin,
            RootWordOrigin::Resident {
                fill_ordinal: 2,
                backing_write_ordinal: 1
            }
        );
        assert_eq!(
            witness.current_backing,
            Some(BackingGeneration {
                write_ordinal: 3,
                word: 2
            })
        );
        assert!(!report.reachability_certified);
        assert!(!report.mutation_coverage_certified);
        assert!(!report.executable_lifetime_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn refill_after_write_moves_origin_to_new_backing_generation() {
        let report = inspect(vec![
            write(1, 1),
            fill(2, 1),
            write(3, 2),
            invalidate(4),
            fill(5, 2),
            root(6, 2),
        ])
        .unwrap();
        assert_eq!(
            report.witnesses[0].origin,
            RootWordOrigin::Resident {
                fill_ordinal: 5,
                backing_write_ordinal: 3
            }
        );
    }

    #[test]
    fn refill_before_write_remains_stale() {
        let report = inspect(vec![
            write(1, 1),
            fill(2, 1),
            invalidate(3),
            fill(4, 1),
            write(5, 2),
            root(6, 1),
        ])
        .unwrap();
        assert_eq!(
            report.witnesses[0].origin,
            RootWordOrigin::Resident {
                fill_ordinal: 4,
                backing_write_ordinal: 1
            }
        );
        assert_eq!(
            report.witnesses[0]
                .current_backing
                .expect("current backing")
                .write_ordinal,
            5
        );
    }

    #[test]
    fn same_value_write_advances_backing_without_relabeling_resident() {
        let report = inspect(vec![write(1, 7), fill(2, 7), write(3, 7), root(4, 7)]).unwrap();
        assert_eq!(
            report.witnesses[0].origin,
            RootWordOrigin::Resident {
                fill_ordinal: 2,
                backing_write_ordinal: 1
            }
        );
        assert_eq!(
            report.witnesses[0]
                .current_backing
                .expect("current backing")
                .write_ordinal,
            3
        );
    }

    #[test]
    fn same_value_refill_after_rewrite_uses_new_generation() {
        let report = inspect(vec![
            write(1, 7),
            fill(2, 7),
            write(3, 7),
            invalidate(4),
            fill(5, 7),
            root(6, 7),
        ])
        .unwrap();
        assert_eq!(
            report.witnesses[0].origin,
            RootWordOrigin::Resident {
                fill_ordinal: 5,
                backing_write_ordinal: 3
            }
        );
    }

    #[test]
    fn current_backing_without_resident_evidence_stays_unknown() {
        let report = inspect(vec![write(1, 9), root(2, 9)]).unwrap();
        assert_eq!(report.witnesses[0].origin, RootWordOrigin::Unknown);
        assert_eq!(
            report.witnesses[0]
                .current_backing
                .expect("current backing")
                .write_ordinal,
            1
        );
    }

    #[test]
    fn rejects_deleted_or_reordered_ordinals() {
        assert!(inspect(vec![write(1, 1), fill(3, 1)]).is_err());
        assert!(inspect(vec![write(2, 1), fill(1, 1)]).is_err());
    }

    #[test]
    fn rejects_fill_and_fetch_payload_forgery() {
        assert!(inspect(vec![write(1, 1), fill(2, 2)]).is_err());
        assert!(inspect(vec![write(1, 1), fill(2, 1), root(3, 2)]).is_err());
    }

    #[test]
    fn rejects_wrong_physical_or_root_scope() {
        let wrong_physical = json!({"kind":"backing_write","ordinal":1,"physical":388,"word":1});
        assert!(inspect(vec![wrong_physical]).is_err());

        let mut wrong_root = root(2, 1);
        wrong_root["input"]["bev"] = json!(true);
        assert!(inspect(vec![write(1, 1), wrong_root]).is_err());
    }

    #[test]
    fn complete_source_hash_and_report_replay_are_binding() {
        let bytes = history(vec![write(1, 1), fill(2, 1), root(3, 1)]);
        let digest = sha256(&bytes);
        let report = inspect_exception_root_generation_history(&bytes, &digest).unwrap();
        verify_exception_root_generation_report(&report, &bytes, &digest).unwrap();

        let mut forged = bytes.clone();
        let last = forged.len() - 1;
        forged[last] = b' ';
        assert!(inspect_exception_root_generation_history(&forged, &digest).is_err());

        let mut altered = report;
        altered.witnesses[0].word ^= 1;
        assert!(verify_exception_root_generation_report(&altered, &bytes, &digest).is_err());
    }
}
