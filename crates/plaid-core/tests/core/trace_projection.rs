use plaid_core::{
    GuestAddr,
    merge::import_trace,
    program::{EvidenceRefs, GuestRange, PhysicalAddr, Region, RomIdentity, RomOffset},
    rom::sha256,
    trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
    trace_projection::verify_discovery_trace_projection,
};
use std::collections::BTreeSet;

fn trace() -> DiscoveryTrace {
    let words = vec![0x03e0_0008, 0];
    DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: RomIdentity {
                sha256: "0".repeat(64),
                size: 4096,
            },
            engine: "trace-projection-test".into(),
            revision: "r1".into(),
            capabilities: BTreeSet::new(),
        },
        events: vec![
            EventRecord {
                seq: 0,
                data: TraceEvent::CompileBegin {
                    unit: 7,
                    start: GuestAddr(0x8000_0000),
                    physical_start: None,
                    delay_slot_entry: false,
                },
            },
            EventRecord {
                seq: 1,
                data: TraceEvent::EntryInstalled {
                    unit: 7,
                    pc: GuestAddr(0x8000_0000),
                    register_mask: 0,
                },
            },
            EventRecord {
                seq: 2,
                data: TraceEvent::UnitCompiled {
                    unit: 7,
                    start: GuestAddr(0x8000_0000),
                    words: words.clone(),
                },
            },
            EventRecord {
                seq: 3,
                data: TraceEvent::EntryBytesVerified {
                    unit: 7,
                    pc: GuestAddr(0x8000_0000),
                    register_mask: 0,
                    words,
                },
            },
            EventRecord {
                seq: 4,
                data: TraceEvent::IndirectTargetObserved {
                    site: GuestAddr(0x8000_0000),
                    target: GuestAddr(0x8000_0000),
                    delay_slot_pc: Some(GuestAddr(0x8000_0004)),
                    source_unit: Some(7),
                },
            },
            EventRecord {
                seq: 5,
                data: TraceEvent::TargetLookup {
                    target: GuestAddr(0x8000_0000),
                    delay_slot_entry: false,
                },
            },
            EventRecord {
                seq: 6,
                data: TraceEvent::CpuWordStoreObserved {
                    site: GuestAddr(0x8000_0000),
                    destination: GuestAddr(0x8000_0100),
                    value: 0x1122_3344,
                },
            },
            EventRecord {
                seq: 7,
                data: TraceEvent::CpuWordStoreObserved {
                    site: GuestAddr(0x8000_0000),
                    destination: GuestAddr(0x8000_0104),
                    value: 0x1122_3344,
                },
            },
            EventRecord {
                seq: 8,
                data: TraceEvent::RomDmaObserved {
                    rom_offset: RomOffset(64),
                    physical_destination: PhysicalAddr(0x1000),
                    size: 4,
                },
            },
            EventRecord {
                seq: 9,
                data: TraceEvent::Invalidate { range: None },
            },
            EventRecord {
                seq: 10,
                data: TraceEvent::CpuWordStoreObserved {
                    site: GuestAddr(0x8000_0000),
                    destination: GuestAddr(0x8000_0108),
                    value: 0x5566_7788,
                },
            },
        ],
    }
}

fn event_id(trace: &DiscoveryTrace, seq: u64) -> String {
    let session = sha256(trace.to_ndjson().unwrap().as_bytes());
    format!("trace:{session}:{seq}")
}

fn imported(trace: &DiscoveryTrace) -> plaid_core::program::ProgramMap {
    import_trace(trace, &[], 128).unwrap()
}

#[test]
fn valid_complete_projection_rechecks() {
    let trace = trace();
    let map = imported(&trace);
    verify_discovery_trace_projection(&map, &trace).unwrap();
}

#[test]
fn explicit_source_unit_may_also_be_shared_observation_provenance() {
    let trace = trace();
    let mut map = imported(&trace);
    let mut indirect = map.indirect_observations.pop_first().unwrap();
    indirect
        .evidence
        .insert(indirect.source_unit.clone().unwrap());
    map.indirect_observations.insert(indirect);
    let mut verification = map.entry_verifications.pop_first().unwrap();
    verification
        .evidence
        .insert(verification.source_unit.clone());
    map.entry_verifications.insert(verification);
    map.validate().unwrap();
    verify_discovery_trace_projection(&map, &trace).unwrap();
}

