use plaid_core::{
    EvidenceKind, GuestAddr,
    discovery::CodeImage,
    indirect::analyze_indirect,
    merge::{import_trace, merge_maps},
    program::{
        CodeAddress, PhysicalAddr, ProgramMap, RomIdentity, RomOffset, TargetDispatchKind,
    },
    solver::{ClosureStatus, Scope, SolveReport, solve},
    trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "target-dispatch-test".into(),
            generation: 0,
        },
        // J 0x80000000; NOP. This finite immutable scope closes normally.
        words: vec![0x0800_0000, 0],
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
    }
}

fn indirect_image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "target-dispatch-indirect-test".into(),
            generation: 0,
        },
        // LUI/ORI r8, 0x80000000; JR r8; NOP. Static analysis can certify
        // the indirect target, but that must not lend a source site to a raw lookup.
        words: vec![0x3c08_8000, 0x3508_0000, 0x0100_0008, 0],
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
    }
}

fn trace(i: &CodeImage, extra: Option<TraceEvent>) -> DiscoveryTrace {
    let mut events = vec![
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
                words: i.words.clone(),
            },
        },
    ];
    if let Some(data) = extra {
        events.push(EventRecord { seq: 3, data });
    }
    DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: rom(),
            engine: "target-dispatch-test-sensor".into(),
            revision: "exact-test-pin".into(),
            capabilities: Default::default(),
        },
        events,
    }
}

fn import(i: &CodeImage, extra: Option<TraceEvent>) -> ProgramMap {
    import_trace(&trace(i, extra), std::slice::from_ref(i), 100).unwrap()
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|blocker| blocker.kind == kind)
}

fn delete_only_derived_target_blocker(mut map: ProgramMap) -> ProgramMap {
    let blocker = map
        .unresolved
        .iter()
        .find(|u| u.kind == "uncorrelated_target")
        .expect("importer must derive the target blocker")
        .clone();
    assert!(blocker.evidence.iter().all(|id| map.evidence.contains_key(id)));
    map.unresolved.remove(&blocker);
    assert!(map
        .unresolved
        .iter()
        .all(|u| u.kind != "uncorrelated_target"));
    // The trace event provenance record and typed raw primitive still exist.
    // Only the derived diagnostic was deleted.
    assert!(blocker.evidence.iter().all(|id| map.evidence.contains_key(id)));
    assert_eq!(map.target_dispatch_observations.len(), 1);
    map.validate().unwrap();
    map
}

fn assert_raw_gate(map: ProgramMap, i: &CodeImage) {
    let edited = delete_only_derived_target_blocker(map);
    let report = solve(&edited, std::slice::from_ref(i), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_raw_target_dispatch"));
}

#[test]
fn deleting_lookup_diagnostic_cannot_manufacture_static_closure() {
    let i = image();
    let map = import(
        &i,
        Some(TraceEvent::TargetLookup {
            // Equal to an already decoded executable PC on purpose. PC/value
            // equality must not synthesize the missing source-site correlation.
            target: GuestAddr(0x8000_0000),
            delay_slot_entry: false,
        }),
    );
    assert_eq!(map.target_dispatch_observations.len(), 1);
    assert!(matches!(
        map.target_dispatch_observations.first().unwrap().kind,
        TargetDispatchKind::TargetLookup {
            delay_slot_entry: false
        }
    ));
    assert_eq!(
        solve(&map, std::slice::from_ref(&i), Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Open
    );
    assert_raw_gate(map, &i);
}

#[test]
fn deleting_runtime_link_diagnostic_cannot_manufacture_static_closure() {
    let i = image();
    let map = import(
        &i,
        Some(TraceEvent::RuntimeLink {
            target: GuestAddr(0x8000_0000),
        }),
    );
    assert_eq!(map.target_dispatch_observations.len(), 1);
    assert!(matches!(
        map.target_dispatch_observations.first().unwrap().kind,
        TargetDispatchKind::RuntimeLink
    ));
    assert_eq!(
        solve(&map, std::slice::from_ref(&i), Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Open
    );
    assert_raw_gate(map, &i);
}

#[test]
fn certified_indirect_decoy_cannot_launder_source_uncorrelated_lookup() {
    let i = indirect_image();
    let map = import(
        &i,
        Some(TraceEvent::TargetLookup {
            target: GuestAddr(0x8000_0000),
            delay_slot_entry: false,
        }),
    );
    let map = analyze_indirect(&map, &i).unwrap();
    assert!(map.indirect_sites.iter().any(|site| site.closed_proof.is_some()));
    assert_raw_gate(map, &i);
}

#[test]
fn raw_dispatch_survives_roundtrip_merge_and_same_target_kind_distinction() {
    let i = image();
    let lookup = import(
        &i,
        Some(TraceEvent::TargetLookup {
            target: GuestAddr(0x8000_0000),
            delay_slot_entry: true,
        }),
    );
    let link = import(
        &i,
        Some(TraceEvent::RuntimeLink {
            target: GuestAddr(0x8000_0000),
        }),
    );
    let merged = merge_maps(&lookup, &link).unwrap();
    assert_eq!(merged.target_dispatch_observations.len(), 2);
    assert_eq!(merged, merge_maps(&merged, &merged).unwrap());
    let roundtrip = ProgramMap::from_json(&merged.to_json().unwrap()).unwrap();
    assert_eq!(roundtrip, merged);
    assert!(roundtrip.target_dispatch_observations.iter().any(|o| matches!(
        o.kind,
        TargetDispatchKind::TargetLookup {
            delay_slot_entry: true
        }
    )));
    assert!(roundtrip
        .target_dispatch_observations
        .iter()
        .any(|o| matches!(o.kind, TargetDispatchKind::RuntimeLink)));
}

#[test]
fn raw_dispatch_rejects_forged_non_trace_provenance() {
    let i = image();
    let mut map = import(
        &i,
        Some(TraceEvent::TargetLookup {
            target: GuestAddr(0x8000_0000),
            delay_slot_entry: false,
        }),
    );
    let evidence = map
        .target_dispatch_observations
        .first()
        .unwrap()
        .evidence
        .first()
        .unwrap()
        .clone();
    map.evidence.get_mut(&evidence).unwrap().kind = EvidenceKind::Static;
    assert!(map
        .validate()
        .unwrap_err()
        .contains("target-dispatch observation lacks trace provenance"));
}

#[test]
fn no_target_dispatch_event_control_remains_closed() {
    let i = image();
    let map = import(&i, None);
    assert!(map.unresolved.is_empty());
    assert!(map.target_dispatch_observations.is_empty());
    assert_eq!(
        solve(&map, &[i], Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Closed
    );
}
