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

fn insert_raw(
    map: &mut plaid_core::program::ProgramMap,
    id: &str,
    site: u32,
    target: u32,
    generation: u64,
) {
    map.evidence.insert(
        id.into(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: "solver-raw-indirect-test".into(),
            revision: "0".into(),
            detail: "synthetic completed indirect transfer retained after correlation facts were removed"
                .into(),
        },
    );
    map.indirect_observations.insert(ObservedIndirect {
        site: GuestAddr(site),
        target: GuestAddr(target),
        delay_slot_pc: Some(GuestAddr(site + 4)),
        generation,
        source_unit: None,
        evidence: [id.to_string()].into(),
    });
}

#[test]
fn unresolved_raw_indirect_execution_must_prevent_static_closure() {
    let image = image(vec![0x0800_0000, 0]); // j 0x80000000; nop
    let mut map = map(&image);
    insert_raw(&mut map, "trace:raw:1", 0x9000_0000, 0x9000_0010, 7);
    map.validate().unwrap();

    let report = solve(&map, std::slice::from_ref(&image), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_raw_indirect_execution"));
}

#[test]
fn uniquely_resolved_raw_observation_does_not_add_a_new_blocker() {
    // lui t0,0x8000; ori t0,t0,0; jr t0; nop
    let image = image(vec![0x3c08_8000, 0x3508_0000, 0x0100_0008, 0]);
    let mut map = analyze_indirect(&map(&image), &image).unwrap();
    let raw_id = "trace:raw:resolved";
    insert_raw(&mut map, raw_id, 0x8000_0008, 0x8000_0000, 0);

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
    let image = image(vec![0x3c08_8000, 0x3508_0000, 0x0100_0008, 0]);
    let mut map = analyze_indirect(&map(&image), &image).unwrap();
    insert_raw(&mut map, "trace:raw:decoy", 0x8000_0008, 0x8000_0000, 0);
    map.validate().unwrap();

    let report = solve(&map, std::slice::from_ref(&image), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_raw_indirect_execution"));
}
