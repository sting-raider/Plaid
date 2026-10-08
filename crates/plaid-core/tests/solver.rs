use plaid_core::{GuestAddr, discovery::*, indirect::analyze_indirect, program::*, solver::*};

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "solver-test".into(),
            generation: 0,
        },
        words,
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
fn has(r: &SolveReport, kind: &str) -> bool {
    r.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn finite_synthetic_cfg_can_close_only_under_explicit_scope() {
    let i = image(vec![0x08000000, 0]);
    let m = map(&i);
    let r = solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(r.status, ClosureStatus::Closed);
    assert!(!r.native_complete);
    assert!(!r.assumptions.is_empty());
    let r = solve(&m, &[i], Scope::WholeRom).unwrap();
    assert_eq!(r.status, ClosureStatus::Open);
    assert!(has(&r, "unproven_executable_universe"));
    assert!(has(&r, "unmodeled_exception_paths"));
}

#[test]
fn finite_indirect_observations_and_missing_bytes_fail_closed() {
    let i = image(vec![0x03e00008, 0]);
    let mut m = map(&i);
    let mut s = m.indirect_sites.pop_first().unwrap();
    s.observed.insert(i.base.clone(), s.evidence.clone());
    m.indirect_sites.insert(s);
    let r = solve(&m, &[i], Scope::DeclaredStaticImages).unwrap();
    assert!(has(&r, "unresolved_indirect_site"));
    assert!(has(&r, "indirect_evidence_disagreement"));
    assert!(has(
        &solve(&m, &[], Scope::WholeRom).unwrap(),
        "missing_instruction_source"
    ));
}

#[test]
fn rechecked_constant_target_requires_discovered_destination_block() {
    let i = image(vec![0x3c088000, 0x35080000, 0x01000008, 0]);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert_eq!(
        solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Closed
    );
    let mut changed = i.clone();
    changed.words[1] = 0x35080020;
    assert!(has(
        &solve(&m, &[changed], Scope::DeclaredStaticImages).unwrap(),
        "unresolved_indirect_site"
    ));
    let i = image(vec![0x3c088000, 0x35080020, 0x01000008, 0]);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert!(has(
        &solve(&m, &[i], Scope::DeclaredStaticImages).unwrap(),
        "unresolved_indirect_target"
    ));
}

#[test]
fn deleting_control_facts_cannot_manufacture_closure() {
    let i = image(vec![0x08000000, 0]);
    let mut m = map(&i);
    m.direct_edges.clear();
    assert!(has(
        &solve(&m, &[i], Scope::DeclaredStaticImages).unwrap(),
        "missing_decoded_edge"
    ));
    let i = image(vec![0x03e00008, 0]);
    let mut m = map(&i);
    m.indirect_sites.clear();
    assert!(has(
        &solve(&m, &[i], Scope::DeclaredStaticImages).unwrap(),
        "missing_decoded_indirect_site"
    ));
}

#[test]
fn exceptions_writes_and_empty_maps_are_blockers() {
    let i = image(vec![0x0000000c]);
    let mut m = map(&i);
    let refs = m.blocks.first().unwrap().evidence.clone();
    m.executable_writes.insert(ExecutableWrite {
        range: None,
        kind: WriteKind::Unknown,
        evidence: refs,
    });
    let r = solve(&m, &[i], Scope::DeclaredStaticImages).unwrap();
    assert!(has(&r, "exception_or_unsupported_instruction"));
    assert!(has(&r, "unresolved_executable_write"));
    let empty = ProgramMap::new(m.rom);
    assert!(has(
        &solve(&empty, &[], Scope::DeclaredStaticImages).unwrap(),
        "missing_entry_universe"
    ));
}

#[test]
fn conflicting_or_fabricated_extra_facts_cannot_close() {
    let i = image(vec![0x08000000, 0]);
    let mut m = map(&i);
    let mut b = m.blocks.first().unwrap().clone();
    b.size = 4;
    m.blocks.insert(b);
    assert!(has(
        &solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap(),
        "unexpected_block_extent"
    ));
    let mut m = map(&i);
    let mut e = m.direct_edges.first().unwrap().clone();
    e.kind = EdgeKind::Call;
    m.direct_edges.insert(e);
    assert!(has(
        &solve(&m, &[i], Scope::DeclaredStaticImages).unwrap(),
        "unexpected_decoded_edge"
    ));
}
