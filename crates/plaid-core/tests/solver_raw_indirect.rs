use plaid_core::{
    EvidenceKind, GuestAddr,
    discovery::{CodeImage, direct_cfg},
    indirect::analyze_indirect,
    program::{CodeAddress, Evidence, ObservedIndirect, RomIdentity},
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "solver-raw-indirect".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
    }
}

fn map(image: &CodeImage) -> plaid_core::program::ProgramMap {
    direct_cfg(
        RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        },
        image,
        &[image.base.pc],
        100,
    )
    .unwrap()
    .map
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|blocker| blocker.kind == kind)
}

fn insert_trace_evidence(map: &mut plaid_core::program::ProgramMap, id: &str, detail: &str) {
    map.evidence.insert(
        id.into(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: "solver-raw-indirect-test".into(),
            revision: "0".into(),
            detail: detail.into(),
        },
    );
}

fn insert_raw(
    map: &mut plaid_core::program::ProgramMap,
    id: &str,
    site: u32,
    target: u32,
    generation: u64,
    source_unit: Option<&str>,
) {
    insert_trace_evidence(
        map,
        id,
        "synthetic completed indirect transfer retained after correlation facts were removed",
    );
    map.indirect_observations.insert(ObservedIndirect {
        site: GuestAddr(site),
        target: GuestAddr(target),
        delay_slot_pc: Some(GuestAddr(site + 4)),
        generation,
        source_unit: source_unit.map(str::to_owned),
        evidence: [id.to_string()].into(),
    });
}

fn constant_jr() -> CodeImage {
    // lui t0,0x8000; ori t0,t0,0; jr t0; nop
    image(vec![0x3c08_8000, 0x3508_0000, 0x0100_0008, 0])
}

#[test]
fn unresolved_raw_indirect_execution_must_prevent_static_closure() {
    let image = image(vec![0x0800_0000, 0]); // j 0x80000000; nop
    let mut map = map(&image);
    insert_raw(
        &mut map,
        "trace:raw:1",
        0x9000_0000,
        0x9000_0010,
        7,
        None,
    );
    map.validate().unwrap();

    let report = solve(&map, std::slice::from_ref(&image), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_raw_indirect_execution"));
}

#[test]
fn uniquely_resolved_raw_observation_does_not_add_a_new_blocker() {
    let image = constant_jr();
    let mut map = analyze_indirect(&map(&image), &image).unwrap();
    let raw_id = "trace:raw:resolved";
    insert_raw(
        &mut map,
        raw_id,
        0x8000_0008,
        0x8000_0000,
        0,
        None,
    );

    let mut site = map.indirect_sites.pop_first().unwrap();
    site.observed
        .entry(image.base.clone())
        .or_default()
        .insert(raw_id.into());
    map.indirect_sites.insert(site);
    map.validate().unwrap();

    let report = solve(&map, std::slice::from_ref(&image), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "unresolved_raw_indirect_execution"));
}

