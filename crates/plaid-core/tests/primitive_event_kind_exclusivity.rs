use plaid_core::{
    EvidenceKind, GuestAddr,
    merge::merge_maps,
    program::{
        CodeAddress, Evidence, EvidenceRefs, GuestRange, ObservedEntryVerification,
        ObservedIndirect, ObservedWordStore, ProgramMap, Region, RomIdentity,
    },
};

fn refs(ids: &[&str]) -> EvidenceRefs {
    ids.iter().map(|id| (*id).to_string()).collect()
}

fn base_map() -> ProgramMap {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    });
    map.evidence.insert(
        "static:entry".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "test".into(),
            revision: "0".into(),
            detail: "entry provenance".into(),
        },
    );
    for n in 0..8 {
        map.evidence.insert(
            format!("trace:session:{n}"),
            Evidence {
                kind: EvidenceKind::Trace,
                producer: "test-trace".into(),
                revision: "0".into(),
                detail: format!("trace event {n}"),
            },
        );
    }
    map.entries.insert(
        CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "image".into(),
            generation: 0,
        },
        refs(&["static:entry"]),
    );
    map
}

fn store(event: &str) -> ObservedWordStore {
    ObservedWordStore {
        site: GuestAddr(0x8000_0010),
        destination: GuestAddr(0x8000_0100),
        value: 0x1122_3344,
        generation: 0,
        evidence: refs(&[event]),
    }
}

fn indirect(event: &str, source_unit: Option<&str>) -> ObservedIndirect {
    ObservedIndirect {
        site: GuestAddr(0x8000_0020),
        target: GuestAddr(0x8000_0040),
        delay_slot_pc: Some(GuestAddr(0x8000_0024)),
        generation: 0,
        source_unit: source_unit.map(str::to_string),
        evidence: refs(&[event]),
    }
}

fn verification(event: &str, source_unit: &str) -> ObservedEntryVerification {
    ObservedEntryVerification {
        entry: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "image".into(),
            generation: 0,
        },
        register_mask: 0,
        source_unit: source_unit.into(),
        generation: 0,
        evidence: refs(&[event]),
    }
}

#[test]
fn one_trace_event_cannot_be_both_store_and_indirect() {
    let mut map = base_map();
    map.word_store_observations.insert(store("trace:session:1"));
    map.indirect_observations
        .insert(indirect("trace:session:1", None));
    assert!(
        map.validate().is_err(),
        "one TraceEvent enum record cannot simultaneously be a CPU store and indirect transfer"
    );
}

#[test]
fn one_trace_event_cannot_be_both_indirect_and_entry_verification() {
    let mut map = base_map();
    map.indirect_observations
        .insert(indirect("trace:session:2", Some("trace:session:0")));
    map.entry_verifications
        .insert(verification("trace:session:2", "trace:session:0"));
    assert!(
        map.validate().is_err(),
        "one TraceEvent enum record cannot be both an indirect transfer and entry verification"
    );
}

#[test]
fn raw_event_identity_cannot_masquerade_as_compile_begin_source_unit() {
    let mut map = base_map();
    map.word_store_observations.insert(store("trace:session:3"));
    map.indirect_observations
        .insert(indirect("trace:session:4", Some("trace:session:3")));
    assert!(
        map.validate().is_err(),
        "a CPU-store event identity cannot also name a CompileBegin source unit"
    );
}

#[test]
fn cross_map_merge_cannot_launder_a_cross_kind_event_collision() {
    let mut left = base_map();
    left.word_store_observations
        .insert(store("trace:session:5"));
    assert!(left.validate().is_ok());

    let mut right = base_map();
    right
        .indirect_observations
        .insert(indirect("trace:session:5", None));
    assert!(right.validate().is_ok());

    assert!(
        merge_maps(&left, &right).is_err(),
        "merging individually valid maps must not turn one raw event into two event kinds"
    );
    assert!(merge_maps(&right, &left).is_err());
}

#[test]
fn distinct_events_and_shared_source_units_remain_valid() {
    let mut map = base_map();
    map.word_store_observations.insert(store("trace:session:1"));
    map.indirect_observations
        .insert(indirect("trace:session:2", Some("trace:session:0")));
    map.entry_verifications
        .insert(verification("trace:session:3", "trace:session:0"));
    assert!(map.validate().is_ok());
}

#[test]
fn raw_event_provenance_may_still_propagate_to_derived_facts() {
    let mut map = base_map();
    map.word_store_observations.insert(store("trace:session:1"));
    map.regions.insert(Region {
        image: "image".into(),
        generation: 0,
        range: GuestRange {
            start: GuestAddr(0x8000_0000),
            size: 8,
        },
        rom_offset: None,
        physical_start: None,
        overlay: None,
        evidence: refs(&["trace:session:1"]),
    });
    assert!(
        map.validate().is_ok(),
        "derived facts may retain the raw event as provenance without claiming a second raw event role"
    );
}
