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
    store.evidence = [event_id(&trace, 5)].into();
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
    verification.source_unit = event_id(&trace, 5);
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
