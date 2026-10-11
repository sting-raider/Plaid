//! Source-bound compiler-time replay of captured TLB mapping/context operations.
//! Mapping-operation generations, translation-context generations and cache/executable
//! lifetimes remain deliberately distinct.
use crate::{program::GuestVirtualAddr, rom::sha256};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-tlb-history-v0";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    Mtc0EntryHiAttempt {
        ordinal: u64,
        pc: GuestVirtualAddr,
        cop0_usable: bool,
        entry_hi_before: u64,
        value: u64,
    },
    TlbwiAttempt {
        ordinal: u64,
        pc: GuestVirtualAddr,
        cop0_usable: bool,
        index: u8,
        entry_hi_before: u64,
        staged_entry_digest: String,
        slot_before_digest: Option<String>,
    },
    TlbrAttempt {
        ordinal: u64,
        pc: GuestVirtualAddr,
        cop0_usable: bool,
        index: u8,
        entry_hi_before: u64,
        selected_entry_hi: Option<u64>,
        selected_entry_digest: Option<String>,
    },
    TlbpAttempt {
        ordinal: u64,
        pc: GuestVirtualAddr,
        cop0_usable: bool,
        entry_hi_before: u64,
    },
    MappingWrite {
        ordinal: u64,
        instruction_ordinal: u64,
        slot: u8,
        entry_digest: String,
    },
    ContextWrite {
        ordinal: u64,
        instruction_ordinal: u64,
        source: ContextWriteSource,
        entry_hi: u64,
    },
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::Mtc0EntryHiAttempt { ordinal, .. }
            | Self::TlbwiAttempt { ordinal, .. }
            | Self::TlbrAttempt { ordinal, .. }
            | Self::TlbpAttempt { ordinal, .. }
            | Self::MappingWrite { ordinal, .. }
            | Self::ContextWrite { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ContextWriteSource {
    Mtc0EntryHi,
    Tlbr,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MappingGeneration {
    pub event_ordinal: u64,
    pub instruction_ordinal: u64,
    pub slot: u8,
    pub entry_digest: String,
    pub content_changed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TranslationContextGeneration {
    pub event_ordinal: u64,
    pub instruction_ordinal: u64,
    pub source: ContextWriteSource,
    pub entry_hi: u64,
    pub content_changed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbHistoryReport {
    pub format: String,
    pub source_sha256: String,
    pub instruction_attempts: usize,
    pub probe_attempts: usize,
    pub executed_probe_operations: usize,
    pub mapping_generations: Vec<MappingGeneration>,
    pub context_generations: Vec<TranslationContextGeneration>,
    pub complete_source_bound: bool,
    pub sensor_completeness_certified: bool,
    pub executable_lifetime_certified: bool,
    pub cache_lifetime_certified: bool,
    pub native_complete: bool,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok {
        Ok(())
    } else {
        Err(message.into())
    }
}

fn valid_digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn validate_pc(pc: GuestVirtualAddr) -> Result<(), String> {
    require(pc.0.is_multiple_of(4), "unaligned TLB instruction PC")
}

fn bind_entry_hi(current: &mut Option<u64>, observed: u64) -> Result<(), String> {
    if let Some(expected) = *current {
        require(expected == observed, "TLB EntryHi continuity mismatch")?;
    } else {
        *current = Some(observed);
    }
    Ok(())
}

fn reject_effect_for(events: &[Event], index: usize, instruction_ordinal: u64) -> Result<(), String> {
    if let Some(next) = events.get(index + 1) {
        match next {
            Event::MappingWrite {
                instruction_ordinal: owner,
                ..
            }
            | Event::ContextWrite {
                instruction_ordinal: owner,
                ..
            } if *owner == instruction_ordinal => {
                return Err("failed TLB attempt produced a mutation boundary".into());
            }
            _ => {}
        }
    }
    Ok(())
}

/// Verify a finite captured TLB history against an externally trusted complete-source receipt.
///
/// A successful report authenticates only the supplied event stream. It does not prove that the
/// underlying sensor observed every CPU/TLB mutation or that any mapping/cache lifetime is closed.
pub fn inspect_tlb_history(source: &[u8], expected_sha256: &str) -> Result<TlbHistoryReport, String> {
    let digest = sha256(source);
    require(digest == expected_sha256, "TLB source receipt mismatch")?;
    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(history.format == FORMAT, "unsupported TLB history format")?;

    for (index, event) in history.events.iter().enumerate() {
        require(
            event.ordinal() == index as u64 + 1,
            "noncontiguous TLB history ordinals",
        )?;
    }

    let mut entry_hi = None;
    let mut slots = vec![None::<String>; 32];
    let mut instruction_attempts = 0usize;
    let mut probe_attempts = 0usize;
    let mut executed_probe_operations = 0usize;
    let mut mapping_generations = Vec::new();
    let mut context_generations = Vec::new();
    let mut index = 0usize;

    while index < history.events.len() {
        match &history.events[index] {
            Event::Mtc0EntryHiAttempt {
                ordinal,
                pc,
                cop0_usable,
                entry_hi_before,
                value,
            } => {
                instruction_attempts += 1;
                validate_pc(*pc)?;
                bind_entry_hi(&mut entry_hi, *entry_hi_before)?;
                if !cop0_usable {
                    reject_effect_for(&history.events, index, *ordinal)?;
                    index += 1;
                    continue;
                }
                let Some(Event::ContextWrite {
                    ordinal: effect_ordinal,
                    instruction_ordinal,
                    source: ContextWriteSource::Mtc0EntryHi,
                    entry_hi: written,
                }) = history.events.get(index + 1)
                else {
                    return Err("successful MTC0 EntryHi missing context-write boundary".into());
                };
                require(
                    *instruction_ordinal == *ordinal && *written == *value,
                    "MTC0 EntryHi context-write mismatch",
                )?;
                context_generations.push(TranslationContextGeneration {
                    event_ordinal: *effect_ordinal,
                    instruction_ordinal: *ordinal,
                    source: ContextWriteSource::Mtc0EntryHi,
                    entry_hi: *written,
                    content_changed: *written != *entry_hi_before,
                });
                entry_hi = Some(*written);
                index += 2;
            }
            Event::TlbwiAttempt {
                ordinal,
                pc,
                cop0_usable,
                index: slot,
                entry_hi_before,
                staged_entry_digest,
                slot_before_digest,
            } => {
                instruction_attempts += 1;
                validate_pc(*pc)?;
                bind_entry_hi(&mut entry_hi, *entry_hi_before)?;
                require(
                    valid_digest(staged_entry_digest),
                    "invalid staged TLB entry digest",
                )?;
                if !cop0_usable {
                    require(
                        slot_before_digest.is_none(),
                        "failed TLBWI supplied a selected-slot snapshot",
                    )?;
                    reject_effect_for(&history.events, index, *ordinal)?;
                    index += 1;
                    continue;
                }
                if *slot >= 32 {
                    require(
                        slot_before_digest.is_none(),
                        "out-of-range TLBWI supplied a selected-slot snapshot",
                    )?;
                    reject_effect_for(&history.events, index, *ordinal)?;
                    index += 1;
                    continue;
                }
                let before = slot_before_digest
                    .as_ref()
                    .ok_or("successful TLBWI missing selected-slot snapshot")?;
                require(valid_digest(before), "invalid prior TLB entry digest")?;
                if let Some(known) = &slots[*slot as usize] {
                    require(known == before, "TLB slot continuity mismatch")?;
                }
                slots[*slot as usize] = Some(before.clone());
                let Some(Event::MappingWrite {
                    ordinal: effect_ordinal,
                    instruction_ordinal,
                    slot: written_slot,
                    entry_digest,
                }) = history.events.get(index + 1)
                else {
                    return Err("successful TLBWI missing mapping-write boundary".into());
                };
                require(
                    *instruction_ordinal == *ordinal
                        && *written_slot == *slot
                        && entry_digest == staged_entry_digest
                        && valid_digest(entry_digest),
                    "TLBWI mapping-write mismatch",
                )?;
                mapping_generations.push(MappingGeneration {
                    event_ordinal: *effect_ordinal,
                    instruction_ordinal: *ordinal,
                    slot: *slot,
                    entry_digest: entry_digest.clone(),
                    content_changed: before != entry_digest,
                });
                slots[*slot as usize] = Some(entry_digest.clone());
                index += 2;
            }
            Event::TlbrAttempt {
                ordinal,
                pc,
                cop0_usable,
                index: slot,
                entry_hi_before,
                selected_entry_hi,
                selected_entry_digest,
            } => {
                instruction_attempts += 1;
                validate_pc(*pc)?;
                bind_entry_hi(&mut entry_hi, *entry_hi_before)?;
                if !cop0_usable || *slot >= 32 {
                    require(
                        selected_entry_hi.is_none() && selected_entry_digest.is_none(),
                        "failed TLBR supplied selected-entry state",
                    )?;
                    reject_effect_for(&history.events, index, *ordinal)?;
                    index += 1;
                    continue;
                }
                let selected_hi = selected_entry_hi
                    .ok_or("successful TLBR missing selected EntryHi")?;
                let selected_digest = selected_entry_digest
                    .as_deref()
                    .ok_or("successful TLBR missing selected entry digest")?;
                require(
                    valid_digest(selected_digest),
                    "invalid selected TLB entry digest",
                )?;
                if let Some(known) = &slots[*slot as usize] {
                    require(
                        known == selected_digest,
                        "TLBR selected-slot continuity mismatch",
                    )?;
                }
                slots[*slot as usize] = Some(selected_digest.to_string());
                let Some(Event::ContextWrite {
                    ordinal: effect_ordinal,
                    instruction_ordinal,
                    source: ContextWriteSource::Tlbr,
                    entry_hi: written,
                }) = history.events.get(index + 1)
                else {
                    return Err("successful TLBR missing context-write boundary".into());
                };
                require(
                    *instruction_ordinal == *ordinal && *written == selected_hi,
                    "TLBR context-write mismatch",
                )?;
                context_generations.push(TranslationContextGeneration {
                    event_ordinal: *effect_ordinal,
                    instruction_ordinal: *ordinal,
                    source: ContextWriteSource::Tlbr,
                    entry_hi: *written,
                    content_changed: *written != *entry_hi_before,
                });
                entry_hi = Some(*written);
                index += 2;
            }
            Event::TlbpAttempt {
                ordinal,
                pc,
                cop0_usable,
                entry_hi_before,
            } => {
                instruction_attempts += 1;
                probe_attempts += 1;
                if *cop0_usable {
                    executed_probe_operations += 1;
                }
                validate_pc(*pc)?;
                bind_entry_hi(&mut entry_hi, *entry_hi_before)?;
                reject_effect_for(&history.events, index, *ordinal)?;
                index += 1;
            }
            Event::MappingWrite { .. } | Event::ContextWrite { .. } => {
                return Err("orphan TLB mutation boundary".into());
            }
        }
    }

    Ok(TlbHistoryReport {
        format: history.format,
        source_sha256: digest,
        instruction_attempts,
        probe_attempts,
        executed_probe_operations,
        mapping_generations,
        context_generations,
        complete_source_bound: true,
        sensor_completeness_certified: false,
        executable_lifetime_certified: false,
        cache_lifetime_certified: false,
        native_complete: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    const A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const B: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

    fn inspect(value: Value) -> Result<TlbHistoryReport, String> {
        let bytes = serde_json::to_vec(&value).unwrap();
        let digest = crate::rom::sha256(&bytes);
        inspect_tlb_history(&bytes, &digest)
    }

    fn base_events() -> Vec<Value> {
        vec![
            json!({"kind":"mtc0_entry_hi_attempt","ordinal":1,"pc":2147483648u64,"cop0_usable":true,"entry_hi_before":17u64,"value":17u64}),
            json!({"kind":"context_write","ordinal":2,"instruction_ordinal":1,"source":"mtc0_entry_hi","entry_hi":17u64}),
            json!({"kind":"tlbwi_attempt","ordinal":3,"pc":2147483652u64,"cop0_usable":true,"index":5,"entry_hi_before":17u64,"staged_entry_digest":A,"slot_before_digest":A}),
            json!({"kind":"mapping_write","ordinal":4,"instruction_ordinal":3,"slot":5,"entry_digest":A}),
            json!({"kind":"tlbr_attempt","ordinal":5,"pc":2147483656u64,"cop0_usable":true,"index":5,"entry_hi_before":17u64,"selected_entry_hi":17u64,"selected_entry_digest":A}),
            json!({"kind":"context_write","ordinal":6,"instruction_ordinal":5,"source":"tlbr","entry_hi":17u64}),
            json!({"kind":"tlbp_attempt","ordinal":7,"pc":2147483660u64,"cop0_usable":true,"entry_hi_before":17u64}),
        ]
    }

    #[test]
    fn preserves_same_value_mapping_and_context_generations() {
        let report = inspect(json!({"format":FORMAT,"events":base_events()})).unwrap();
        assert_eq!(report.instruction_attempts, 4);
        assert_eq!(report.probe_attempts, 1);
        assert_eq!(report.executed_probe_operations, 1);
        assert_eq!(report.mapping_generations.len(), 1);
        assert!(!report.mapping_generations[0].content_changed);
        assert_eq!(report.context_generations.len(), 2);
        assert!(report.context_generations.iter().all(|g| !g.content_changed));
        assert!(!report.sensor_completeness_certified);
        assert!(!report.executable_lifetime_certified);
        assert!(!report.cache_lifetime_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn keeps_equal_payload_slots_distinct() {
        let mut events = base_events();
        events.truncate(4);
        events.push(json!({"kind":"tlbwi_attempt","ordinal":5,"pc":2147483656u64,"cop0_usable":true,"index":7,"entry_hi_before":17u64,"staged_entry_digest":A,"slot_before_digest":B}));
        events.push(json!({"kind":"mapping_write","ordinal":6,"instruction_ordinal":5,"slot":7,"entry_digest":A}));
        let report = inspect(json!({"format":FORMAT,"events":events})).unwrap();
        assert_eq!(report.mapping_generations[0].slot, 5);
        assert_eq!(report.mapping_generations[1].slot, 7);
        assert!(report.mapping_generations[1].content_changed);
    }

    #[test]
    fn rejects_failed_attempt_that_mints_generation() {
        let value = json!({"format":FORMAT,"events":[
            {"kind":"tlbwi_attempt","ordinal":1,"pc":2147483648u64,"cop0_usable":true,"index":63,"entry_hi_before":0u64,"staged_entry_digest":A,"slot_before_digest":null},
            {"kind":"mapping_write","ordinal":2,"instruction_ordinal":1,"slot":5,"entry_digest":A}
        ]});
        assert!(inspect(value)
            .unwrap_err()
            .contains("failed TLB attempt produced a mutation boundary"));
    }

    #[test]
    fn rejects_missing_same_value_boundary() {
        let value = json!({"format":FORMAT,"events":[
            {"kind":"tlbwi_attempt","ordinal":1,"pc":2147483648u64,"cop0_usable":true,"index":5,"entry_hi_before":0u64,"staged_entry_digest":A,"slot_before_digest":A}
        ]});
        assert!(inspect(value)
            .unwrap_err()
            .contains("successful TLBWI missing mapping-write boundary"));
    }

    #[test]
    fn rejects_tlbp_context_generation() {
        let value = json!({"format":FORMAT,"events":[
            {"kind":"tlbp_attempt","ordinal":1,"pc":2147483648u64,"cop0_usable":true,"entry_hi_before":0u64},
            {"kind":"context_write","ordinal":2,"instruction_ordinal":1,"source":"tlbr","entry_hi":0u64}
        ]});
        assert!(inspect(value)
            .unwrap_err()
            .contains("failed TLB attempt produced a mutation boundary"));
    }

    #[test]
    fn rejects_entry_hi_and_slot_continuity_forgery() {
        let mut events = base_events();
        events.push(json!({"kind":"tlbwi_attempt","ordinal":8,"pc":2147483664u64,"cop0_usable":true,"index":5,"entry_hi_before":34u64,"staged_entry_digest":B,"slot_before_digest":B}));
        events.push(json!({"kind":"mapping_write","ordinal":9,"instruction_ordinal":8,"slot":5,"entry_digest":B}));
        assert!(inspect(json!({"format":FORMAT,"events":events}))
            .unwrap_err()
            .contains("TLB EntryHi continuity mismatch"));

        let mut events = base_events();
        events.push(json!({"kind":"tlbwi_attempt","ordinal":8,"pc":2147483664u64,"cop0_usable":true,"index":5,"entry_hi_before":17u64,"staged_entry_digest":B,"slot_before_digest":B}));
        events.push(json!({"kind":"mapping_write","ordinal":9,"instruction_ordinal":8,"slot":5,"entry_digest":B}));
        assert!(inspect(json!({"format":FORMAT,"events":events}))
            .unwrap_err()
            .contains("TLB slot continuity mismatch"));
    }

    #[test]
    fn rejects_wrong_tlbr_slot_identity_and_out_of_range_selection() {
        let value = json!({"format":FORMAT,"events":[
            {"kind":"tlbwi_attempt","ordinal":1,"pc":2147483648u64,"cop0_usable":true,"index":5,"entry_hi_before":0u64,"staged_entry_digest":A,"slot_before_digest":B},
            {"kind":"mapping_write","ordinal":2,"instruction_ordinal":1,"slot":5,"entry_digest":A},
            {"kind":"tlbr_attempt","ordinal":3,"pc":2147483652u64,"cop0_usable":true,"index":5,"entry_hi_before":0u64,"selected_entry_hi":0u64,"selected_entry_digest":B},
            {"kind":"context_write","ordinal":4,"instruction_ordinal":3,"source":"tlbr","entry_hi":0u64}
        ]});
        assert!(inspect(value)
            .unwrap_err()
            .contains("TLBR selected-slot continuity mismatch"));

        let value = json!({"format":FORMAT,"events":[
            {"kind":"tlbr_attempt","ordinal":1,"pc":2147483648u64,"cop0_usable":true,"index":63,"entry_hi_before":0u64,"selected_entry_hi":0u64,"selected_entry_digest":A}
        ]});
        assert!(inspect(value)
            .unwrap_err()
            .contains("failed TLBR supplied selected-entry state"));
    }

    #[test]
    fn rejects_receipt_and_ordinal_tampering() {
        let value = json!({"format":FORMAT,"events":base_events()});
        let bytes = serde_json::to_vec(&value).unwrap();
        assert!(inspect_tlb_history(&bytes, &"0".repeat(64))
            .unwrap_err()
            .contains("TLB source receipt mismatch"));

        let mut events = base_events();
        events[2]["ordinal"] = json!(9u64);
        assert!(inspect(json!({"format":FORMAT,"events":events}))
            .unwrap_err()
            .contains("noncontiguous TLB history ordinals"));
    }
}
