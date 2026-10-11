//! Bounded source-bound replay of decoded TLBWR operation boundaries.
//!
//! TLBWR replacement identity comes from the observed random-selection boundary,
//! never CP0 Index, a snapshot diff, payload equality, or a later translation.
//! A legal selected-slot write is a fresh operation generation even when the
//! normalized mapping bytes are unchanged. This finite replay does not certify
//! hardware random distribution, mapping semantics, sensor completeness,
//! translation-context lifetime, cache residency, or native readiness.

use crate::{program::GuestVirtualAddr, rom::sha256, tlb_history::TlbEntryFingerprint};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-tlbwr-history-v0";
const TLBWR_WORD: u32 = 0x4200_0006;
const TLB_ENTRIES: u8 = 32;
const CAPTURED_RANDOM_VALUES: u8 = 64;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TlbwrNoWriteKind {
    OutOfRangeSelection { selected_slot: u8 },
    Exception { code: u8, selected_slot: Option<u8> },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbwrGeneration {
    pub operation_generation: u64,
    pub epoch: u64,
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub begin_ordinal: u64,
    pub select_ordinal: u64,
    pub write_ordinal: u64,
    pub end_ordinal: u64,
    pub cp0_index: u32,
    pub wired: u8,
    pub selected_slot: u8,
    pub staged_entry: TlbEntryFingerprint,
    pub before_entry: TlbEntryFingerprint,
    pub after_entry: TlbEntryFingerprint,
    pub same_entry_content: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbwrNoWriteAttempt {
    pub epoch: u64,
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub begin_ordinal: u64,
    pub select_ordinal: Option<u64>,
    pub end_ordinal: u64,
    pub cp0_index: u32,
    pub wired: u8,
    pub selected_slot: Option<u8>,
    pub staged_entry: TlbEntryFingerprint,
    pub kind: TlbwrNoWriteKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbwrHistoryReport {
    pub format: String,
    pub source_sha256: String,
    pub attempts: usize,
    pub selection_boundaries: usize,
    pub write_boundaries: usize,
    pub same_content_generations: usize,
    pub generations: Vec<TlbwrGeneration>,
    pub no_write_attempts: Vec<TlbwrNoWriteAttempt>,
    pub sensor_coverage_certified: bool,
    pub mapping_semantics_certified: bool,
    pub hardware_random_distribution_certified: bool,
    pub translation_context_certified: bool,
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
        wired: u8,
        staged_entry: TlbEntryFingerprint,
    },
    Select {
        ordinal: u64,
        context: u64,
        slot: u8,
    },
    Write {
        ordinal: u64,
        context: u64,
        slot: u8,
        before_entry: TlbEntryFingerprint,
        after_entry: TlbEntryFingerprint,
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
    wired: u8,
    staged_entry: TlbEntryFingerprint,
    selection: Option<ObservedSelection>,
    write: Option<ObservedWrite>,
}

#[derive(Clone, Copy)]
struct ObservedSelection {
    ordinal: u64,
    slot: u8,
}

struct ObservedWrite {
    ordinal: u64,
    slot: u8,
    before_entry: TlbEntryFingerprint,
    after_entry: TlbEntryFingerprint,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn validate_fingerprint(value: &TlbEntryFingerprint) -> Result<(), String> {
    require(
        value.sha256.len() == 64
            && value
                .sha256
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)),
        "invalid TLB entry fingerprint",
    )
}

/// The expected hash must come from a separately trusted complete-source receipt.
/// Replaying this finite source does not certify that the producer observed every
/// architecturally relevant TLB operation or that its random sequence is hardware
/// representative.
pub fn inspect_tlbwr_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<TlbwrHistoryReport, String> {
    let digest = sha256(source);
    require(digest == expected_sha256, "TLBWR source receipt mismatch")?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(history.format == FORMAT, "unsupported TLBWR history format")?;

    let mut next_ordinal = 1u64;
    let mut last_epoch = 0u64;
    let mut attempts = 0usize;
    let mut selection_boundaries = 0usize;
    let mut active: Option<Active> = None;
    let mut generations = Vec::new();
    let mut no_write_attempts = Vec::new();

    for event in history.events {
        match event {
            Event::Begin {
                ordinal,
                context,
                epoch,
                pc,
                word,
                cp0_index,
                wired,
                staged_entry,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous TLBWR event ordinals",
                )?;
                next_ordinal += 1;
                require(active.is_none(), "nested TLBWR begin")?;
                require(context == ordinal, "TLBWR context must equal begin ordinal")?;
                require(
                    epoch != 0 && epoch >= last_epoch,
                    "invalid or reordered TLBWR epoch",
                )?;
                require(pc.0.is_multiple_of(4), "unaligned TLBWR PC")?;
                require(word == TLBWR_WORD, "history begin is not decoded TLBWR")?;
                require(cp0_index < 64, "TLBWR CP0 Index outside captured field")?;
                require(
                    wired < CAPTURED_RANDOM_VALUES,
                    "TLBWR Wired outside captured field",
                )?;
                validate_fingerprint(&staged_entry)?;
                last_epoch = epoch;
                attempts += 1;
                active = Some(Active {
                    begin_ordinal: ordinal,
                    context,
                    epoch,
                    pc,
                    cp0_index,
                    wired,
                    staged_entry,
                    selection: None,
                    write: None,
                });
            }
            Event::Select {
                ordinal,
                context,
                slot,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous TLBWR event ordinals",
                )?;
                next_ordinal += 1;
                let current = active
                    .as_mut()
                    .ok_or("TLBWR selection without active instruction")?;
                require(
                    context == current.context,
                    "TLBWR selection context mismatch",
                )?;
                require(
                    current.selection.is_none(),
                    "duplicate TLBWR selection boundary",
                )?;
                require(
                    current.write.is_none(),
                    "TLBWR selection after write boundary",
                )?;
                require(
                    slot < CAPTURED_RANDOM_VALUES,
                    "TLBWR selection outside captured random field",
                )?;
                selection_boundaries += 1;
                current.selection = Some(ObservedSelection { ordinal, slot });
            }
            Event::Write {
                ordinal,
                context,
                slot,
                before_entry,
                after_entry,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous TLBWR event ordinals",
                )?;
                next_ordinal += 1;
                let current = active
                    .as_mut()
                    .ok_or("TLBWR write without active instruction")?;
                require(context == current.context, "TLBWR write context mismatch")?;
                require(current.write.is_none(), "duplicate TLBWR write boundary")?;
                let selection = current
                    .selection
                    .ok_or("TLBWR write lacks observed random selection")?;
                require(
                    selection.slot < TLB_ENTRIES && slot == selection.slot,
                    "TLBWR write did not target the observed selected slot",
                )?;
                validate_fingerprint(&before_entry)?;
                validate_fingerprint(&after_entry)?;
                current.write = Some(ObservedWrite {
                    ordinal,
                    slot,
                    before_entry,
                    after_entry,
                });
            }
            Event::End {
                ordinal,
                context,
                epoch,
                pc,
                exception_code,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous TLBWR event ordinals",
                )?;
                next_ordinal += 1;
                let current = active
                    .take()
                    .ok_or("TLBWR end without active instruction")?;
                require(
                    (context, epoch, pc) == (current.context, current.epoch, current.pc),
                    "TLBWR end context mismatch",
                )?;
                require(exception_code <= 31, "invalid TLBWR exception code")?;

                if let Some(write) = current.write {
                    require(
                        exception_code == 0,
                        "faulting TLBWR cannot carry a successful write boundary",
                    )?;
                    let selection = current
                        .selection
                        .ok_or("TLBWR write lacks observed random selection")?;
                    require(
                        selection.slot < TLB_ENTRIES && selection.slot == write.slot,
                        "TLBWR selected/write slot mismatch",
                    )?;
                    let same_entry_content = write.before_entry == write.after_entry;
                    generations.push(TlbwrGeneration {
                        operation_generation: generations.len() as u64 + 1,
                        epoch: current.epoch,
                        context: current.context,
                        pc: current.pc,
                        begin_ordinal: current.begin_ordinal,
                        select_ordinal: selection.ordinal,
                        write_ordinal: write.ordinal,
                        end_ordinal: ordinal,
                        cp0_index: current.cp0_index,
                        wired: current.wired,
                        selected_slot: write.slot,
                        staged_entry: current.staged_entry,
                        before_entry: write.before_entry,
                        after_entry: write.after_entry,
                        same_entry_content,
                    });
                } else {
                    let selection = current.selection;
                    let kind = if exception_code != 0 {
                        TlbwrNoWriteKind::Exception {
                            code: exception_code,
                            selected_slot: selection.map(|observed| observed.slot),
                        }
                    } else {
                        let selection = selection
                            .ok_or("successful TLBWR lacks observed random selection boundary")?;
                        require(
                            selection.slot >= TLB_ENTRIES,
                            "in-range successful TLBWR lacks an observed write boundary",
                        )?;
                        TlbwrNoWriteKind::OutOfRangeSelection {
                            selected_slot: selection.slot,
                        }
                    };
                    no_write_attempts.push(TlbwrNoWriteAttempt {
                        epoch: current.epoch,
                        context: current.context,
                        pc: current.pc,
                        begin_ordinal: current.begin_ordinal,
                        select_ordinal: selection.map(|observed| observed.ordinal),
                        end_ordinal: ordinal,
                        cp0_index: current.cp0_index,
                        wired: current.wired,
                        selected_slot: selection.map(|observed| observed.slot),
                        staged_entry: current.staged_entry,
                        kind,
                    });
                }
            }
        }
    }

    require(active.is_none(), "truncated TLBWR instruction context")?;
    let same_content_generations = generations
        .iter()
        .filter(|generation| generation.same_entry_content)
        .count();

    Ok(TlbwrHistoryReport {
        format: history.format,
        source_sha256: digest,
        attempts,
        selection_boundaries,
        write_boundaries: generations.len(),
        same_content_generations,
        generations,
        no_write_attempts,
        sensor_coverage_certified: false,
        mapping_semantics_certified: false,
        hardware_random_distribution_certified: false,
        translation_context_certified: false,
        cache_residency_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_tlbwr_report(
    report: &TlbwrHistoryReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_tlbwr_history(source, expected_sha256)?,
        "TLBWR report differs from complete source replay",
    )
}