#[test]
fn source_unit_metadata_cannot_be_forged_under_the_context_exemption() {
    let trace = trace();
    let mut map = imported(&trace);
    map.evidence.get_mut(&event_id(&trace, 0)).unwrap().revision = "forged".into();
    map.validate().unwrap();
    assert!(verify_discovery_trace_projection(&map, &trace).is_err());
}

#[test]
fn wrong_source_event_kind_is_rejected() {
    let trace = trace();
    let mut map = imported(&trace);
    let mut store = map
        .word_store_observations
        .iter()
        .find(|s| s.destination == GuestAddr(0x8000_0100))
        .unwrap()
        .clone();
    map.word_store_observations.remove(&store);
    store.evidence = [event_id(&trace, 2)].into();
    map.word_store_observations.insert(store);

    map.validate().unwrap();
    assert!(
        verify_discovery_trace_projection(&map, &trace)
            .unwrap_err()
            .contains("not a primitive event of the claimed role")
    );
}

#[test]
fn equal_value_different_store_event_cannot_be_transplanted() {
    let trace = trace();
    let mut map = imported(&trace);
    let stores: Vec<_> = map.word_store_observations.iter().cloned().collect();
    map.word_store_observations.clear();
    let mut first = stores
        .iter()
        .find(|s| s.destination == GuestAddr(0x8000_0100))
        .unwrap()
        .clone();
    first.evidence = [event_id(&trace, 7)].into();
    map.word_store_observations.insert(first);
    map.word_store_observations.insert(
        stores
            .iter()
            .find(|s| s.destination == GuestAddr(0x8000_0108))
            .unwrap()
            .clone(),
    );

    map.validate().unwrap();
    assert!(
        verify_discovery_trace_projection(&map, &trace)
            .unwrap_err()
            .contains("does not match retained primitive semantics")
    );
}

#[test]
fn deleting_a_source_primitive_is_detected() {
    let trace = trace();
    let mut map = imported(&trace);
    map.dma_observations.clear();
    map.validate().unwrap();
    assert!(
        verify_discovery_trace_projection(&map, &trace)
            .unwrap_err()
            .contains("is missing from ProgramMap")
    );
}

#[test]
fn foreign_session_cannot_satisfy_source_recheck() {
    let trace = trace();
    let mut other = trace.clone();
    other.header.revision = "r2".into();
    let map = imported(&other);
    map.validate().unwrap();
    assert!(
        verify_discovery_trace_projection(&map, &trace)
            .unwrap_err()
            .contains("missing source trace evidence")
    );
}

#[test]
fn invalidation_generation_is_replayed_not_inferred() {
    let trace = trace();
    let mut map = imported(&trace);
    let mut store = map
        .word_store_observations
        .iter()
        .find(|s| s.destination == GuestAddr(0x8000_0108))
        .unwrap()
        .clone();
    map.word_store_observations.remove(&store);
    store.generation = 0;
    map.word_store_observations.insert(store);
    map.validate().unwrap();
    assert!(verify_discovery_trace_projection(&map, &trace).is_err());
}

#[test]
fn indirect_source_unit_is_authenticated_to_compile_begin() {
    let trace = trace();
    let mut map = imported(&trace);
    let mut indirect = map.indirect_observations.first().unwrap().clone();
    map.indirect_observations.remove(&indirect);
    indirect.source_unit = None;
    map.indirect_observations.insert(indirect);
    map.validate().unwrap();
    assert!(verify_discovery_trace_projection(&map, &trace).is_err());
}

#[test]
fn entry_verification_context_is_source_bound() {
    let trace = trace();
    let mut map = imported(&trace);
    let mut verification = map.entry_verifications.first().unwrap().clone();
    map.entry_verifications.remove(&verification);
    verification.source_unit = event_id(&trace, 2);
    map.entry_verifications.insert(verification);
    map.validate().unwrap();
    assert!(verify_discovery_trace_projection(&map, &trace).is_err());
}

