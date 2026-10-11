use plaid_core::{
    GuestAddr,
    discovery::CodeImage,
    evidence_manifest::DiscoveryTraceManifestSet,
    merge::{import_trace_with_rom, merge_maps},
    program::{GuestRange, ProgramMap, RomOffset},
    rom::{CanonicalRom, sha256},
    solver::{ClosureStatus, DiscoverySourceInputs, Scope, solve, solve_with_discovery_sources},
    trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
};

fn fixture(store: bool) -> (CanonicalRom, CodeImage, DiscoveryTrace, ProgramMap) {
    let mut bytes = vec![0; 4096];
    bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    bytes[64..72].copy_from_slice(&[0x08, 0, 0, 0, 0, 0, 0, 0]);
    let rom = CanonicalRom::from_bytes(&bytes).unwrap();
    let image = CodeImage::from_rom(
        &rom,
        RomOffset(64),
        GuestRange {
            start: GuestAddr(0x8000_0000),
            size: 8,
        },
    )
    .unwrap();
    let mut events = vec![
        TraceEvent::CompileBegin {
            unit: 1,
            start: image.base.pc,
            physical_start: None,
            delay_slot_entry: false,
        },
        TraceEvent::EntryInstalled {
            unit: 1,
            pc: image.base.pc,
            register_mask: 0,
        },
        TraceEvent::UnitCompiled {
            unit: 1,
            start: image.base.pc,
            words: image.words.clone(),
        },
    ];
    if store {
        events.push(TraceEvent::CpuWordStoreObserved {
            site: image.base.pc,
            destination: GuestAddr(0x8000_1000),
            value: 0,
        });
    }
    let trace = DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: rom.identity.clone(),
            engine: "source-admission-test".into(),
            revision: "r1".into(),
            capabilities: Default::default(),
        },
        events: events
            .into_iter()
            .enumerate()
            .map(|(seq, data)| EventRecord {
                seq: seq as u64,
                data,
            })
            .collect(),
    };
    let map = import_trace_with_rom(&trace, std::slice::from_ref(&image), &rom, 100).unwrap();
    (rom, image, trace, map)
}

#[test]
fn source_bound_declared_closure_preserves_exact_expectations_and_map_commitment() {
    let (rom, image, trace, map) = fixture(false);
    let traces = [trace];
    let expected = DiscoveryTraceManifestSet::from_traces(&traces).unwrap();
    let known = [image];
    let sources = DiscoverySourceInputs {
        expected: &expected,
        traces: &traces,
        rom: &rom,
        known_images: &known,
        import_budget: 100,
    };
    let report =
        solve_with_discovery_sources(&map, &known, Scope::DeclaredStaticImages, &sources).unwrap();
    assert_eq!(report.closure.status, ClosureStatus::Closed);
    assert!(!report.closure.native_complete);
    assert_eq!(report.discovery_sources, expected);
    assert_eq!(report.map_sha256, sha256(map.to_json().unwrap().as_bytes()));
    let whole = solve_with_discovery_sources(&map, &known, Scope::WholeRom, &sources).unwrap();
    assert_eq!(whole.closure.status, ClosureStatus::Open);
    assert!(
        whole
            .closure
            .blockers
            .iter()
            .any(|b| b.kind == "unproven_executable_universe")
    );
}