#[test]
fn equal_guest_addresses_without_shared_observation_evidence_do_not_resolve_raw_execution() {
    // Same source/target PCs as the resolved case, but the raw event evidence is
    // not attached to the derived observed edge. Address equality is not provenance.
    let image = constant_jr();
    let mut map = analyze_indirect(&map(&image), &image).unwrap();
    insert_raw(
        &mut map,
        "trace:raw:decoy",
        0x8000_0008,
        0x8000_0000,
        0,
        None,
    );
    map.validate().unwrap();

    let report = solve(&map, std::slice::from_ref(&image), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_raw_indirect_execution"));
}

#[test]
fn implicit_source_generation_mismatch_cannot_borrow_equal_pc_target() {
    let image = constant_jr();
    let mut map = analyze_indirect(&map(&image), &image).unwrap();
    let raw_id = "trace:raw:generation-mismatch";
    insert_raw(
        &mut map,
        raw_id,
        0x8000_0008,
        0x8000_0000,
        9,
        None,
    );
    let mut site = map.indirect_sites.pop_first().unwrap();
    site.observed
        .entry(image.base.clone())
        .or_default()
        .insert(raw_id.into());
    map.indirect_sites.insert(site);

    let report = solve(&map, std::slice::from_ref(&image), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_raw_indirect_execution"));
}

#[test]
fn explicit_source_unit_can_identify_an_older_executing_generation() {
    let image = constant_jr();
    let mut map = analyze_indirect(&map(&image), &image).unwrap();
    let raw_id = "trace:raw:old-source";
    let unit_id = "trace:unit:old-source";
    insert_trace_evidence(&mut map, unit_id, "synthetic compile-begin identity");
    insert_raw(
        &mut map,
        raw_id,
        0x8000_0008,
        0x8000_0000,
        9,
        Some(unit_id),
    );
    let mut site = map.indirect_sites.pop_first().unwrap();
    site.evidence.insert(unit_id.into());
    site.observed
        .entry(image.base.clone())
        .or_default()
        .insert(raw_id.into());
    map.indirect_sites.insert(site);

    let report = solve(&map, std::slice::from_ref(&image), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "unresolved_raw_indirect_execution"));
}

#[test]
fn explicit_source_unit_must_be_bound_to_the_declared_source_site() {
    let image = constant_jr();
    let mut map = analyze_indirect(&map(&image), &image).unwrap();
    let raw_id = "trace:raw:wrong-source-unit";
    let unit_id = "trace:unit:wrong-source-unit";
    insert_trace_evidence(&mut map, unit_id, "synthetic unrelated compile-begin identity");
    insert_raw(
        &mut map,
        raw_id,
        0x8000_0008,
        0x8000_0000,
        9,
        Some(unit_id),
    );
    let mut site = map.indirect_sites.pop_first().unwrap();
    site.observed
        .entry(image.base.clone())
        .or_default()
        .insert(raw_id.into());
    map.indirect_sites.insert(site);

    let report = solve(&map, std::slice::from_ref(&image), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_raw_indirect_execution"));
}

#[test]
fn deleting_importers_uncorrelated_diagnostic_cannot_launder_raw_transfer() {
    use plaid_core::{
        merge::import_trace,
        program::{PhysicalAddr, RomOffset},
        trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
    };

    let mut image = constant_jr();
    image.rom_offset = Some(RomOffset(64));
    image.physical_start = Some(PhysicalAddr(0));
    let mut trace = DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: RomIdentity {
                sha256: "a".repeat(64),
                size: 4096,
            },
            engine: "solver-raw-indirect-test".into(),
            revision: "pin".into(),
            capabilities: Default::default(),
        },
        events: vec![
            EventRecord {
                seq: 0,
                data: TraceEvent::CompileBegin {
                    unit: 0,
                    start: image.base.pc,
                    physical_start: image.physical_start,
                    delay_slot_entry: false,
                },
            },
            EventRecord {
                seq: 1,
                data: TraceEvent::EntryInstalled {
                    unit: 0,
                    pc: image.base.pc,
                    register_mask: 0,
                },
            },
            EventRecord {
                seq: 2,
                data: TraceEvent::UnitCompiled {
                    unit: 0,
                    start: image.base.pc,
                    words: image.words.clone(),
                },
            },
        ],
    };
    trace.events.push(EventRecord {
        seq: 3,
        data: TraceEvent::IndirectTargetObserved {
            site: GuestAddr(0x8000_0008),
            target: GuestAddr(0x9000_0000),
            delay_slot_pc: Some(GuestAddr(0x8000_000c)),
            source_unit: Some(0),
        },
    });

    let imported = import_trace(&trace, std::slice::from_ref(&image), 100).unwrap();
    assert_eq!(imported.indirect_observations.len(), 1);
    assert!(
        imported
            .unresolved
            .iter()
            .any(|u| u.kind == "uncorrelated_indirect_observation")
    );

    let mut laundered = analyze_indirect(&imported, &image).unwrap();
    laundered
        .unresolved
        .retain(|u| u.kind != "uncorrelated_indirect_observation");
    assert!(laundered.unresolved.is_empty());

    let report = solve(
        &laundered,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_raw_indirect_execution"));
}
