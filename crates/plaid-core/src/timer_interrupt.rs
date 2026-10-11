//! Source-bound finite replay for the VR4300 Count/Compare timer producer.
//!
//! The validated portable contract is deliberately narrower than an emulator
//! event scheduler: successful Count/Compare writes are distinct operations,
//! Compare writes acknowledge/clear the latched timer request even when the
//! visible Compare value is unchanged, Count writes do not acknowledge it, and
//! an observed timer assertion is a distinct causal transition. Exact timing of
//! Count rewrites relative to the next Compare match remains unresolved because
//! the pinned references disagree.
//!
//! This module replays an externally authenticated finite source. It does not
//! prove that the source observed every architecturally relevant timer operation,
//! derive assertions from register-value equality, establish interrupt eligibility,
//! or certify handler provenance/lifetime.

use crate::rom::sha256;
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-count-compare-timer-history-v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TimerRegister {
    Count,
    Compare,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TimerWriteGeneration {
    /// Fresh generation across all successfully observed Count/Compare writes.
    pub operation_generation: u64,
    /// Fresh generation within the selected register, independent of value equality.
    pub register_generation: u64,
    pub ordinal: u64,
    pub register: TimerRegister,
    pub before_value: u32,
    pub after_value: u32,
    pub same_value: bool,
    pub pending_before: bool,
    pub pending_after: bool,
    /// True only when a Compare write observed a pending request and cleared it.
    pub acknowledged_pending: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TimerAssertionGeneration {
    pub assertion_generation: u64,
    pub ordinal: u64,
    pub count: u32,
    pub compare: u32,
    /// Number of successful Count writes observed before this assertion.
    pub count_generation: u64,
    /// Number of successful Compare writes observed before this assertion.
    pub compare_generation: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TimerInterruptHistoryReport {
    pub format: String,
    pub source_sha256: String,
    pub initial_count: u32,
    pub initial_compare: u32,
    pub initial_pending: bool,
    pub writes: Vec<TimerWriteGeneration>,
    pub assertions: Vec<TimerAssertionGeneration>,
    pub final_count: u32,
    pub final_compare: u32,
    pub final_pending: bool,
    pub count_generation: u64,
    pub compare_generation: u64,
    pub sensor_coverage_certified: bool,
    pub exact_count_rewrite_timing_certified: bool,
    pub interrupt_gate_chronology_certified: bool,
    pub save_restore_reset_chronology_certified: bool,
    pub handler_lifetime_certified: bool,
    pub whole_rom_roots_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    initial_count: u32,
    initial_compare: u32,
    initial_pending: bool,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    CountWrite {
        ordinal: u64,
        before_value: u32,
        after_value: u32,
        pending_before: bool,
        pending_after: bool,
    },
    CompareWrite {
        ordinal: u64,
        before_value: u32,
        after_value: u32,
        pending_before: bool,
        pending_after: bool,
    },
    TimerAssert {
        ordinal: u64,
        count: u32,
        compare: u32,
        pending_before: bool,
        pending_after: bool,
    },
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

/// Replay one externally authenticated finite Count/Compare timer history.
///
/// `expected_sha256` must come from a separately trusted complete-source receipt.
/// A `timer_assert` record is an observed false-to-true producer transition. It
/// is intentionally not inferred from Count/Compare equality or from a scheduler
/// deadline, because the validated references disagree on Count-rewrite timing.
pub fn inspect_timer_interrupt_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<TimerInterruptHistoryReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "Count/Compare timer source receipt mismatch",
    )?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported Count/Compare timer history format",
    )?;

    let mut next_ordinal = 1u64;
    let mut count = history.initial_count;
    let mut compare = history.initial_compare;
    let mut pending = history.initial_pending;
    let mut count_generation = 0u64;
    let mut compare_generation = 0u64;
    let mut operation_generation = 0u64;
    let mut assertion_generation = 0u64;
    let mut writes = Vec::new();
    let mut assertions = Vec::new();

    for event in history.events {
        match event {
            Event::CountWrite {
                ordinal,
                before_value,
                after_value,
                pending_before,
                pending_after,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous Count/Compare timer event ordinals",
                )?;
                next_ordinal += 1;
                require(before_value == count, "Count write before-value mismatch")?;
                require(
                    pending_before == pending,
                    "Count write pending-before mismatch",
                )?;
                require(
                    pending_after == pending_before,
                    "Count write cannot acknowledge the timer request",
                )?;

                count = after_value;
                pending = pending_after;
                count_generation += 1;
                operation_generation += 1;
                writes.push(TimerWriteGeneration {
                    operation_generation,
                    register_generation: count_generation,
                    ordinal,
                    register: TimerRegister::Count,
                    before_value,
                    after_value,
                    same_value: before_value == after_value,
                    pending_before,
                    pending_after,
                    acknowledged_pending: false,
                });
            }
            Event::CompareWrite {
                ordinal,
                before_value,
                after_value,
                pending_before,
                pending_after,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous Count/Compare timer event ordinals",
                )?;
                next_ordinal += 1;
                require(
                    before_value == compare,
                    "Compare write before-value mismatch",
                )?;
                require(
                    pending_before == pending,
                    "Compare write pending-before mismatch",
                )?;
                require(
                    !pending_after,
                    "Compare write must clear the observed timer request",
                )?;

                compare = after_value;
                pending = false;
                compare_generation += 1;
                operation_generation += 1;
                writes.push(TimerWriteGeneration {
                    operation_generation,
                    register_generation: compare_generation,
                    ordinal,
                    register: TimerRegister::Compare,
                    before_value,
                    after_value,
                    same_value: before_value == after_value,
                    pending_before,
                    pending_after: false,
                    acknowledged_pending: pending_before,
                });
            }
            Event::TimerAssert {
                ordinal,
                count: observed_count,
                compare: observed_compare,
                pending_before,
                pending_after,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous Count/Compare timer event ordinals",
                )?;
                next_ordinal += 1;
                require(
                    (observed_count, observed_compare) == (count, compare),
                    "timer assertion register snapshot mismatch",
                )?;
                require(
                    pending_before == pending,
                    "timer assertion pending-before mismatch",
                )?;
                require(
                    !pending_before && pending_after,
                    "timer assertion must be an observed false-to-true transition",
                )?;

                pending = true;
                assertion_generation += 1;
                assertions.push(TimerAssertionGeneration {
                    assertion_generation,
                    ordinal,
                    count,
                    compare,
                    count_generation,
                    compare_generation,
                });
            }
        }
    }

    Ok(TimerInterruptHistoryReport {
        format: history.format,
        source_sha256: digest,
        initial_count: history.initial_count,
        initial_compare: history.initial_compare,
        initial_pending: history.initial_pending,
        writes,
        assertions,
        final_count: count,
        final_compare: compare,
        final_pending: pending,
        count_generation,
        compare_generation,
        sensor_coverage_certified: false,
        exact_count_rewrite_timing_certified: false,
        interrupt_gate_chronology_certified: false,
        save_restore_reset_chronology_certified: false,
        handler_lifetime_certified: false,
        whole_rom_roots_certified: false,
        native_complete: false,
    })
}

