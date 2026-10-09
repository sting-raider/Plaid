use plaid_core::{
    GuestAddr,
    discovery::CodeImage,
    merge::import_trace,
    program::{CodeAddress, PhysicalAddr, ProgramMap, RomIdentity, RomOffset},
    solver::{ClosureStatus, Scope, solve},
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

fn trace(extra: Option<TraceEvent>) -> DiscoveryTrace {
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
                words: image().words,
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

fn import(extra: Option<TraceEvent>) -> ProgramMap {
    let i = image();
    import_trace(&trace(extra), std::slice::from_ref(&i), 100).unwrap()
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
    // The trace event provenance record still exists. Only its derived diagnostic
    // was deleted, which must not be enough to manufacture closure.
    assert!(blocker.evidence.iter().all(|id| map.evidence.contains_key(id)));
    map.validate().unwrap();
    map
}

#[test]
fn deleting_lookup_diagnostic_cannot_manufacture_static_closure() {
    let map = import(Some(TraceEvent::TargetLookup {
        target: GuestAddr(0x8000_0000),
        delay_slot_entry: false,
    }));
    assert_eq!(
        solve(&map, &[image()], Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Open
    );

    let edited = delete_only_derived_target_blocker(map);
    assert_eq!(
        solve(&edited, &[image()], Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Open,
        "retained lookup provenance must independently keep closure open"
    );
}

#[test]
fn deleting_runtime_link_diagnostic_cannot_manufacture_static_closure() {
    let map = import(Some(TraceEvent::RuntimeLink {
        target: GuestAddr(0x8000_0000),
    }));
    assert_eq!(
        solve(&map, &[image()], Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Open
    );

    let edited = delete_only_derived_target_blocker(map);
    assert_eq!(
        solve(&edited, &[image()], Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Open,
        "retained runtime-link provenance must independently keep closure open"
    );
}

#[test]
fn no_target_dispatch_event_control_remains_closed() {
    let map = import(None);
    assert!(map.unresolved.is_empty());
    assert_eq!(
        solve(&map, &[image()], Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Closed
    );
}
