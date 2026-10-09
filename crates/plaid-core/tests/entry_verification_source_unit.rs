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
                data: TraceEvent::EntryInstalled {
                    unit: 0,
                    pc: GuestAddr(0x8000_0000),
                    register_mask: 0,
                },
            },
            EventRecord {
                seq: 2,
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

fn compile_begin_evidence(map: &ProgramMap, unit: u64) -> String {
    let needle = format!("CompileBegin {{ unit: {unit},");
    map.evidence
        .iter()
        .find(|(_, e)| e.kind == EvidenceKind::Trace && e.detail.contains(&needle))
        .map(|(id, _)| id.clone())
        .expect("compile-begin evidence")
}

#[test]
fn unrelated_compile_unit_must_not_validate_as_verified_entry_source() {
    let words = vec![0x03e0_0008, 0];
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
            words: words.clone(),
        },
    );
    push(
        &mut trace,
        TraceEvent::EntryBytesVerified {
            unit: 0,
            pc: GuestAddr(0x8000_0000),
            register_mask: 0,
            words,
        },
    );

    let map = import_trace(&trace, &[], 100).unwrap();
    let good = map.entry_verifications.first().unwrap().source_unit.clone();
    let unrelated = compile_begin_evidence(&map, 1);
    assert_ne!(good, unrelated);

    let mut forged = map.clone();
    let mut verification = forged.entry_verifications.pop_first().unwrap();
    verification.source_unit = unrelated;
    forged.entry_verifications.insert(verification);

    // Desired invariant. This fails on current main-derived validation.
    assert!(forged.validate().is_err());
}

#[test]
fn equal_byte_same_identity_recompile_defeats_region_provenance_join() {
    let words = vec![0x03e0_0008, 0];
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
        TraceEvent::EntryInstalled {
            unit: 1,
            pc: GuestAddr(0x8000_0000),
            register_mask: 0,
        },
    );
    push(
        &mut trace,
        TraceEvent::UnitCompiled {
            unit: 1,
            start: GuestAddr(0x8000_0000),
            words: words.clone(),
        },
    );
    push(
        &mut trace,
        TraceEvent::EntryBytesVerified {
            unit: 0,
            pc: GuestAddr(0x8000_0000),
            register_mask: 0,
            words,
        },
    );

    let map = import_trace(&trace, &[], 100).unwrap();
    let verification = map.entry_verifications.first().unwrap();
    let unit0 = verification.source_unit.clone();
    let unit1 = compile_begin_evidence(&map, 1);
    assert_ne!(unit0, unit1);

    let matching_region = map
        .regions
        .iter()
        .find(|r| {
            r.image == verification.entry.image
                && r.generation == verification.entry.generation
                && r.range.contains(verification.entry.pc)
        })
        .unwrap();
    assert!(matching_region.evidence.contains(&unit0));
    assert!(matching_region.evidence.contains(&unit1));

    let mut forged = map.clone();
    let mut verification = forged.entry_verifications.pop_first().unwrap();
    verification.source_unit = unit1;
    forged.entry_verifications.insert(verification);

    // Equal bytes/address/generation collapse both compilations into the same
    // executable identity, so "source unit appears in matching region evidence"
    // cannot recover the exact unit either.
    assert!(forged.validate().is_ok());
}