#[test]
fn derived_facts_may_retain_primitive_provenance() {
    let trace = trace();
    let mut map = imported(&trace);
    let evidence: EvidenceRefs = [event_id(&trace, 6)].into();
    map.regions.insert(Region {
        image: "derived-context-only".into(),
        generation: 0,
        range: GuestRange {
            start: GuestAddr(0x8000_1000),
            size: 4,
        },
        rom_offset: None,
        physical_start: None,
        overlay: None,
        evidence,
    });
    map.validate().unwrap();
    verify_discovery_trace_projection(&map, &trace).unwrap();
}

#[test]
fn dispatch_projection_requires_every_source_event_and_exact_semantics() {
    let trace = trace();
    let original = imported(&trace);
    let mut deleted = original.clone();
    deleted.target_dispatch_observations.clear();
    deleted.validate().unwrap();
    assert!(verify_discovery_trace_projection(&deleted, &trace).is_err());
    let mut forged = original.clone();
    let mut dispatch = forged.target_dispatch_observations.pop_first().unwrap();
    dispatch.generation += 1;
    forged.target_dispatch_observations.insert(dispatch);
    forged.validate().unwrap();
    assert!(verify_discovery_trace_projection(&forged, &trace).is_err());
}

#[test]
fn dispatch_identity_cannot_fork_or_cross_primitive_roles() {
    let trace = trace();
    let original = imported(&trace);
    let mut forked = original.clone();
    let mut dispatch = forked.target_dispatch_observations.first().unwrap().clone();
    dispatch.target = GuestAddr(0x8000_0004);
    forked.target_dispatch_observations.insert(dispatch);
    assert!(forked.validate().is_err());
    let mut crossed = original;
    let mut dispatch = crossed.target_dispatch_observations.pop_first().unwrap();
    dispatch.evidence = [event_id(&trace, 6)].into();
    crossed.target_dispatch_observations.insert(dispatch);
    assert!(crossed.validate().is_err());
}

#[test]
fn equal_identity_recompilation_cannot_substitute_exact_source_unit() {
    let mut trace = trace();
    trace.events.clear();
    let pc = GuestAddr(0x8000_0000);
    let words = vec![0x03e0_0008, 0];
    let mut events = Vec::new();
    for unit in [0, 1] {
        events.extend([
            TraceEvent::CompileBegin {
                unit,
                start: pc,
                physical_start: None,
                delay_slot_entry: false,
            },
            TraceEvent::EntryInstalled {
                unit,
                pc,
                register_mask: 0,
            },
            TraceEvent::UnitCompiled {
                unit,
                start: pc,
                words: words.clone(),
            },
        ]);
    }
    events.extend([
        TraceEvent::EntryBytesVerified {
            unit: 0,
            pc,
            register_mask: 0,
            words,
        },
        TraceEvent::IndirectTargetObserved {
            site: pc,
            target: pc,
            delay_slot_pc: Some(GuestAddr(pc.0 + 4)),
            source_unit: Some(0),
        },
    ]);
    trace.events = events
        .into_iter()
        .enumerate()
        .map(|(seq, data)| EventRecord {
            seq: seq as u64,
            data,
        })
        .collect();
    let map = imported(&trace);
    verify_discovery_trace_projection(&map, &trace).unwrap();
    let original_unit = event_id(&trace, 0);
    let decoy_unit = event_id(&trace, 3);
    let region = map.regions.first().unwrap();
    assert!(region.evidence.contains(&original_unit));
    assert!(region.evidence.contains(&decoy_unit));
    // Region provenance membership accepts both equal-byte compilation units;
    // complete source authentication must still preserve the actual event's unit.
    let mut forged_entry = map.clone();
    let mut entry = forged_entry.entry_verifications.pop_first().unwrap();
    entry.source_unit = decoy_unit.clone();
    forged_entry.entry_verifications.insert(entry);
    forged_entry.validate().unwrap();
    assert!(verify_discovery_trace_projection(&forged_entry, &trace).is_err());
    let mut forged_indirect = map;
    let mut observation = forged_indirect.indirect_observations.pop_first().unwrap();
    observation.source_unit = Some(decoy_unit);
    forged_indirect.indirect_observations.insert(observation);
    forged_indirect.validate().unwrap();
    assert!(verify_discovery_trace_projection(&forged_indirect, &trace).is_err());
}