/// Rebuild the complete report from the authenticated source.
pub fn verify_timer_interrupt_report(
    report: &TimerInterruptHistoryReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_timer_interrupt_history(source, expected_sha256)?,
        "Count/Compare timer report differs from complete source replay",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn source(
        initial_count: u32,
        initial_compare: u32,
        initial_pending: bool,
        events: Vec<serde_json::Value>,
    ) -> Vec<u8> {
        serde_json::to_vec(&json!({
            "format": FORMAT,
            "initial_count": initial_count,
            "initial_compare": initial_compare,
            "initial_pending": initial_pending,
            "events": events,
        }))
        .unwrap()
    }

    fn inspect(source: &[u8]) -> Result<TimerInterruptHistoryReport, String> {
        inspect_timer_interrupt_history(source, &sha256(source))
    }

    #[test]
    fn same_value_compare_write_is_a_fresh_acknowledgement_generation() {
        let bytes = source(
            103,
            103,
            true,
            vec![json!({
                "record": "compare_write",
                "ordinal": 1,
                "before_value": 103,
                "after_value": 103,
                "pending_before": true,
                "pending_after": false,
            })],
        );
        let report = inspect(&bytes).unwrap();
        assert!(!report.final_pending);
        assert_eq!(report.compare_generation, 1);
        assert_eq!(report.writes.len(), 1);
        assert!(report.writes[0].same_value);
        assert!(report.writes[0].acknowledged_pending);
        assert_eq!(report.writes[0].register_generation, 1);
        assert_eq!(report.writes[0].operation_generation, 1);
    }

    #[test]
    fn equal_final_register_values_do_not_imply_equal_causal_state() {
        let untouched = source(103, 103, true, vec![]);
        let acknowledged = source(
            103,
            103,
            true,
            vec![json!({
                "record": "compare_write",
                "ordinal": 1,
                "before_value": 103,
                "after_value": 103,
                "pending_before": true,
                "pending_after": false,
            })],
        );
        let a = inspect(&untouched).unwrap();
        let b = inspect(&acknowledged).unwrap();
        assert_eq!(
            (a.final_count, a.final_compare),
            (b.final_count, b.final_compare)
        );
        assert_ne!(a.final_pending, b.final_pending);
        assert_ne!(a.compare_generation, b.compare_generation);
    }

    #[test]
    fn count_write_cannot_masquerade_as_timer_acknowledgement() {
        let forged = source(
            103,
            103,
            true,
            vec![json!({
                "record": "count_write",
                "ordinal": 1,
                "before_value": 103,
                "after_value": 500,
                "pending_before": true,
                "pending_after": false,
            })],
        );
        assert!(inspect(&forged).is_err());
    }

    #[test]
    fn assertion_identity_is_observed_not_inferred_from_equal_values() {
        let bytes = source(
            100,
            103,
            false,
            vec![json!({
                "record": "timer_assert",
                "ordinal": 1,
                "count": 100,
                "compare": 103,
                "pending_before": false,
                "pending_after": true,
            })],
        );
        let report = inspect(&bytes).unwrap();
        assert!(report.final_pending);
        assert_eq!(report.assertions.len(), 1);
        assert_eq!(report.assertions[0].assertion_generation, 1);
        assert_eq!(report.assertions[0].count_generation, 0);
        assert_eq!(report.assertions[0].compare_generation, 0);
        assert!(!report.exact_count_rewrite_timing_certified);
    }

    #[test]
    fn repeated_assert_without_an_acknowledgement_is_rejected() {
        let forged = source(
            1,
            1,
            false,
            vec![
                json!({
                    "record": "timer_assert",
                    "ordinal": 1,
                    "count": 1,
                    "compare": 1,
                    "pending_before": false,
                    "pending_after": true,
                }),
                json!({
                    "record": "timer_assert",
                    "ordinal": 2,
                    "count": 1,
                    "compare": 1,
                    "pending_before": true,
                    "pending_after": true,
                }),
            ],
        );
        assert!(inspect(&forged).is_err());
    }

    #[test]
    fn stale_before_state_and_reordered_ordinals_fail_closed() {
        let stale = source(
            10,
            20,
            false,
            vec![json!({
                "record": "compare_write",
                "ordinal": 1,
                "before_value": 21,
                "after_value": 20,
                "pending_before": false,
                "pending_after": false,
            })],
        );
        assert!(inspect(&stale).is_err());

        let reordered = source(
            10,
            20,
            false,
            vec![json!({
                "record": "count_write",
                "ordinal": 2,
                "before_value": 10,
                "after_value": 11,
                "pending_before": false,
                "pending_after": false,
            })],
        );
        assert!(inspect(&reordered).is_err());
    }

    #[test]
    fn deleted_or_changed_source_cannot_reuse_the_original_receipt() {
        let original = source(
            103,
            103,
            true,
            vec![json!({
                "record": "compare_write",
                "ordinal": 1,
                "before_value": 103,
                "after_value": 103,
                "pending_before": true,
                "pending_after": false,
            })],
        );
        let expected = sha256(&original);
        let deleted = source(103, 103, true, vec![]);
        assert!(inspect_timer_interrupt_history(&deleted, &expected).is_err());
    }

    #[test]
    fn complete_report_replay_rejects_tampering_and_keeps_proof_flags_open() {
        let bytes = source(
            7,
            9,
            false,
            vec![
                json!({
                    "record": "count_write",
                    "ordinal": 1,
                    "before_value": 7,
                    "after_value": 8,
                    "pending_before": false,
                    "pending_after": false,
                }),
                json!({
                    "record": "compare_write",
                    "ordinal": 2,
                    "before_value": 9,
                    "after_value": 9,
                    "pending_before": false,
                    "pending_after": false,
                }),
            ],
        );
        let digest = sha256(&bytes);
        let report = inspect_timer_interrupt_history(&bytes, &digest).unwrap();
        verify_timer_interrupt_report(&report, &bytes, &digest).unwrap();

        let mut forged = report.clone();
        forged.compare_generation += 1;
        assert!(verify_timer_interrupt_report(&forged, &bytes, &digest).is_err());
        assert!(!report.sensor_coverage_certified);
        assert!(!report.exact_count_rewrite_timing_certified);
        assert!(!report.interrupt_gate_chronology_certified);
        assert!(!report.save_restore_reset_chronology_certified);
        assert!(!report.handler_lifetime_certified);
        assert!(!report.whole_rom_roots_certified);
        assert!(!report.native_complete);
    }
}