#[test]
fn deleting_raw_negative_facts_and_diagnostics_cannot_enter_source_bound_solver() {
    let (rom, image, trace, mut map) = fixture(true);
    let traces = [trace];
    let expected = DiscoveryTraceManifestSet::from_traces(&traces).unwrap();
    let known = [image];
    assert_eq!(
        solve(&map, &known, Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Open
    );
    map.word_store_observations.clear();
    map.executable_writes.clear();
    map.unresolved.clear();
    map.validate().unwrap();
    // Without the separately preserved source expectation, the solver only has
    // the submitted finite static facts and cannot recover this deleted store.
    assert_eq!(
        solve(&map, &known, Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Closed
    );
    let sources = DiscoverySourceInputs {
        expected: &expected,
        traces: &traces,
        rom: &rom,
        known_images: &known,
        import_budget: 100,
    };
    for scope in [Scope::DeclaredStaticImages, Scope::WholeRom] {
        assert!(solve_with_discovery_sources(&map, &known, scope, &sources).is_err());
    }
}

#[test]
fn installed_entry_binding_is_checked_after_primitive_authentication() {
    let (rom, image, trace, mut map) = fixture(false);
    let traces = [trace];
    let expected = DiscoveryTraceManifestSet::from_traces(&traces).unwrap();
    let known = [image];
    let installed_id = map
        .evidence
        .keys()
        .find(|id| id.ends_with(":1"))
        .unwrap()
        .clone();
    for refs in map.entries.values_mut() {
        refs.remove(&installed_id);
    }
    map.validate().unwrap();
    expected
        .verify_primitive_projections(&map, &traces)
        .unwrap();
    let sources = DiscoverySourceInputs {
        expected: &expected,
        traces: &traces,
        rom: &rom,
        known_images: &known,
        import_budget: 100,
    };
    assert!(
        solve_with_discovery_sources(&map, &known, Scope::DeclaredStaticImages, &sources)
            .unwrap_err()
            .contains("EntryInstalled")
    );
}

#[test]
fn merged_sources_preserve_negative_sessions_and_reject_whole_session_deletion() {
    let (rom, image, positive, positive_map) = fixture(false);
    let (_, _, negative, negative_map) = fixture(true);
    let traces = [positive.clone(), negative];
    let expected = DiscoveryTraceManifestSet::from_traces(&traces).unwrap();
    let known = [image];
    let merged = merge_maps(&positive_map, &negative_map).unwrap();
    let sources = DiscoverySourceInputs {
        expected: &expected,
        traces: &traces,
        rom: &rom,
        known_images: &known,
        import_budget: 100,
    };
    let report =
        solve_with_discovery_sources(&merged, &known, Scope::DeclaredStaticImages, &sources)
            .unwrap();
    assert_eq!(report.closure.status, ClosureStatus::Open);
    assert_eq!(report.discovery_sources.sessions.len(), 2);
    let submitted = [positive];
    let deleted = DiscoverySourceInputs {
        traces: &submitted,
        ..sources
    };
    assert!(
        solve_with_discovery_sources(&positive_map, &known, Scope::DeclaredStaticImages, &deleted)
            .is_err()
    );
    let reverse = [traces[1].clone(), traces[0].clone()];
    let reordered = DiscoverySourceInputs {
        traces: &reverse,
        ..sources
    };
    let reversed_report =
        solve_with_discovery_sources(&merged, &known, Scope::DeclaredStaticImages, &reordered)
            .unwrap();
    assert_eq!(
        serde_json::to_string(&report).unwrap(),
        serde_json::to_string(&reversed_report).unwrap()
    );
}

#[test]
fn wrong_rom_and_unexpected_map_session_fail_before_closure() {
    let (rom, image, trace, map) = fixture(false);
    let traces = [trace];
    let expected = DiscoveryTraceManifestSet::from_traces(&traces).unwrap();
    let known = [image];
    let mut other_bytes = rom.bytes().to_vec();
    other_bytes[100] = 1;
    let other = CanonicalRom::from_bytes(&other_bytes).unwrap();
    let sources = DiscoverySourceInputs {
        expected: &expected,
        traces: &traces,
        rom: &other,
        known_images: &known,
        import_budget: 100,
    };
    assert!(
        solve_with_discovery_sources(&map, &known, Scope::DeclaredStaticImages, &sources).is_err()
    );
    let (_, _, extra, extra_map) = fixture(true);
    let combined = merge_maps(&map, &extra_map).unwrap();
    let correct_rom = DiscoverySourceInputs {
        rom: &rom,
        ..sources
    };
    assert!(
        solve_with_discovery_sources(&combined, &known, Scope::WholeRom, &correct_rom).is_err()
    );
    // Even supplying the unexpected source cannot replace the independent set.
    let added = [traces[0].clone(), extra];
    let added_sources = DiscoverySourceInputs {
        traces: &added,
        ..correct_rom
    };
    assert!(
        solve_with_discovery_sources(&combined, &known, Scope::WholeRom, &added_sources).is_err()
    );
}
