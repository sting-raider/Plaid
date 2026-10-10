use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    program::{CodeAddress, ProgramMap, RomIdentity},
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn image(base_pc: u32, image: &str, generation: u64, words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(base_pc),
            image: image.into(),
            generation,
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

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|blocker| blocker.kind == kind)
}

fn primary() -> CodeImage {
    // ADDIU t0,zero,1; ADDIU t1,zero,2; J 0x80000000; NOP.
    // direct_cfg produces one normal block rooted at 0x80000000.  The second
    // instruction is deliberately interior to that block.
    image(
        0x80000000,
        "opaque-overlap-test",
        7,
        vec![0x24080001, 0x24090002, 0x08000000, 0],
    )
}

#[test]
fn conflicting_interior_fragment_must_fail_closed() {
    let primary = primary();
    let map = map(&primary);
    let baseline = solve(
        &map,
        std::slice::from_ref(&primary),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(baseline.status, ClosureStatus::Closed);

    // Same opaque execution identity and same interior PC, but different bytes.
    // This fragment does not contain the block/entry root at 0x80000000.
    let conflicting = image(0x80000004, "opaque-overlap-test", 7, vec![0x24090003]);
    let report = solve(
        &map,
        &[primary.clone(), conflicting],
        Scope::DeclaredStaticImages,
    )
    .unwrap();

    assert_eq!(report.status, ClosureStatus::Open, "{report:#?}");
    assert!(
        has(&report, "conflicting_instruction_sources"),
        "{report:#?}"
    );
}

#[test]
fn equal_interior_fragment_is_not_a_conflict() {
    let primary = primary();
    let map = map(&primary);
    let equal = image(0x80000004, "opaque-overlap-test", 7, vec![0x24090002]);
    let report = solve(&map, &[primary, equal], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed, "{report:#?}");
    assert!(!has(&report, "conflicting_instruction_sources"));
}

#[test]
fn different_execution_identity_does_not_create_same_identity_conflict() {
    let primary = primary();
    let map = map(&primary);

    for decoy in [
        image(0x80000004, "different-image", 7, vec![0x24090003]),
        image(0x80000004, "opaque-overlap-test", 8, vec![0x24090003]),
    ] {
        let report = solve(&map, &[primary.clone(), decoy], Scope::DeclaredStaticImages).unwrap();
        assert_eq!(report.status, ClosureStatus::Closed, "{report:#?}");
        assert!(!has(&report, "conflicting_instruction_sources"));
    }
}

#[test]
fn conflict_covering_block_start_is_already_ambiguous() {
    let primary = primary();
    let map = map(&primary);
    let conflicting = image(0x80000000, "opaque-overlap-test", 7, vec![0x24080009]);
    let report = solve(&map, &[primary, conflicting], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open, "{report:#?}");
    assert!(has(&report, "missing_instruction_source"), "{report:#?}");
}
