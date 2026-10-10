use plaid_core::{
    EvidenceKind, GuestAddr,
    merge::import_trace,
    program::*,
    trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn base_trace(words: Vec<u32>) -> DiscoveryTrace {
    DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: rom(),
            engine: "sensor".into(),
            revision: "pin".into(),
            capabilities: Default::default(),
        },
        events: vec![
            EventRecord {
                seq: 0,
                data: TraceEvent::CompileBegin {
                    unit: 0,
                    start: GuestAddr(0x8000_0000),
                    physical_start: Some(PhysicalAddr(0)),
                    delay_slot_entry: false,
                },
            },
            EventRecord {
                seq: 1,
                data: TraceEvent::UnitCompiled {
                    unit: 0,
                    start: GuestAddr(0x8000_0000),
                    words,
                },
            },
        ],
    }
}

fn push(trace: &mut DiscoveryTrace, data: TraceEvent) {
    trace.events.push(EventRecord {
        seq: trace.events.len() as u64,
        data,
    });
}

fn trace_evidence(map: &ProgramMap, needle: &str) -> String {
    map.evidence
        .iter()
        .find(|(_, e)| e.kind == EvidenceKind::Trace && e.detail.contains(needle))
        .map(|(id, _)| id.clone())
        .unwrap_or_else(|| panic!("missing trace evidence: {needle}"))
}

fn compile_begin_evidence(map: &ProgramMap, unit: u64) -> String {
    trace_evidence(map, &format!("CompileBegin {{ unit: {unit},"))
}

fn candidate_region_binding(map: &ProgramMap) -> bool {
    map.indirect_observations.iter().all(|observation| {
        observation.source_unit.as_ref().is_none_or(|unit| {
            map.evidence
                .get(unit)
                .is_some_and(|e| e.kind == EvidenceKind::Trace)
                && map.regions.iter().any(|region| {
                    region.range.contains(observation.site) && region.evidence.contains(unit)
                })
        })
    })
}

fn push_observation(trace: &mut DiscoveryTrace) {
    push(
        trace,
        TraceEvent::IndirectTargetObserved {
            site: GuestAddr(0x8000_0000),
            target: GuestAddr(0x8000_0040),
            delay_slot_pc: Some(GuestAddr(0x8000_0004)),
            source_unit: Some(0),
        },
    );
}

#[test]
fn unrelated_completed_unit_must_not_validate_as_exact_indirect_source() {
    let words = vec![0x0100_0008, 0];
    let mut trace = base_trace(words.clone());
    push(
        &mut trace,
        TraceEvent::CompileBegin {
            unit: 1,
            start: GuestAddr(0x8000_0020),
            physical_start: Some(PhysicalAddr(0x20)),
            delay_slot_entry: false,
        },
    );
    push(
        &mut trace,
        TraceEvent::UnitCompiled {
            unit: 1,
            start: GuestAddr(0x8000_0020),
            words,
        },
    );
    push_observation(&mut trace);

    let map = import_trace(&trace, &[], 100).unwrap();
    let good = map
        .indirect_observations
        .first()
        .unwrap()
        .source_unit
        .clone()
        .unwrap();
    let unrelated = compile_begin_evidence(&map, 1);
    assert_ne!(good, unrelated);

    let mut forged = map.clone();
    let mut observation = forged.indirect_observations.pop_first().unwrap();
    observation.source_unit = Some(unrelated);
    forged.indirect_observations.insert(observation);

    // Desired invariant. This intentionally fails on canonical-base behavior.
    assert!(forged.validate().is_err());
}

#[test]
fn equal_byte_same_identity_recompile_defeats_region_provenance_candidate() {
    let words = vec![0x0100_0008, 0];
    let mut trace = base_trace(words.clone());
    push(
        &mut trace,
        TraceEvent::CompileBegin {
            unit: 1,
            start: GuestAddr(0x8000_0000),
            physical_start: Some(PhysicalAddr(0)),
            delay_slot_entry: false,
        },
    );
    push(
        &mut trace,
        TraceEvent::UnitCompiled {
            unit: 1,
            start: GuestAddr(0x8000_0000),
            words,
        },
    );
    push_observation(&mut trace);

    let map = import_trace(&trace, &[], 100).unwrap();
    assert!(candidate_region_binding(&map));
    let observation = map.indirect_observations.first().unwrap();
    let unit0 = observation.source_unit.clone().unwrap();
    let unit1 = compile_begin_evidence(&map, 1);
    assert_ne!(unit0, unit1);

    let matching_region = map
        .regions
        .iter()
        .find(|r| r.range.contains(observation.site))
        .unwrap();
    assert!(matching_region.evidence.contains(&unit0));
    assert!(matching_region.evidence.contains(&unit1));

    let mut forged = map.clone();
    let mut observation = forged.indirect_observations.pop_first().unwrap();
    observation.source_unit = Some(unit1);
    forged.indirect_observations.insert(observation);

    assert!(forged.validate().is_ok());
    assert!(candidate_region_binding(&forged));
}

#[test]
fn non_compile_trace_event_can_masquerade_as_source_unit() {
    let words = vec![0x0100_0008, 0];
    let mut trace = base_trace(words);
    push_observation(&mut trace);

    let map = import_trace(&trace, &[], 100).unwrap();
    let compiled = trace_evidence(&map, "UnitCompiled { unit: 0,");
    let compile_begin = compile_begin_evidence(&map, 0);
    assert_ne!(compiled, compile_begin);

    let mut forged = map.clone();
    let mut observation = forged.indirect_observations.pop_first().unwrap();
    observation.source_unit = Some(compiled);
    forged.indirect_observations.insert(observation);

    assert!(forged.validate().is_ok());
    assert!(candidate_region_binding(&forged));
}
