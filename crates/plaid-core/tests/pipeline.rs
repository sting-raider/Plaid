use plaid_core::{GuestAddr, discovery::CodeImage, pipeline::*, program::*, solver::*};

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "pipeline".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
    }
}
fn run(i: &CodeImage) -> plaid_core::discovery::Discovery {
    discover_image(
        RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        },
        i,
        &[i.base.pc],
        100,
    )
    .unwrap()
}

#[test]
fn inferred_target_is_recursively_discovered_and_scope_can_close() {
    let i = image(vec![
        0x3c088000, 0x35080020, 0x01000008, 0, 0, 0, 0, 0, 0x08000008, 0,
    ]);
    let d = run(&i);
    assert!(d.map.blocks.iter().any(|b| b.start.pc.0 == 0x80000020));
    assert!(d.words.keys().any(|a| a.pc.0 == 0x80000020));
    assert_eq!(
        solve(
            &d.map,
            std::slice::from_ref(&i),
            Scope::DeclaredStaticImages
        )
        .unwrap()
        .status,
        ClosureStatus::Closed
    );
    assert_eq!(d.map.to_json().unwrap(), run(&i).map.to_json().unwrap());
}

#[test]
fn reentry_repartitions_blocks_and_retains_candidate_provenance() {
    let i = image(vec![0x3c088000, 0x35080004, 0x01000008, 0]);
    let d = run(&i);
    assert!(d.map.blocks.iter().any(|b| b.start.pc.0 == 0x80000004));
    let site = d.map.indirect_sites.first().unwrap();
    assert_eq!(site.candidates.len(), 1);
    assert!(site.closed_proof.is_none());
    assert!(
        site.candidates
            .values()
            .flatten()
            .all(|id| d.map.evidence.contains_key(id))
    );
    assert_eq!(
        solve(&d.map, &[i], Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Open
    );
}

#[test]
fn external_candidates_remain_unresolved() {
    let i = image(vec![0x3c088000, 0x35080100, 0x01000008, 0]);
    let d = run(&i);
    assert!(
        solve(&d.map, &[i], Scope::DeclaredStaticImages)
            .unwrap()
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_indirect_target")
    );
}

#[test]
fn cross_block_target_traversal_and_solver_rechecking_work_together() {
    let mut words = vec![0; 18];
    words[..6].copy_from_slice(&[0x3c088000, 0x08000004, 0x35080040, 0, 0x01000008, 0]);
    words[16] = 0x08000010;
    let i = image(words);
    let d = run(&i);
    assert!(d.map.blocks.iter().any(|b| b.start.pc.0 == 0x80000040));
    assert_eq!(
        solve(
            &d.map,
            std::slice::from_ref(&i),
            Scope::DeclaredStaticImages
        )
        .unwrap()
        .status,
        ClosureStatus::Closed
    );
    let mut missing = d.map;
    missing.direct_edges.retain(|e| e.site.pc.0 != 0x80000004);
    let report = solve(&missing, &[i], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_indirect_site")
    );
}
