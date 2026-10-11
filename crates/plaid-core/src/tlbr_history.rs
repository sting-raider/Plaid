//! Bounded source-bound replay of decoded TLBR translation-context loads.
//!
//! A successful in-range TLBR is an operation generation even when the selected
//! entry is bit-identical to the already-active context. The load boundary is
//! distinct from TLB-entry mutation: this module never mints an installed-entry
//! mapping generation. It also does not infer sensor completeness, PageMask/global
//! policy, cache residency, executable lifetime, or native readiness.

use crate::{program::GuestVirtualAddr, rom::sha256};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-tlbr-history-v0";
const TLBR_WORD: u32 = 0x4200_0001;
const TLB_ENTRIES: u32 = 32;

/// Fingerprint of one normalized active TLB context / selected entry snapshot.
///
/// The producer is responsible for hashing the same canonical field set for both
/// selected entries and active contexts. This replay authenticates the supplied
/// complete history; it does not independently reconstruct the fingerprint.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbContextFingerprint {
    pub sha256: String,
    pub asid: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TlbrNoLoadKind {
    OutOfRangeIndex,
    Exception { code: u8 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbrContextGeneration {
    pub operation_generation: u64,
    pub epoch: u64,
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub begin_ordinal: u64,
    pub load_ordinal: u64,
    pub end_ordinal: u64,
    pub selected_slot: u32,
    pub before_context: TlbContextFingerprint,
    pub selected_entry: TlbContextFingerprint,
    pub after_context: TlbContextFingerprint,
    pub same_context_content: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbrNoLoadAttempt {
    pub epoch: u64,
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub begin_ordinal: u64,
    pub end_ordinal: u64,
    pub cp0_index: u32,
    pub before_context: TlbContextFingerprint,
    pub kind: TlbrNoLoadKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbrHistoryReport {
    pub format: String,
    pub source_sha256: String,
    pub attempts: usize,
    pub load_boundaries: usize,
    pub same_context_generations: usize,
    pub generations: Vec<TlbrContextGeneration>,
    pub no_load_attempts: Vec<TlbrNoLoadAttempt>,
    pub sensor_coverage_certified: bool,
    pub installed_mapping_certified: bool,
    pub translation_context_census_certified: bool,
    pub cache_residency_certified: bool,
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
    Begin {
        ordinal: u64,
        context: u64,
        epoch: u64,
        pc: GuestVirtualAddr,
        word: u32,
        cp0_index: u32,
        before_context: TlbContextFingerprint,
    },
    Load {
        ordinal: u64,
        context: u64,
        slot: u32,
        selected_entry: TlbContextFingerprint,
        after_context: TlbContextFingerprint,
    },
    End {
        ordinal: u64,
        context: u64,
        epoch: u64,
        pc: GuestVirtualAddr,
        exception_code: u8,
    },
}

struct Active {
    begin_ordinal: u64,
    context: u64,
    epoch: u64,
    pc: GuestVirtualAddr,
    cp0_index: u32,
    before_context: TlbContextFingerprint,
    load: Option<ObservedLoad>,
}

struct ObservedLoad {
    ordinal: u64,
    slot: u32,
    selected_entry: TlbContextFingerprint,
    after_context: TlbContextFingerprint,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn validate_fingerprint(value: &TlbContextFingerprint) -> Result<(), String> {
    require(
        value.sha256.len() == 64
            && value
                .sha256
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)),
        "invalid TLBR context fingerprint",
    )
}

/// Inspect one externally authenticated complete TLBR source.
///
/// `expected_sha256` must come from a separately trusted complete-source receipt.
/// Replaying this finite source proves only the operation boundaries present in
/// that source. It does not prove that every architecturally relevant context
/// writer was observed.
pub fn inspect_tlbr_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<TlbrHistoryReport, String> {
    let digest = sha256(source);
    require(digest == expected_sha256, "TLBR source receipt mismatch")?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(history.format == FORMAT, "unsupported TLBR history format")?;

    let mut next_ordinal = 1u64;
    let mut last_epoch = 0u64;
    let mut attempts = 0usize;
    let mut active: Option<Active> = None;
    let mut generations = Vec::new();
    let mut no_load_attempts = Vec::new();

    for event in history.events {
        match event {
            Event::Begin {
                ordinal,
                context,
                epoch,
                pc,
                word,
                cp0_index,
                before_context,
            } => {
                require(ordinal == next_ordinal, "noncontiguous TLBR event ordinals")?;
                next_ordinal += 1;
                require(active.is_none(), "nested TLBR begin")?;
                require(context == ordinal, "TLBR context must equal begin ordinal")?;
                require(
                    epoch != 0 && epoch >= last_epoch,
                    "invalid or reordered TLBR epoch",
                )?;
                require(pc.0.is_multiple_of(4), "unaligned TLBR PC")?;
                require(word == TLBR_WORD, "history begin is not decoded TLBR")?;
                require(cp0_index < 64, "TLBR CP0 Index outside captured field")?;
                validate_fingerprint(&before_context)?;
                last_epoch = epoch;
                attempts += 1;
                active = Some(Active {
                    begin_ordinal: ordinal,
                    context,
                    epoch,
                    pc,
                    cp0_index,
                    before_context,
                    load: None,
                });
            }
            Event::Load {
                ordinal,
                context,
                slot,
                selected_entry,
                after_context,
            } => {
                require(ordinal == next_ordinal, "noncontiguous TLBR event ordinals")?;
                next_ordinal += 1;
                let current = active
                    .as_mut()
                    .ok_or("TLBR load without active instruction")?;
                require(context == current.context, "TLBR load context mismatch")?;
                require(current.load.is_none(), "duplicate TLBR load boundary")?;
                require(
                    current.cp0_index < TLB_ENTRIES
                        && slot < TLB_ENTRIES
                        && slot == current.cp0_index,
                    "TLBR load did not use the captured CP0 Index slot",
                )?;
                validate_fingerprint(&selected_entry)?;
                validate_fingerprint(&after_context)?;
                require(
                    selected_entry == after_context,
                    "TLBR active context does not match the selected entry",
                )?;
                current.load = Some(ObservedLoad {
                    ordinal,
                    slot,
                    selected_entry,
                    after_context,
                });
            }
            Event::End {
                ordinal,
                context,
                epoch,
                pc,
                exception_code,
            } => {
                require(ordinal == next_ordinal, "noncontiguous TLBR event ordinals")?;
                next_ordinal += 1;
                let current = active.take().ok_or("TLBR end without active instruction")?;
                require(
                    (context, epoch, pc) == (current.context, current.epoch, current.pc),
                    "TLBR end context mismatch",
                )?;
                require(exception_code <= 31, "invalid TLBR exception code")?;

                if let Some(load) = current.load {
                    require(
                        exception_code == 0,
                        "faulting TLBR cannot carry a successful context load",
                    )?;
                    let same_context_content = current.before_context == load.after_context;
                    generations.push(TlbrContextGeneration {
                        operation_generation: generations.len() as u64 + 1,
                        epoch: current.epoch,
                        context: current.context,
                        pc: current.pc,
                        begin_ordinal: current.begin_ordinal,
                        load_ordinal: load.ordinal,
                        end_ordinal: ordinal,
                        selected_slot: load.slot,
                        before_context: current.before_context,
                        selected_entry: load.selected_entry,
                        after_context: load.after_context,
                        same_context_content,
                    });
                } else {
                    require(
                        current.cp0_index >= TLB_ENTRIES || exception_code != 0,
                        "in-range successful TLBR lacks an observed load boundary",
                    )?;
                    let kind = if exception_code != 0 {
                        TlbrNoLoadKind::Exception {
                            code: exception_code,
                        }
                    } else {
                        TlbrNoLoadKind::OutOfRangeIndex
                    };
                    no_load_attempts.push(TlbrNoLoadAttempt {
                        epoch: current.epoch,
                        context: current.context,
                        pc: current.pc,
                        begin_ordinal: current.begin_ordinal,
                        end_ordinal: ordinal,
                        cp0_index: current.cp0_index,
                        before_context: current.before_context,
                        kind,
                    });
                }
            }
        }
    }

    require(active.is_none(), "truncated TLBR instruction context")?;
    let same_context_generations = generations
        .iter()
        .filter(|generation| generation.same_context_content)
        .count();

    Ok(TlbrHistoryReport {
        format: history.format,
        source_sha256: digest,
        attempts,
        load_boundaries: generations.len(),
        same_context_generations,
        generations,
        no_load_attempts,
        sensor_coverage_certified: false,
        installed_mapping_certified: false,
        translation_context_census_certified: false,
        cache_residency_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_tlbr_report(
    report: &TlbrHistoryReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_tlbr_history(source, expected_sha256)?,
        "TLBR report differs from complete source replay",
    )
}
