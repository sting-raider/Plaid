use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    program::{CodeAddress, ExecutableWrite, ProgramMap, RomIdentity, WriteKind},
    solver::{ClosureStatus, Scope, solve},
};

fn image(generation: u64) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "static-generation-test".into(),
            generation,
        },
        // j 0x80000000; nop
        words: vec![0x0800_0000, 0],
        rom_offset: None,
        physical_start: None,
    }
}

fn map(i: &CodeImage) -> ProgramMap {
    direct_cfg(
        RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        },
        i,
        &[i.base.pc],
        100,
    )
    .unwrap()
    .map
}

fn combine(mut left: ProgramMap, right: ProgramMap) -> ProgramMap {
    assert_eq!(left.rom, right.rom);
    left.evidence.extend(right.evidence);
    left.regions.extend(right.regions);
    left.blocks.extend(right.blocks);
    left.entries.extend(right.entries);
    left.direct_edges.extend(right.direct_edges);
    left.indirect_sites.extend(right.indirect_sites);
    left.unresolved.extend(right.unresolved);
    left
}

fn has(report: &plaid_core::solver::SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn nonzero_generation_is_an_identity_label_not_transition_evidence() {
    let i = image(7);
    let m = map(&i);
    m.validate().unwrap();

    let report = solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(report.blockers.is_empty());
}

#[test]
fn two_generations_can_be_independent_declared_static_roots() {
    let i0 = image(0);
    let i1 = image(9);
    let m = combine(map(&i0), map(&i1));
    m.validate().unwrap();

    let report = solve(&m, &[i0.clone(), i1.clone()], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(report.blockers.is_empty());

    // Whole-ROM semantics are unchanged: these finite declared roots do not
    // establish the executable universe or any runtime lifetime relation.
    assert_eq!(
        solve(&m, &[i0, i1], Scope::WholeRom).unwrap().status,
        ClosureStatus::Open
    );
}

#[test]
fn explicit_transition_like_mutation_evidence_still_blocks_static_scope() {
    let i0 = image(0);
    let i1 = image(9);
    let mut m = combine(map(&i0), map(&i1));
    let evidence = m.regions.first().unwrap().evidence.clone();
    m.executable_writes.insert(ExecutableWrite {
        range: None,
        kind: WriteKind::OverlayReload,
        evidence,
    });
    m.validate().unwrap();

    let report = solve(&m, &[i0, i1], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_executable_write"));
}

#[test]
fn inert_region_generation_metadata_is_not_execution_evidence() {
    let i = image(0);
    let mut m = map(&i);
    let mut inert = m.regions.first().unwrap().clone();
    inert.generation = 123;
    m.regions.insert(inert);
    m.validate().unwrap();

    let report = solve(&m, &[i], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(report.blockers.is_empty());
}
