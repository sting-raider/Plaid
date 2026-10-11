//! Bounded source-bound replay of decoded TLBWI operation boundaries.
//!
//! A legal selected-slot write is an operation generation even when the normalized
//! mapping bytes are unchanged. This module does not infer mapping semantics,
//! translation-context lifetime, cache residency, sensor completeness, or native
//! readiness from those finite operations.

use crate::{program::GuestVirtualAddr, rom::sha256};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-tlbwi-history-v0";
const TLBWI_WORD: u32 = 0x4200_0002;
const TLB_ENTRIES: u32 = 32;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbEntryFingerprint {
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TlbwiNoWriteKind {
    OutOfRangeIndex,
    Exception { code: u8 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbwiGeneration {
    pub operation_generation: u64,
    pub epoch: u64,
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub begin_ordinal: u64,
    pub write_ordinal: u64,
    pub end_ordinal: u64,
    pub selected_slot: u32,
    pub staged_entry: TlbEntryFingerprint,
    pub before_entry: TlbEntryFingerprint,
    pub after_entry: TlbEntryFingerprint,
    pub same_entry_content: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbwiNoWriteAttempt {
    pub epoch: u64,
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub begin_ordinal: u64,
    pub end_ordinal: u64,
    pub cp0_index: u32,
    pub staged_entry: TlbEntryFingerprint,
    pub kind: TlbwiNoWriteKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbwiHistoryReport {
    pub format: String,
    pub source_sha256: String,
    pub attempts: usize,
    pub write_boundaries: usize,
    pub same_content_generations: usize,
    pub generations: Vec<TlbwiGeneration>,
    pub no_write_attempts: Vec<TlbwiNoWriteAttempt>,
    pub sensor_coverage_certified: bool,
    pub mapping_semantics_certified: bool,
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
        staged_entry: TlbEntryFingerprint,
    },
    Write {
        ordinal: u64,
        context: u64,
        slot: u32,
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
    staged_entry: TlbEntryFingerprint,
    write: Option<ObservedWrite>,
}

struct ObservedWrite {
    ordinal: u64,
    slot: u32,
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
/// architecturally relevant TLB operation.
pub fn inspect_tlbwi_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<TlbwiHistoryReport, String> {
    let digest = sha256(source);
    require(digest == expected_sha256, "TLBWI source receipt mismatch")?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(history.format == FORMAT, "unsupported TLBWI history format")?;

    let mut next_ordinal = 1u64;
    let mut last_epoch = 0u64;
    let mut attempts = 0usize;
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
                staged_entry,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous TLBWI event ordinals",
                )?;
                next_ordinal += 1;
                require(active.is_none(), "nested TLBWI begin")?;
                require(context == ordinal, "TLBWI context must equal begin ordinal")?;
                require(
                    epoch != 0 && epoch >= last_epoch,
                    "invalid or reordered TLBWI epoch",
                )?;
                require(pc.0.is_multiple_of(4), "unaligned TLBWI PC")?;
                require(word == TLBWI_WORD, "history begin is not decoded TLBWI")?;
                require(cp0_index < 64, "TLBWI CP0 Index outside captured field")?;
                validate_fingerprint(&staged_entry)?;
                last_epoch = epoch;
                attempts += 1;
                active = Some(Active {
                    begin_ordinal: ordinal,
                    context,
                    epoch,
                    pc,
                    cp0_index,
                    staged_entry,
                    write: None,
                });
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
                    "noncontiguous TLBWI event ordinals",
                )?;
                next_ordinal += 1;
                let current = active
                    .as_mut()
                    .ok_or("TLBWI write without active instruction")?;
                require(context == current.context, "TLBWI write context mismatch")?;
                require(current.write.is_none(), "duplicate TLBWI write boundary")?;
                require(
                    current.cp0_index < TLB_ENTRIES
                        && slot < TLB_ENTRIES
                        && slot == current.cp0_index,
                    "TLBWI write did not target the captured CP0 Index slot",
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
                    "noncontiguous TLBWI event ordinals",
                )?;
                next_ordinal += 1;
                let current = active
                    .take()
                    .ok_or("TLBWI end without active instruction")?;
                require(
                    (context, epoch, pc) == (current.context, current.epoch, current.pc),
                    "TLBWI end context mismatch",
                )?;
                require(exception_code <= 31, "invalid TLBWI exception code")?;
                if let Some(write) = current.write {
                    require(
                        exception_code == 0,
                        "faulting TLBWI cannot carry a successful write boundary",
                    )?;
                    let same_entry_content = write.before_entry == write.after_entry;
                    generations.push(TlbwiGeneration {
                        operation_generation: generations.len() as u64 + 1,
                        epoch: current.epoch,
                        context: current.context,
                        pc: current.pc,
                        begin_ordinal: current.begin_ordinal,
                        write_ordinal: write.ordinal,
                        end_ordinal: ordinal,
                        selected_slot: write.slot,
                        staged_entry: current.staged_entry,
                        before_entry: write.before_entry,
                        after_entry: write.after_entry,
                        same_entry_content,
                    });
                } else {
                    require(
                        current.cp0_index >= TLB_ENTRIES || exception_code != 0,
                        "in-range successful TLBWI lacks an observed write boundary",
                    )?;
                    let kind = if exception_code != 0 {
                        TlbwiNoWriteKind::Exception {
                            code: exception_code,
                        }
                    } else {
                        TlbwiNoWriteKind::OutOfRangeIndex
                    };
                    no_write_attempts.push(TlbwiNoWriteAttempt {
                        epoch: current.epoch,
                        context: current.context,
                        pc: current.pc,
                        begin_ordinal: current.begin_ordinal,
                        end_ordinal: ordinal,
                        cp0_index: current.cp0_index,
                        staged_entry: current.staged_entry,
                        kind,
                    });
                }
            }
        }
    }

    require(active.is_none(), "truncated TLBWI instruction context")?;
    let same_content_generations = generations
        .iter()
        .filter(|generation| generation.same_entry_content)
        .count();

    Ok(TlbwiHistoryReport {
        format: history.format,
        source_sha256: digest,
        attempts,
        write_boundaries: generations.len(),
        same_content_generations,
        generations,
        no_write_attempts,
        sensor_coverage_certified: false,
        mapping_semantics_certified: false,
        translation_context_certified: false,
        cache_residency_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_tlbwi_report(
    report: &TlbwiHistoryReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_tlbwi_history(source, expected_sha256)?,
        "TLBWI report differs from complete source replay",
    )
}
