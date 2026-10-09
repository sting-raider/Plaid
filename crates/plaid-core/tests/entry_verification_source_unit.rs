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

/// Smallest plausible post-import check without parsing Evidence.detail:
/// require the claimed source unit to be among the provenance of an executable
/// region that contains the verified entry. This is deliberately branch-local
/// research code; the second adversary proves it is not sufficient.
fn candidate_region_binding(map: &ProgramMap) -> bool {
    map.entry_verifications.iter().all(|verification| {
        map.entries.contains_key(&verification.entry)
            && map
                .evidence
                .get(&verification.source_unit)
                .is_some_and(|e| e.kind == EvidenceKind::Trace)
            && map.regions.iter().any(|region| {
                region.image == verification.entry.image
                    && region.generation == verification.entry.generation
                    && region.range.contains(verification.entry.pc)
                    && region.evidence.contains(&verification.source_unit)
            })
    })
}

#[test]
fn unrelated_compile_unit_substitution_is_not_structurally_bound() {
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
    assert!(candidate_region_binding(&map));
    let good = map.entry_verifications.first().unwrap().source_unit.clone();
    let unrelated = compile_begin_evidence(&map, 1);
    assert_ne!(good, unrelated);

    let mut forged = map.clone();
    let mut verification = forged.entry_verifications.pop_first().unwrap();
    verification.source_unit = unrelated;
    forged.entry_verifications.insert(verification);

    // Reproduction on current main-derived ProgramMap validation.
    assert!(forged.validate().is_ok());
    // The smallest structural candidate does catch this easy substitution.
    assert!(!candidate_region_binding(&forged));
}

#[test]
fn equal_byte_same_identity_recompile_defeats_region_provenance_candidate() {
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
    assert!(candidate_region_binding(&map));
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

    // Current validation accepts it, and the candidate also accepts it because
    // provenance union collapsed both equal-byte compilations onto the same
    // Region. That is exactly why this partial check must not be promoted.
    assert!(forged.validate().is_ok());
    assert!(candidate_region_binding(&forged));
}
