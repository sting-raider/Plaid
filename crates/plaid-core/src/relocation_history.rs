//! Bounded source-bound replay of runtime MIPS HI16/LO16 relocation mutations.
//!
//! The replay assigns load, storage, and relocation-operation generations from
//! ordered source events. Equal words, targets, and sites never substitute for
//! those generations. This module does not discover relocators, prove a mutation
//! census, authenticate HI16/LO16 semantic pairing, establish cache-visible
//! executable lifetime, or discharge ProgramMap relocation blockers.

use crate::{program::GuestVirtualAddr, rom::sha256};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FORMAT: &str = "plaid-runtime-relocation-history-v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeRelocationKind {
    MipsHi16,
    MipsLo16,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LoadedWordGeneration {
    pub storage_generation: u64,
    pub ordinal: u64,
    pub site: GuestVirtualAddr,
    pub word: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LoadGeneration {
    pub load_generation: u64,
    pub context: u64,
    pub begin_ordinal: u64,
    pub end_ordinal: u64,
    pub words: Vec<LoadedWordGeneration>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeRelocationGeneration {
    pub operation_generation: u64,
    pub context: u64,
    pub kind: RuntimeRelocationKind,
    pub site: GuestVirtualAddr,
    pub target: u32,
    pub load_generation: u64,
    pub input_storage_generation: u64,
    pub output_storage_generation: u64,
    pub begin_ordinal: u64,
    pub write_ordinal: u64,
    pub end_ordinal: u64,
    pub preimage_word: u32,
    pub postimage_word: u32,
    pub same_value_write: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HiLoPairReceipt {
    pub hi_operation_generation: u64,
    pub lo_operation_generation: u64,
    pub target: u32,
    pub load_generation: u64,
    pub hi_site: GuestVirtualAddr,
    pub lo_site: GuestVirtualAddr,
    /// Same-load/target/order is only a necessary bounded check. It does not
    /// authenticate guest symbolic pairing or addend semantics.
    pub semantic_pairing_certified: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeRelocationHistoryReport {
    pub format: String,
    pub source_sha256: String,
    pub loads: Vec<LoadGeneration>,
    pub relocations: Vec<RuntimeRelocationGeneration>,
    pub same_value_relocations: usize,
    pub relocator_discovery_certified: bool,
    pub mutation_census_certified: bool,
    pub pair_semantics_certified: bool,
    pub cache_visibility_certified: bool,
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
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    LoadBegin {
        ordinal: u64,
        context: u64,
    },
    LoadWord {
        ordinal: u64,
        context: u64,
        site: GuestVirtualAddr,
        word: u32,
    },
    LoadEnd {
        ordinal: u64,
        context: u64,
    },
    RelocationBegin {
        ordinal: u64,
        context: u64,
        site: GuestVirtualAddr,
        kind: RuntimeRelocationKind,
        target: u32,
    },
    RelocationWrite {
        ordinal: u64,
        context: u64,
        site: GuestVirtualAddr,
        before_word: u32,
        after_word: u32,
    },
    RelocationEnd {
        ordinal: u64,
        context: u64,
        site: GuestVirtualAddr,
    },
}

#[derive(Debug, Clone, Copy)]
struct StorageState {
    storage_generation: u64,
    load_generation: u64,
    word: u32,
}

struct ActiveLoad {
    context: u64,
    generation: u64,
    begin_ordinal: u64,
    words: Vec<LoadedWordGeneration>,
}

struct ActiveRelocation {
    context: u64,
    begin_ordinal: u64,
    site: GuestVirtualAddr,
    kind: RuntimeRelocationKind,
    target: u32,
    input: StorageState,
    write: Option<ObservedWrite>,
}

struct ObservedWrite {
    ordinal: u64,
    output_storage_generation: u64,
    before_word: u32,
    after_word: u32,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn consume_ordinal(ordinal: u64, next_ordinal: &mut u64) -> Result<(), String> {
    require(
        ordinal == *next_ordinal,
        "noncontiguous relocation history ordinals",
    )?;
    *next_ordinal = next_ordinal
        .checked_add(1)
        .ok_or("relocation history ordinal overflow")?;
    Ok(())
}

fn mint_generation(counter: &mut u64, label: &str) -> Result<u64, String> {
    *counter = counter
        .checked_add(1)
        .ok_or_else(|| format!("{label} generation overflow"))?;
    Ok(*counter)
}

fn validate_site(site: GuestVirtualAddr) -> Result<(), String> {
    require(site.0.is_multiple_of(4), "unaligned relocation site")
}

fn transform_word(kind: RuntimeRelocationKind, before: u32, target: u32) -> u32 {
    let immediate = match kind {
        RuntimeRelocationKind::MipsHi16 => target.wrapping_add(0x8000) >> 16,
        RuntimeRelocationKind::MipsLo16 => target & 0xffff,
    };
    (before & 0xffff_0000) | (immediate & 0xffff)
}

/// Inspect one externally authenticated, finite relocation history.
///
/// The expected hash must come from a separately trusted complete-source receipt.
/// Successful replay authenticates this supplied chronology only; it does not
/// certify that the producer observed every relocation or executable mutation.
pub fn inspect_runtime_relocation_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<RuntimeRelocationHistoryReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "runtime relocation source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported runtime relocation history format",
    )?;

    let mut next_ordinal = 1u64;
    let mut load_generation_counter = 0u64;
    let mut storage_generation_counter = 0u64;
    let mut active_load: Option<ActiveLoad> = None;
    let mut active_relocation: Option<ActiveRelocation> = None;
    let mut storage = BTreeMap::<GuestVirtualAddr, StorageState>::new();
    let mut loads = Vec::new();
    let mut relocations = Vec::new();

    for event in history.events {
        match event {
            Event::LoadBegin { ordinal, context } => {
                consume_ordinal(ordinal, &mut next_ordinal)?;
                require(
                    active_load.is_none() && active_relocation.is_none(),
                    "nested or overlapping relocation/load context",
                )?;
                require(context == ordinal, "load context must equal begin ordinal")?;
                let generation = mint_generation(&mut load_generation_counter, "load")?;
                active_load = Some(ActiveLoad {
                    context,
                    generation,
                    begin_ordinal: ordinal,
                    words: Vec::new(),
                });
            }
            Event::LoadWord {
                ordinal,
                context,
                site,
                word,
            } => {
                consume_ordinal(ordinal, &mut next_ordinal)?;
                validate_site(site)?;
                let current = active_load
                    .as_mut()
                    .ok_or("load word without active load context")?;
                require(
                    active_relocation.is_none() && context == current.context,
                    "load word context mismatch",
                )?;
                let storage_generation =
                    mint_generation(&mut storage_generation_counter, "storage")?;
                storage.insert(
                    site,
                    StorageState {
                        storage_generation,
                        load_generation: current.generation,
                        word,
                    },
                );
                current.words.push(LoadedWordGeneration {
                    storage_generation,
                    ordinal,
                    site,
                    word,
                });
            }
            Event::LoadEnd { ordinal, context } => {
                consume_ordinal(ordinal, &mut next_ordinal)?;
                let current = active_load.take().ok_or("load end without begin")?;
                require(
                    active_relocation.is_none() && context == current.context,
                    "load end context mismatch",
                )?;
                require(
                    !current.words.is_empty(),
                    "empty executable load generation",
                )?;
                loads.push(LoadGeneration {
                    load_generation: current.generation,
                    context: current.context,
                    begin_ordinal: current.begin_ordinal,
                    end_ordinal: ordinal,
                    words: current.words,
                });
            }
            Event::RelocationBegin {
                ordinal,
                context,
                site,
                kind,
                target,
            } => {
                consume_ordinal(ordinal, &mut next_ordinal)?;
                validate_site(site)?;
                require(
                    active_load.is_none() && active_relocation.is_none(),
                    "nested or overlapping relocation/load context",
                )?;
                require(
                    context == ordinal,
                    "relocation context must equal begin ordinal",
                )?;
                let input = *storage
                    .get(&site)
                    .ok_or("relocation site has no captured storage generation")?;
                active_relocation = Some(ActiveRelocation {
                    context,
                    begin_ordinal: ordinal,
                    site,
                    kind,
                    target,
                    input,
                    write: None,
                });
            }
            Event::RelocationWrite {
                ordinal,
                context,
                site,
                before_word,
                after_word,
            } => {
                consume_ordinal(ordinal, &mut next_ordinal)?;
                validate_site(site)?;
                let current = active_relocation
                    .as_mut()
                    .ok_or("relocation write without active relocation")?;
                require(
                    active_load.is_none() && context == current.context && site == current.site,
                    "relocation write context mismatch",
                )?;
                require(current.write.is_none(), "duplicate relocation write")?;
                require(
                    before_word == current.input.word,
                    "relocation preimage differs from captured storage generation",
                )?;
                require(
                    after_word == transform_word(current.kind, before_word, current.target),
                    "relocation postimage does not match bounded transform",
                )?;
                require(
                    storage.get(&site).copied().is_some_and(|state| {
                        state.storage_generation == current.input.storage_generation
                            && state.load_generation == current.input.load_generation
                            && state.word == current.input.word
                    }),
                    "relocation input storage generation is no longer current",
                )?;
                let output_storage_generation =
                    mint_generation(&mut storage_generation_counter, "storage")?;
                storage.insert(
                    site,
                    StorageState {
                        storage_generation: output_storage_generation,
                        load_generation: current.input.load_generation,
                        word: after_word,
                    },
                );
                current.write = Some(ObservedWrite {
                    ordinal,
                    output_storage_generation,
                    before_word,
                    after_word,
                });
            }
            Event::RelocationEnd {
                ordinal,
                context,
                site,
            } => {
                consume_ordinal(ordinal, &mut next_ordinal)?;
                let current = active_relocation
                    .take()
                    .ok_or("relocation end without begin")?;
                require(
                    active_load.is_none() && context == current.context && site == current.site,
                    "relocation end context mismatch",
                )?;
                let write = current
                    .write
                    .ok_or("completed relocation lacks concrete write boundary")?;
                let operation_generation = u64::try_from(relocations.len())
                    .map_err(|_| "relocation generation overflow")?
                    .checked_add(1)
                    .ok_or("relocation generation overflow")?;
                relocations.push(RuntimeRelocationGeneration {
                    operation_generation,
                    context: current.context,
                    kind: current.kind,
                    site: current.site,
                    target: current.target,
                    load_generation: current.input.load_generation,
                    input_storage_generation: current.input.storage_generation,
                    output_storage_generation: write.output_storage_generation,
                    begin_ordinal: current.begin_ordinal,
                    write_ordinal: write.ordinal,
                    end_ordinal: ordinal,
                    preimage_word: write.before_word,
                    postimage_word: write.after_word,
                    same_value_write: write.before_word == write.after_word,
                });
            }
        }
    }

    require(active_load.is_none(), "truncated executable load context")?;
    require(
        active_relocation.is_none(),
        "truncated runtime relocation context",
    )?;
    let same_value_relocations = relocations
        .iter()
        .filter(|relocation| relocation.same_value_write)
        .count();

    Ok(RuntimeRelocationHistoryReport {
        format: history.format,
        source_sha256: digest,
        loads,
        relocations,
        same_value_relocations,
        relocator_discovery_certified: false,
        mutation_census_certified: false,
        pair_semantics_certified: false,
        cache_visibility_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

/// Reconstruct the whole report from the authenticated source.
pub fn verify_runtime_relocation_report(
    report: &RuntimeRelocationHistoryReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_runtime_relocation_history(source, expected_sha256)?,
        "runtime relocation report differs from complete source replay",
    )
}

/// Check only the bounded chronology prerequisites shared by a HI16/LO16 pair.
/// This does not prove that guest code intended the two operations as one symbolic
/// relocation or authenticate an addend/pairing record.
pub fn inspect_hi16_lo16_pair(
    report: &RuntimeRelocationHistoryReport,
    hi_operation_generation: u64,
    lo_operation_generation: u64,
) -> Result<HiLoPairReceipt, String> {
    let hi = report
        .relocations
        .iter()
        .find(|relocation| relocation.operation_generation == hi_operation_generation)
        .ok_or("HI16 relocation generation not present")?;
    let lo = report
        .relocations
        .iter()
        .find(|relocation| relocation.operation_generation == lo_operation_generation)
        .ok_or("LO16 relocation generation not present")?;
    require(
        hi.kind == RuntimeRelocationKind::MipsHi16 && lo.kind == RuntimeRelocationKind::MipsLo16,
        "relocation pair has wrong kinds",
    )?;
    require(hi.target == lo.target, "relocation pair target mismatch")?;
    require(
        hi.load_generation == lo.load_generation,
        "relocation pair crosses executable load generations",
    )?;
    require(
        hi.end_ordinal < lo.begin_ordinal,
        "relocation pair chronology is not HI16 before LO16",
    )?;
    Ok(HiLoPairReceipt {
        hi_operation_generation,
        lo_operation_generation,
        target: hi.target,
        load_generation: hi.load_generation,
        hi_site: hi.site,
        lo_site: lo.site,
        semantic_pairing_certified: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};

    fn source(events: Vec<Value>) -> Vec<u8> {
        serde_json::to_vec(&json!({"format": FORMAT, "events": events})).unwrap()
    }

    fn inspect(events: Vec<Value>) -> Result<RuntimeRelocationHistoryReport, String> {
        let bytes = source(events);
        let digest = sha256(&bytes);
        inspect_runtime_relocation_history(&bytes, &digest)
    }

    fn load(context: u64, site: u64, word: u32) -> Vec<Value> {
        vec![
            json!({"record":"load_begin","ordinal":context,"context":context}),
            json!({"record":"load_word","ordinal":context + 1,"context":context,"site":site,"word":word}),
            json!({"record":"load_end","ordinal":context + 2,"context":context}),
        ]
    }

    fn relocate(
        context: u64,
        site: u64,
        kind: &str,
        target: u32,
        before: u32,
        after: u32,
    ) -> Vec<Value> {
        vec![
            json!({"record":"relocation_begin","ordinal":context,"context":context,"site":site,"kind":kind,"target":target}),
            json!({"record":"relocation_write","ordinal":context + 1,"context":context,"site":site,"before_word":before,"after_word":after}),
            json!({"record":"relocation_end","ordinal":context + 2,"context":context,"site":site}),
        ]
    }

    #[test]
    fn erased_preimages_keep_distinct_load_and_storage_generations() {
        let target = 0x8040_8000;
        let mut events = load(1, 0x8000_1000, 0x3c08_1111);
        events.extend(relocate(
            4,
            0x8000_1000,
            "mips_hi16",
            target,
            0x3c08_1111,
            0x3c08_8041,
        ));
        events.extend(load(7, 0x8000_1000, 0x3c08_2222));
        events.extend(relocate(
            10,
            0x8000_1000,
            "mips_hi16",
            target,
            0x3c08_2222,
            0x3c08_8041,
        ));
        let report = inspect(events).unwrap();
        assert_eq!(report.relocations.len(), 2);
        assert_eq!(report.relocations[0].postimage_word, 0x3c08_8041);
        assert_eq!(report.relocations[1].postimage_word, 0x3c08_8041);
        assert_ne!(
            report.relocations[0].load_generation,
            report.relocations[1].load_generation
        );
        assert_ne!(
            report.relocations[0].input_storage_generation,
            report.relocations[1].input_storage_generation
        );
        assert_ne!(
            report.relocations[0].output_storage_generation,
            report.relocations[1].output_storage_generation
        );
        assert!(!report.native_complete);
    }

    #[test]
    fn same_value_relocation_still_mints_a_fresh_storage_generation() {
        let mut events = load(1, 0x8000_1000, 0x3c08_8041);
        events.extend(relocate(
            4,
            0x8000_1000,
            "mips_hi16",
            0x8040_8000,
            0x3c08_8041,
            0x3c08_8041,
        ));
        let report = inspect(events).unwrap();
        let relocation = &report.relocations[0];
        assert!(relocation.same_value_write);
        assert_eq!(report.same_value_relocations, 1);
        assert_ne!(
            relocation.input_storage_generation,
            relocation.output_storage_generation
        );
    }

    #[test]
    fn equal_payload_overlay_reload_is_a_new_load_generation() {
        let mut events = load(1, 0x8000_1000, 0x3c08_1111);
        events.extend(load(4, 0x8000_1000, 0x3c08_1111));
        let report = inspect(events).unwrap();
        assert_eq!(report.loads.len(), 2);
        assert_ne!(
            report.loads[0].load_generation,
            report.loads[1].load_generation
        );
        assert_ne!(
            report.loads[0].words[0].storage_generation,
            report.loads[1].words[0].storage_generation
        );
    }

    #[test]
    fn bounded_hi_lo_pair_requires_one_load_generation_and_order() {
        let target = 0x8040_8123;
        let mut events = vec![
            json!({"record":"load_begin","ordinal":1,"context":1}),
            json!({"record":"load_word","ordinal":2,"context":1,"site":0x80001000u64,"word":0x3c080000u32}),
            json!({"record":"load_word","ordinal":3,"context":1,"site":0x80001004u64,"word":0x25080000u32}),
            json!({"record":"load_end","ordinal":4,"context":1}),
        ];
        events.extend(relocate(
            5,
            0x8000_1000,
            "mips_hi16",
            target,
            0x3c08_0000,
            0x3c08_8041,
        ));
        events.extend(relocate(
            8,
            0x8000_1004,
            "mips_lo16",
            target,
            0x2508_0000,
            0x2508_8123,
        ));
        let report = inspect(events).unwrap();
        let pair = inspect_hi16_lo16_pair(&report, 1, 2).unwrap();
        assert_eq!(pair.load_generation, 1);
        assert!(!pair.semantic_pairing_certified);
        assert!(inspect_hi16_lo16_pair(&report, 2, 1).is_err());
    }

    #[test]
    fn cross_load_hi_lo_pair_is_rejected_even_with_equal_target() {
        let target = 0x8040_8123;
        let mut events = load(1, 0x8000_1000, 0x3c08_0000);
        events.extend(relocate(
            4,
            0x8000_1000,
            "mips_hi16",
            target,
            0x3c08_0000,
            0x3c08_8041,
        ));
        events.extend(load(7, 0x8000_1004, 0x2508_0000));
        events.extend(relocate(
            10,
            0x8000_1004,
            "mips_lo16",
            target,
            0x2508_0000,
            0x2508_8123,
        ));
        let report = inspect(events).unwrap();
        assert!(inspect_hi16_lo16_pair(&report, 1, 2).is_err());
    }

    #[test]
    fn deleted_or_forged_write_cannot_complete_a_relocation() {
        let mut missing = load(1, 0x8000_1000, 0x3c08_1111);
        missing.push(json!({"record":"relocation_begin","ordinal":4,"context":4,"site":0x80001000u64,"kind":"mips_hi16","target":0x80408000u32}));
        missing
            .push(json!({"record":"relocation_end","ordinal":5,"context":4,"site":0x80001000u64}));
        assert!(inspect(missing).is_err());

        let mut forged = load(1, 0x8000_1000, 0x3c08_1111);
        forged.extend(relocate(
            4,
            0x8000_1000,
            "mips_hi16",
            0x8040_8000,
            0x3c08_2222,
            0x3c08_8041,
        ));
        assert!(inspect(forged).is_err());
    }

    #[test]
    fn wrong_postimage_and_reordered_source_fail_closed() {
        let mut wrong = load(1, 0x8000_1000, 0x3c08_1111);
        wrong.extend(relocate(
            4,
            0x8000_1000,
            "mips_hi16",
            0x8040_8000,
            0x3c08_1111,
            0x3c08_8040,
        ));
        assert!(inspect(wrong).is_err());

        let reordered = source(vec![
            json!({"record":"load_begin","ordinal":1,"context":1}),
            json!({"record":"load_word","ordinal":3,"context":1,"site":0x80001000u64,"word":0x3c081111u32}),
        ]);
        let digest = sha256(&reordered);
        assert!(inspect_runtime_relocation_history(&reordered, &digest).is_err());
    }

    #[test]
    fn boolean_ordinal_is_not_a_numeric_generation_shortcut() {
        let bytes = br#"{"format":"plaid-runtime-relocation-history-v0","events":[{"record":"load_begin","ordinal":false,"context":1}]}"#;
        let digest = sha256(bytes);
        assert!(inspect_runtime_relocation_history(bytes, &digest).is_err());
    }

    #[test]
    fn source_receipt_and_report_are_rechecked_exactly() {
        let events = load(1, 0x8000_1000, 0x3c08_1111);
        let bytes = source(events);
        let digest = sha256(&bytes);
        let report = inspect_runtime_relocation_history(&bytes, &digest).unwrap();
        verify_runtime_relocation_report(&report, &bytes, &digest).unwrap();

        let mut forged_report = report.clone();
        forged_report.loads[0].words[0].word ^= 1;
        assert!(verify_runtime_relocation_report(&forged_report, &bytes, &digest).is_err());
        assert!(inspect_runtime_relocation_history(&bytes, &"0".repeat(64)).is_err());
    }
}
