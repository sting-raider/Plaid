use plaid_core::{EvidenceKind, GuestAddr, merge::merge_maps, program::*};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn trace(detail: &str) -> Evidence {
    Evidence {
        kind: EvidenceKind::Trace,
        producer: "sensor".into(),
        revision: "pin".into(),
        detail: detail.into(),
    }
}

fn static_evidence(detail: &str) -> Evidence {
    Evidence {
        kind: EvidenceKind::Static,
        producer: "fixture".into(),
        revision: "1".into(),
        detail: detail.into(),
    }
}

fn observation(event: &str) -> ObservedIndirect {
    ObservedIndirect {
        site: GuestAddr(0x8000_0000),
        target: GuestAddr(0x8000_0020),
        delay_slot_pc: Some(GuestAddr(0x8000_0004)),
        generation: 0,
        source_unit: None,
        evidence: [event.to_string()].into(),
    }
}

fn map_with_event(event: &str) -> ProgramMap {
    let mut map = ProgramMap::new(rom());
    map.evidence.insert(
        event.into(),
        trace("one concrete IndirectTargetObserved trace event"),
    );
    map.indirect_observations.insert(observation(event));
    assert!(map.validate().is_ok());
    map
}

#[test]
fn one_event_cannot_name_two_different_targets() {
    let mut map = map_with_event("event0");
    let mut forged = observation("event0");
    forged.target = GuestAddr(0x8000_0040);
    map.indirect_observations.insert(forged);
    assert!(
        map.validate().is_err(),
        "one executed indirect-transfer event cannot have two targets"
    );
}

#[test]
fn one_event_cannot_change_other_transfer_semantics() {
    let base = observation("event0");
    let mut variants = Vec::new();

    let mut changed_site = base.clone();
    changed_site.site = GuestAddr(0x8000_0010);
    changed_site.delay_slot_pc = Some(GuestAddr(0x8000_0014));
    variants.push(("site", changed_site));

    let mut changed_delay = base.clone();
    changed_delay.delay_slot_pc = None;
    variants.push(("delay slot", changed_delay));

    let mut changed_generation = base.clone();
    changed_generation.generation = 1;
    variants.push(("generation", changed_generation));

    for (index, (label, variant)) in variants.into_iter().enumerate() {
        let mut map = map_with_event("event0");
        map.indirect_observations.insert(variant);
        assert!(
            map.validate().is_err(),
            "event identity was reused with incompatible {label} semantics (case {index})"
        );
    }
}

#[test]
fn one_event_cannot_change_explicit_source_unit() {
    let mut map = map_with_event("event0");
    map.evidence
        .insert("unit0".into(), trace("CompileBegin unit 0"));
    map.evidence
        .insert("unit1".into(), trace("CompileBegin unit 1"));

    let mut from_unit0 = observation("event0");
    from_unit0.source_unit = Some("unit0".into());
    let mut from_unit1 = observation("event0");
    from_unit1.source_unit = Some("unit1".into());
    map.indirect_observations.clear();
    map.indirect_observations.insert(from_unit0);
    map.indirect_observations.insert(from_unit1);

    assert!(
        map.validate().is_err(),
        "one executed transfer event cannot identify two executing source units"
    );
}

#[test]
fn distinct_event_ids_remain_valid_for_distinct_transfers() {
    let mut map = map_with_event("event0");
    map.evidence.insert(
        "event1".into(),
        trace("a distinct IndirectTargetObserved event"),
    );
    let mut second = observation("event1");
    second.target = GuestAddr(0x8000_0040);
    map.indirect_observations.insert(second);
    assert!(map.validate().is_ok());
}

#[test]
fn equivalent_semantics_may_accumulate_provenance() {
    let mut map = map_with_event("event0");
    map.evidence.insert(
        "context".into(),
        static_evidence("independent supporting context"),
    );
    let mut same = observation("event0");
    same.evidence.insert("context".into());
    map.indirect_observations.insert(same);
    assert!(map.validate().is_ok());
}

#[test]
fn shared_source_unit_trace_context_is_not_an_event_identity() {
    let mut map = ProgramMap::new(rom());
    map.evidence
        .insert("unit0".into(), trace("CompileBegin unit 0"));
    map.evidence.insert(
        "event0".into(),
        trace("first concrete IndirectTargetObserved event"),
    );
    map.evidence.insert(
        "event1".into(),
        trace("second concrete IndirectTargetObserved event"),
    );

    let mut first = observation("event0");
    first.source_unit = Some("unit0".into());
    first.evidence.insert("unit0".into());

    let mut second = observation("event1");
    second.target = GuestAddr(0x8000_0040);
    second.source_unit = Some("unit0".into());
    second.evidence.insert("unit0".into());

    map.indirect_observations.insert(first);
    map.indirect_observations.insert(second);
    assert!(
        map.validate().is_ok(),
        "a CompileBegin source-unit identity is reusable context, not the executed transfer event"
    );
}

#[test]
fn merge_cannot_launder_one_event_into_two_transfers() {
    let left = map_with_event("event0");
    let mut right = map_with_event("event0");
    let mut changed = right.indirect_observations.pop_first().unwrap();
    changed.target = GuestAddr(0x8000_0040);
    right.indirect_observations.insert(changed);
    assert!(right.validate().is_ok());

    assert!(
        merge_maps(&left, &right).is_err(),
        "two individually valid maps must not compose one event identity into two executions"
    );
    assert!(
        merge_maps(&right, &left).is_err(),
        "event-identity conflict must be merge-order symmetric"
    );
}
