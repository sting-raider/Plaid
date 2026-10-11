//! Fail-closed reset/HW2/NMI producer and delivery identity replay.
//!
//! This module deliberately does not choose a repeated-reset hardware policy.
//! Exact pinned references disagree on whether pending reset-related NMI events
//! accumulate or are replaced. Production therefore preserves explicit observed
//! generations and one-shot consumption instead of inferring identity from a
//! pending bit, event type, schedule value, PC, or payload equality.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResetDeliveryKind {
    Hw2,
    Nmi,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ResetProducerRecord {
    Request {
        ordinal: u64,
        request_generation: u64,
    },
    Produce {
        ordinal: u64,
        event_generation: u64,
        request_generation: u64,
        delivery_kind: ResetDeliveryKind,
        schedule_value: u64,
    },
    ImportUnknown {
        ordinal: u64,
        event_generation: u64,
        delivery_kind: ResetDeliveryKind,
        schedule_value: u64,
    },
    Supersede {
        ordinal: u64,
        event_generation: u64,
        replacement_event_generation: u64,
    },
    Deliver {
        ordinal: u64,
        event_generation: u64,
        delivery_kind: ResetDeliveryKind,
    },
}

impl ResetProducerRecord {
    fn ordinal(&self) -> u64 {
        match self {
            Self::Request { ordinal, .. }
            | Self::Produce { ordinal, .. }
            | Self::ImportUnknown { ordinal, .. }
            | Self::Supersede { ordinal, .. }
            | Self::Deliver { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResetProducerHistory {
    /// SHA-256 of the externally supplied complete capture for this replay.
    ///
    /// This binds event generations to one source namespace. The hash is not a
    /// substitute for independently proving that the capture source is complete.
    pub capture_sha256: String,
    pub records: Vec<ResetProducerRecord>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResetDeliveryReceipt {
    pub deliver_ordinal: u64,
    pub event_generation: u64,
    pub delivery_kind: ResetDeliveryKind,
    pub schedule_value: u64,
    pub request_generation: Option<u64>,
    pub producer_identity_certified: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResetSupersessionReceipt {
    pub supersede_ordinal: u64,
    pub event_generation: u64,
    pub replacement_event_generation: u64,
    pub delivery_kind: ResetDeliveryKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ActiveResetEvent {
    pub event_generation: u64,
    pub delivery_kind: ResetDeliveryKind,
    pub schedule_value: u64,
    pub request_generation: Option<u64>,
    pub producer_identity_certified: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResetProducerReport {
    pub capture_sha256: String,
    pub requests: u64,
    pub produced_events: u64,
    pub imported_unknown_events: u64,
    pub deliveries: Vec<ResetDeliveryReceipt>,
    pub supersessions: Vec<ResetSupersessionReceipt>,
    pub active_events: Vec<ActiveResetEvent>,
    pub repeated_reset_policy_certified: bool,
    pub reset_census_certified: bool,
    pub save_restore_identity_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum EventStatus {
    Active,
    Delivered,
    Superseded,
}

#[derive(Debug, Clone, Copy)]
struct EventState {
    delivery_kind: ResetDeliveryKind,
    schedule_value: u64,
    request_generation: Option<u64>,
    status: EventStatus,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn require_generation(value: u64, label: &str) -> Result<(), String> {
    require(value != 0, &format!("zero {label} generation"))
}

/// Replay one source-bound observed reset producer history.
///
/// The replay is intentionally policy-neutral. Multiple active events of the same
/// kind and schedule value are legal and remain distinct generations. A capture
/// that observed replacement/coalescing can record an explicit `Supersede` edge.
/// Neither shape is promoted to universal hardware behavior.
///
/// `ImportUnknown` exists for a pending event whose causal request ancestry is not
/// available in the supplied source namespace. It can be consumed once, but its
/// delivery receipt remains producer-UNKNOWN; no later value equality can attach
/// a request generation to it.
pub fn verify_reset_producer_history(
    history: &ResetProducerHistory,
) -> Result<ResetProducerReport, String> {
    require(
        valid_sha256(&history.capture_sha256),
        "invalid capture SHA-256",
    )?;
    require(!history.records.is_empty(), "empty reset producer history")?;

    let mut requests = BTreeMap::<u64, u64>::new();
    let mut events = BTreeMap::<u64, EventState>::new();
    let mut produced_events = 0_u64;
    let mut imported_unknown_events = 0_u64;
    let mut deliveries = Vec::new();
    let mut supersessions = Vec::new();

    for (index, record) in history.records.iter().enumerate() {
        let expected = u64::try_from(index)
            .map_err(|_| "reset producer history index exceeds u64".to_string())?
            .checked_add(1)
            .ok_or_else(|| "reset producer history ordinal overflow".to_string())?;
        require(
            record.ordinal() == expected,
            "reset producer history ordinal gap/reorder",
        )?;

        match record {
            ResetProducerRecord::Request {
                ordinal,
                request_generation,
            } => {
                require_generation(*request_generation, "request")?;
                require(
                    requests.insert(*request_generation, *ordinal).is_none(),
                    "reused reset request generation",
                )?;
            }
            ResetProducerRecord::Produce {
                event_generation,
                request_generation,
                delivery_kind,
                schedule_value,
                ..
            } => {
                require_generation(*event_generation, "event")?;
                require_generation(*request_generation, "request")?;
                require(
                    requests.contains_key(request_generation),
                    "reset event references unknown request generation",
                )?;
                require(
                    !events.contains_key(event_generation),
                    "reused reset event generation",
                )?;
                events.insert(
                    *event_generation,
                    EventState {
                        delivery_kind: *delivery_kind,
                        schedule_value: *schedule_value,
                        request_generation: Some(*request_generation),
                        status: EventStatus::Active,
                    },
                );
                produced_events = produced_events
                    .checked_add(1)
                    .ok_or_else(|| "produced reset event count overflow".to_string())?;
            }
            ResetProducerRecord::ImportUnknown {
                event_generation,
                delivery_kind,
                schedule_value,
                ..
            } => {
                require_generation(*event_generation, "event")?;
                require(
                    !events.contains_key(event_generation),
                    "reused reset event generation",
                )?;
                events.insert(
                    *event_generation,
                    EventState {
                        delivery_kind: *delivery_kind,
                        schedule_value: *schedule_value,
                        request_generation: None,
                        status: EventStatus::Active,
                    },
                );
                imported_unknown_events = imported_unknown_events
                    .checked_add(1)
                    .ok_or_else(|| "imported reset event count overflow".to_string())?;
            }
            ResetProducerRecord::Supersede {
                ordinal,
                event_generation,
                replacement_event_generation,
            } => {
                require_generation(*event_generation, "event")?;
                require_generation(*replacement_event_generation, "replacement event")?;
                require(
                    event_generation != replacement_event_generation,
                    "reset event cannot supersede itself",
                )?;

                let old = events
                    .get(event_generation)
                    .copied()
                    .ok_or_else(|| "superseded reset event does not exist".to_string())?;
                let replacement = events
                    .get(replacement_event_generation)
                    .copied()
                    .ok_or_else(|| "replacement reset event does not exist".to_string())?;
                require(
                    old.status == EventStatus::Active,
                    "superseded reset event is not active",
                )?;
                require(
                    replacement.status == EventStatus::Active,
                    "replacement reset event is not active",
                )?;
                require(
                    old.delivery_kind == replacement.delivery_kind,
                    "reset supersession changes delivery kind",
                )?;

                events
                    .get_mut(event_generation)
                    .ok_or_else(|| "superseded reset event disappeared".to_string())?
                    .status = EventStatus::Superseded;
                supersessions.push(ResetSupersessionReceipt {
                    supersede_ordinal: *ordinal,
                    event_generation: *event_generation,
                    replacement_event_generation: *replacement_event_generation,
                    delivery_kind: old.delivery_kind,
                });
            }
            ResetProducerRecord::Deliver {
                ordinal,
                event_generation,
                delivery_kind,
            } => {
                require_generation(*event_generation, "event")?;
                let event = events
                    .get(event_generation)
                    .copied()
                    .ok_or_else(|| "delivered reset event does not exist".to_string())?;
                require(
                    event.status == EventStatus::Active,
                    "reset event delivery is stale, superseded, or replayed",
                )?;
                require(
                    event.delivery_kind == *delivery_kind,
                    "reset event delivery kind mismatch",
                )?;

                events
                    .get_mut(event_generation)
                    .ok_or_else(|| "delivered reset event disappeared".to_string())?
                    .status = EventStatus::Delivered;
                deliveries.push(ResetDeliveryReceipt {
                    deliver_ordinal: *ordinal,
                    event_generation: *event_generation,
                    delivery_kind: *delivery_kind,
                    schedule_value: event.schedule_value,
                    request_generation: event.request_generation,
                    producer_identity_certified: event.request_generation.is_some(),
                });
            }
        }
    }

    let active_events = events
        .iter()
        .filter_map(|(generation, event)| {
            (event.status == EventStatus::Active).then_some(ActiveResetEvent {
                event_generation: *generation,
                delivery_kind: event.delivery_kind,
                schedule_value: event.schedule_value,
                request_generation: event.request_generation,
                producer_identity_certified: event.request_generation.is_some(),
            })
        })
        .collect();

    let request_count = u64::try_from(requests.len())
        .map_err(|_| "too many reset request generations".to_string())?;

    Ok(ResetProducerReport {
        capture_sha256: history.capture_sha256.clone(),
        requests: request_count,
        produced_events,
        imported_unknown_events,
        deliveries,
        supersessions,
        active_events,
        repeated_reset_policy_certified: false,
        reset_census_certified: false,
        save_restore_identity_certified: false,
        native_complete: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const HASH: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    fn history(records: Vec<ResetProducerRecord>) -> ResetProducerHistory {
        ResetProducerHistory {
            capture_sha256: HASH.into(),
            records,
        }
    }

    fn request(ordinal: u64, request_generation: u64) -> ResetProducerRecord {
        ResetProducerRecord::Request {
            ordinal,
            request_generation,
        }
    }

    fn produce(
        ordinal: u64,
        event_generation: u64,
        request_generation: u64,
        delivery_kind: ResetDeliveryKind,
        schedule_value: u64,
    ) -> ResetProducerRecord {
        ResetProducerRecord::Produce {
            ordinal,
            event_generation,
            request_generation,
            delivery_kind,
            schedule_value,
        }
    }

    fn deliver(
        ordinal: u64,
        event_generation: u64,
        delivery_kind: ResetDeliveryKind,
    ) -> ResetProducerRecord {
        ResetProducerRecord::Deliver {
            ordinal,
            event_generation,
            delivery_kind,
        }
    }

    #[test]
    fn equal_schedule_values_keep_distinct_accumulated_generations() {
        let report = verify_reset_producer_history(&history(vec![
            request(1, 1),
            produce(2, 10, 1, ResetDeliveryKind::Hw2, 100),
            produce(3, 11, 1, ResetDeliveryKind::Nmi, 50_000_100),
            request(4, 2),
            produce(5, 12, 2, ResetDeliveryKind::Hw2, 100),
            produce(6, 13, 2, ResetDeliveryKind::Nmi, 50_000_100),
            deliver(7, 10, ResetDeliveryKind::Hw2),
            deliver(8, 12, ResetDeliveryKind::Hw2),
            deliver(9, 11, ResetDeliveryKind::Nmi),
            deliver(10, 13, ResetDeliveryKind::Nmi),
        ]))
        .unwrap();

        assert_eq!(report.requests, 2);
        assert_eq!(report.produced_events, 4);
        assert_eq!(report.deliveries.len(), 4);
        assert_eq!(report.deliveries[0].schedule_value, 100);
        assert_eq!(report.deliveries[1].schedule_value, 100);
        assert_eq!(report.deliveries[0].request_generation, Some(1));
        assert_eq!(report.deliveries[1].request_generation, Some(2));
        assert!(report.active_events.is_empty());
        assert!(!report.repeated_reset_policy_certified);
        assert!(!report.reset_census_certified);
        assert!(!report.save_restore_identity_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn explicit_supersession_models_coalescing_without_making_it_hardware_truth() {
        let report = verify_reset_producer_history(&history(vec![
            request(1, 1),
            produce(2, 10, 1, ResetDeliveryKind::Nmi, 200),
            request(3, 2),
            produce(4, 11, 2, ResetDeliveryKind::Nmi, 200),
            ResetProducerRecord::Supersede {
                ordinal: 5,
                event_generation: 10,
                replacement_event_generation: 11,
            },
            deliver(6, 11, ResetDeliveryKind::Nmi),
        ]))
        .unwrap();

        assert_eq!(report.supersessions.len(), 1);
        assert_eq!(report.supersessions[0].event_generation, 10);
        assert_eq!(report.supersessions[0].replacement_event_generation, 11);
        assert_eq!(report.deliveries.len(), 1);
        assert_eq!(report.deliveries[0].request_generation, Some(2));
        assert!(!report.repeated_reset_policy_certified);
    }

    #[test]
    fn imported_pending_event_can_deliver_but_keeps_request_ancestry_unknown() {
        let report = verify_reset_producer_history(&history(vec![
            ResetProducerRecord::ImportUnknown {
                ordinal: 1,
                event_generation: 9,
                delivery_kind: ResetDeliveryKind::Nmi,
                schedule_value: 77,
            },
            deliver(2, 9, ResetDeliveryKind::Nmi),
        ]))
        .unwrap();

        assert_eq!(report.imported_unknown_events, 1);
        assert_eq!(report.deliveries.len(), 1);
        assert_eq!(report.deliveries[0].request_generation, None);
        assert!(!report.deliveries[0].producer_identity_certified);
    }

    #[test]
    fn replay_and_superseded_delivery_are_rejected() {
        let replay = history(vec![
            request(1, 1),
            produce(2, 10, 1, ResetDeliveryKind::Nmi, 20),
            deliver(3, 10, ResetDeliveryKind::Nmi),
            deliver(4, 10, ResetDeliveryKind::Nmi),
        ]);
        assert!(verify_reset_producer_history(&replay).is_err());

        let stale = history(vec![
            request(1, 1),
            produce(2, 10, 1, ResetDeliveryKind::Nmi, 20),
            request(3, 2),
            produce(4, 11, 2, ResetDeliveryKind::Nmi, 20),
            ResetProducerRecord::Supersede {
                ordinal: 5,
                event_generation: 10,
                replacement_event_generation: 11,
            },
            deliver(6, 10, ResetDeliveryKind::Nmi),
        ]);
        assert!(verify_reset_producer_history(&stale).is_err());
    }

    #[test]
    fn fabricated_request_and_generation_reuse_are_rejected() {
        let fabricated = history(vec![produce(1, 10, 99, ResetDeliveryKind::Nmi, 20)]);
        assert!(verify_reset_producer_history(&fabricated).is_err());

        let duplicate_request = history(vec![request(1, 1), request(2, 1)]);
        assert!(verify_reset_producer_history(&duplicate_request).is_err());

        let duplicate_event = history(vec![
            request(1, 1),
            produce(2, 10, 1, ResetDeliveryKind::Hw2, 1),
            produce(3, 10, 1, ResetDeliveryKind::Nmi, 2),
        ]);
        assert!(verify_reset_producer_history(&duplicate_event).is_err());
    }

    #[test]
    fn supersession_requires_two_live_same_kind_events() {
        let wrong_kind = history(vec![
            request(1, 1),
            produce(2, 10, 1, ResetDeliveryKind::Hw2, 1),
            produce(3, 11, 1, ResetDeliveryKind::Nmi, 1),
            ResetProducerRecord::Supersede {
                ordinal: 4,
                event_generation: 10,
                replacement_event_generation: 11,
            },
        ]);
        assert!(verify_reset_producer_history(&wrong_kind).is_err());

        let consumed_replacement = history(vec![
            request(1, 1),
            produce(2, 10, 1, ResetDeliveryKind::Nmi, 1),
            produce(3, 11, 1, ResetDeliveryKind::Nmi, 1),
            deliver(4, 11, ResetDeliveryKind::Nmi),
            ResetProducerRecord::Supersede {
                ordinal: 5,
                event_generation: 10,
                replacement_event_generation: 11,
            },
        ]);
        assert!(verify_reset_producer_history(&consumed_replacement).is_err());

        let self_supersede = history(vec![
            request(1, 1),
            produce(2, 10, 1, ResetDeliveryKind::Nmi, 1),
            ResetProducerRecord::Supersede {
                ordinal: 3,
                event_generation: 10,
                replacement_event_generation: 10,
            },
        ]);
        assert!(verify_reset_producer_history(&self_supersede).is_err());
    }

    #[test]
    fn deleted_reordered_wrong_kind_and_zero_generations_fail_closed() {
        let deleted = history(vec![request(1, 1), request(3, 2)]);
        assert!(verify_reset_producer_history(&deleted).is_err());

        let reordered = history(vec![request(2, 1), request(1, 2)]);
        assert!(verify_reset_producer_history(&reordered).is_err());

        let wrong_kind = history(vec![
            request(1, 1),
            produce(2, 10, 1, ResetDeliveryKind::Hw2, 1),
            deliver(3, 10, ResetDeliveryKind::Nmi),
        ]);
        assert!(verify_reset_producer_history(&wrong_kind).is_err());

        let zero_request = history(vec![request(1, 0)]);
        assert!(verify_reset_producer_history(&zero_request).is_err());

        let zero_event = history(vec![
            request(1, 1),
            produce(2, 0, 1, ResetDeliveryKind::Nmi, 1),
        ]);
        assert!(verify_reset_producer_history(&zero_event).is_err());
    }

    #[test]
    fn malformed_capture_identity_is_rejected() {
        let malformed = ResetProducerHistory {
            capture_sha256: "equal-values-are-not-event-identity".into(),
            records: vec![request(1, 1)],
        };
        assert!(verify_reset_producer_history(&malformed).is_err());
    }
}
