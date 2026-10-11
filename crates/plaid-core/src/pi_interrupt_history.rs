//! Source-bound replay for the PI completion -> MI.PI -> CPU RCP-pending seam.
//!
//! This module deliberately stops before the CPU Status/BEV interrupt-entry gate.
//! A PI byte copy is not a completion witness, a current register snapshot is not
//! producer ancestry, and equal payload/state values do not collapse operations.
//! The expected source hash must come from a separately trusted complete-source
//! receipt; finite replay here does not certify sensor coverage or hardware timing.

use crate::rom::sha256;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const FORMAT: &str = "plaid-pi-interrupt-history-v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PiCompletionGeneration {
    pub completion_generation: u64,
    pub ordinal: u64,
    pub request: u64,
    pub token: u64,
    pub dispatch_event: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RawPiEvidence {
    Unknown,
    Low,
    Completion {
        completion_generation: u64,
        request: u64,
        token: u64,
        dispatch_event: u32,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CpuRcpPendingEvidence {
    Unknown,
    Deasserted,
    Asserted {
        completion_generation: u64,
        request: u64,
        token: u64,
        dispatch_event: u32,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PiPollCause {
    Completion { completion_generation: u64 },
    MaskWrite { same_value: bool },
    InterruptClear,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PiPollGeneration {
    pub poll_generation: u64,
    pub ordinal: u64,
    pub cause: PiPollCause,
    pub raw_pi: RawPiEvidence,
    pub mi_pi_mask: Option<bool>,
    pub cpu_rcp_pending: CpuRcpPendingEvidence,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PiInterruptHistoryReport {
    pub format: String,
    pub source_sha256: String,
    pub events: usize,
    pub completions: Vec<PiCompletionGeneration>,
    pub polls: Vec<PiPollGeneration>,
    pub restore_cuts: Vec<u64>,
    pub same_value_mask_writes: usize,
    pub unknown_polls: usize,
    pub certified_pending_assertions: usize,
    pub final_raw_pi: RawPiEvidence,
    pub final_mi_pi_mask: Option<bool>,
    pub final_cpu_rcp_pending: CpuRcpPendingEvidence,
    pub sensor_coverage_certified: bool,
    pub hardware_timing_certified: bool,
    pub cpu_interrupt_gate_certified: bool,
    pub root_transfer_certified: bool,
    pub handler_provenance_certified: bool,
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
    Completion {
        ordinal: u64,
        request: u64,
        token: u64,
        dispatch_event: u32,
    },
    InterruptClear {
        ordinal: u64,
    },
    MaskWrite {
        ordinal: u64,
        enabled: bool,
    },
    RestoreBoundary {
        ordinal: u64,
    },
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn pending(raw: RawPiEvidence, mask: Option<bool>) -> CpuRcpPendingEvidence {
    match (raw, mask) {
        (RawPiEvidence::Low, _) | (_, Some(false)) => CpuRcpPendingEvidence::Deasserted,
        (
            RawPiEvidence::Completion {
                completion_generation,
                request,
                token,
                dispatch_event,
            },
            Some(true),
        ) => CpuRcpPendingEvidence::Asserted {
            completion_generation,
            request,
            token,
            dispatch_event,
        },
        (RawPiEvidence::Unknown, _) | (RawPiEvidence::Completion { .. }, None) => {
            CpuRcpPendingEvidence::Unknown
        }
    }
}

fn record_poll(
    polls: &mut Vec<PiPollGeneration>,
    ordinal: u64,
    cause: PiPollCause,
    raw_pi: RawPiEvidence,
    mi_pi_mask: Option<bool>,
) -> CpuRcpPendingEvidence {
    let cpu_rcp_pending = pending(raw_pi, mi_pi_mask);
    polls.push(PiPollGeneration {
        poll_generation: polls.len() as u64 + 1,
        ordinal,
        cause,
        raw_pi,
        mi_pi_mask,
        cpu_rcp_pending,
    });
    cpu_rcp_pending
}

/// Replay one complete, independently authenticated PI/MI producer history.
///
/// `completion` records are trusted observation boundaries, not facts inferred
/// from PI copies or queue snapshots. A restore boundary cuts both raw-line and
/// mask ancestry to UNKNOWN until later observed operations re-establish them.
pub fn inspect_pi_interrupt_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<PiInterruptHistoryReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "PI interrupt source receipt mismatch",
    )?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported PI interrupt history format",
    )?;

    let event_count = history.events.len();
    let mut raw_pi = RawPiEvidence::Unknown;
    let mut mi_pi_mask = None;
    let mut current_pending = CpuRcpPendingEvidence::Unknown;
    let mut completions = Vec::new();
    let mut polls = Vec::new();
    let mut restore_cuts = Vec::new();
    let mut seen_requests = BTreeSet::new();
    let mut seen_tokens = BTreeSet::new();
    let mut same_value_mask_writes = 0usize;

    for (next_ordinal, event) in (1u64..).zip(history.events) {
        let ordinal = match event {
            Event::Completion { ordinal, .. }
            | Event::InterruptClear { ordinal }
            | Event::MaskWrite { ordinal, .. }
            | Event::RestoreBoundary { ordinal } => ordinal,
        };
        require(
            ordinal == next_ordinal,
            "noncontiguous PI interrupt event ordinals",
        )?;

        match event {
            Event::Completion {
                request,
                token,
                dispatch_event,
                ..
            } => {
                require(
                    request != 0 && token != 0 && dispatch_event <= 1,
                    "invalid PI completion identity",
                )?;
                require(
                    seen_requests.insert(request) && seen_tokens.insert(token),
                    "reused PI completion request/token identity",
                )?;
                let completion = PiCompletionGeneration {
                    completion_generation: completions.len() as u64 + 1,
                    ordinal,
                    request,
                    token,
                    dispatch_event,
                };
                completions.push(completion);
                raw_pi = RawPiEvidence::Completion {
                    completion_generation: completion.completion_generation,
                    request,
                    token,
                    dispatch_event,
                };
                current_pending = record_poll(
                    &mut polls,
                    ordinal,
                    PiPollCause::Completion {
                        completion_generation: completion.completion_generation,
                    },
                    raw_pi,
                    mi_pi_mask,
                );
            }
            Event::InterruptClear { .. } => {
                raw_pi = RawPiEvidence::Low;
                current_pending = record_poll(
                    &mut polls,
                    ordinal,
                    PiPollCause::InterruptClear,
                    raw_pi,
                    mi_pi_mask,
                );
            }
            Event::MaskWrite { enabled, .. } => {
                let same_value = mi_pi_mask == Some(enabled);
                if same_value {
                    same_value_mask_writes += 1;
                }
                mi_pi_mask = Some(enabled);
                current_pending = record_poll(
                    &mut polls,
                    ordinal,
                    PiPollCause::MaskWrite { same_value },
                    raw_pi,
                    mi_pi_mask,
                );
            }
            Event::RestoreBoundary { .. } => {
                raw_pi = RawPiEvidence::Unknown;
                mi_pi_mask = None;
                current_pending = CpuRcpPendingEvidence::Unknown;
                restore_cuts.push(ordinal);
            }
        }
    }

    let unknown_polls = polls
        .iter()
        .filter(|poll| poll.cpu_rcp_pending == CpuRcpPendingEvidence::Unknown)
        .count();
    let certified_pending_assertions = polls
        .iter()
        .filter(|poll| matches!(poll.cpu_rcp_pending, CpuRcpPendingEvidence::Asserted { .. }))
        .count();

    Ok(PiInterruptHistoryReport {
        format: history.format,
        source_sha256: digest,
        events: event_count,
        completions,
        polls,
        restore_cuts,
        same_value_mask_writes,
        unknown_polls,
        certified_pending_assertions,
        final_raw_pi: raw_pi,
        final_mi_pi_mask: mi_pi_mask,
        final_cpu_rcp_pending: current_pending,
        sensor_coverage_certified: false,
        hardware_timing_certified: false,
        cpu_interrupt_gate_certified: false,
        root_transfer_certified: false,
        handler_provenance_certified: false,
        native_complete: false,
    })
}

pub fn verify_pi_interrupt_report(
    report: &PiInterruptHistoryReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_pi_interrupt_history(source, expected_sha256)?,
        "PI interrupt report differs from complete source replay",
    )
}
