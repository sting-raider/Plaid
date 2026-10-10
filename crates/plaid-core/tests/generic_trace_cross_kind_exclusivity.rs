use plaid_core::{EvidenceKind, GuestAddr, merge::merge_maps, program::*};

const SHARED: &str = "trace:synthetic:7";
const STORE: &str = "trace:synthetic:8";
const INDIRECT: &str = "trace:synthetic:9";
const VERIFY: &str = "trace:synthetic:10";
const UNIT: &str = "trace:synthetic:11";

fn trace_evidence(detail: &str) -> Evidence {
    Evidence {
        kind: EvidenceKind::Trace,
        producer: "synthetic-trace".into(),
        revision: "0".into(),
        detail: detail.into(),
    }
}

fn empty_map() -> ProgramMap {
    ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 256,
    })
}

fn add_evidence(map: &mut ProgramMap, id: &str, detail: &str) {
    map.evidence.insert(id.into(), trace_evidence(detail));
}

fn add_store(map: &mut ProgramMap, event: &str) {
    map.word_store_observations.insert(ObservedWordStore {
        site: GuestAddr(0x8000_1000),
        destination: GuestAddr(0x8000_2000),
        value: 0x1122_3344,
        generation: 3,
        evidence: [event.to_string()].into(),
    });
}

fn add_indirect(map: &mut ProgramMap, event: &str, source_unit: Option<&str>, include_unit: bool) {
    let mut evidence: EvidenceRefs = [event.to_string()].into();
    if include_unit {
        evidence.insert(source_unit.expect("source unit").to_string());
    }
    map.indirect_observations.insert(ObservedIndirect {
        site: GuestAddr(0x8000_1000),
        target: GuestAddr(0x8000_2000),
        delay_slot_pc: Some(GuestAddr(0x8000_1004)),
        generation: 3,
        source_unit: source_unit.map(str::to_string),
        evidence,
    });
}

fn add_verification(map: &mut ProgramMap, event: &str, include_unit: bool) {
    let entry = CodeAddress {
        pc: GuestAddr(0x8000_1000),
        image: "image".into(),
        generation: 3,
    };
    map.entries.insert(entry.clone(), [UNIT.to_string()].into());
    let mut evidence: EvidenceRefs = [event.to_string()].into();
    if include_unit {
        evidence.insert(UNIT.to_string());
    }
    map.entry_verifications.insert(ObservedEntryVerification {
        entry,
        register_mask: 0,
        source_unit: UNIT.into(),
        generation: 3,
        evidence,
    });
}

#[test]
fn one_event_cannot_be_store_and_indirect() {
    let mut map = empty_map();
    add_evidence(&mut map, SHARED, "one concrete CpuWordStoreObserved event");
    add_store(&mut map, SHARED);
    add_indirect(&mut map, SHARED, None, false);
    assert!(map.validate().is_err(), "one trace event cannot be both a successful SW and an executed indirect transfer");
}

#[test]
fn one_event_cannot_be_store_and_entry_verification() {
    let mut map = empty_map();
    add_evidence(&mut map, SHARED, "one concrete CpuWordStoreObserved event");
    add_evidence(&mut map, UNIT, "one concrete CompileBegin event");
    add_store(&mut map, SHARED);
    add_verification(&mut map, SHARED, false);
    assert!(map.validate().is_err(), "one trace event cannot be both a successful SW and EntryBytesVerified");
}

#[test]
fn one_event_cannot_be_indirect_and_entry_verification() {
    let mut map = empty_map();
    add_evidence(&mut map, SHARED, "one concrete IndirectTargetObserved event");
    add_evidence(&mut map, UNIT, "one concrete CompileBegin event");
    add_indirect(&mut map, SHARED, Some(UNIT), false);
    add_verification(&mut map, SHARED, false);
    assert!(map.validate().is_err(), "one trace event cannot be both an executed indirect transfer and EntryBytesVerified");
}

#[test]
fn merge_cannot_launder_store_event_into_indirect_role() {
    let mut left = empty_map();
    add_evidence(&mut left, SHARED, "one concrete CpuWordStoreObserved event");
    add_store(&mut left, SHARED);
    left.validate().unwrap();

    let mut right = empty_map();
    add_evidence(&mut right, SHARED, "one concrete CpuWordStoreObserved event");
    add_indirect(&mut right, SHARED, None, false);
    right.validate().unwrap();

    assert!(merge_maps(&left, &right).is_err(), "merge must reject cross-kind event fabrication");
    assert!(merge_maps(&right, &left).is_err(), "merge-order reversal must reject the same fabrication");
}

#[test]
fn distinct_primitive_event_ids_remain_valid() {
    let mut map = empty_map();
    add_evidence(&mut map, STORE, "CpuWordStoreObserved event");
    add_evidence(&mut map, INDIRECT, "IndirectTargetObserved event");
    add_evidence(&mut map, VERIFY, "EntryBytesVerified event");
    add_evidence(&mut map, UNIT, "CompileBegin event");
    add_store(&mut map, STORE);
    add_indirect(&mut map, INDIRECT, Some(UNIT), false);
    add_verification(&mut map, VERIFY, false);
    map.validate().unwrap();
}

#[test]
fn compile_begin_context_may_be_shared_without_becoming_event_role() {
    let mut map = empty_map();
    add_evidence(&mut map, INDIRECT, "IndirectTargetObserved event");
    add_evidence(&mut map, VERIFY, "EntryBytesVerified event");
    add_evidence(&mut map, UNIT, "CompileBegin event reused as explicit source-unit context");
    add_indirect(&mut map, INDIRECT, Some(UNIT), true);
    add_verification(&mut map, VERIFY, true);
    map.validate().unwrap();
}

#[test]
fn primitive_trace_event_may_support_derived_region_provenance() {
    let mut map = empty_map();
    add_evidence(&mut map, STORE, "CpuWordStoreObserved event");
    add_store(&mut map, STORE);
    map.regions.insert(Region {
        image: "derived-context".into(),
        generation: 3,
        range: GuestRange {
            start: GuestAddr(0x8000_1000),
            size: 8,
        },
        rom_offset: None,
        physical_start: None,
        overlay: None,
        evidence: [STORE.to_string()].into(),
    });
    map.validate().unwrap();
}
