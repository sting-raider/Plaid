use plaid_core::{GuestAddr, discovery::*, program::*, solver::*};

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "solver-rsp-microcode-test".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
    }
}

fn map(image: &CodeImage) -> ProgramMap {
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

fn microcode(byte: char, imem_start: u16, evidence: EvidenceRefs) -> Microcode {
    Microcode {
        sha256: byte.to_string().repeat(64),
        imem_start,
        size: 8,
        evidence,
    }
}

#[test]
fn retained_rsp_microcode_recreates_static_scope_blocker_after_diagnostic_deletion() {
    let image = image(vec![0x08000000, 0]);
    let mut map = map(&image);
    let baseline = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(baseline.status, ClosureStatus::Closed);
    assert!(!has(&baseline, "dynamic_effect_outside_scope"));

    let evidence = map.blocks.first().unwrap().evidence.clone();
    map.rsp_microcodes
        .insert(microcode('b', 0x000, evidence.clone()));
    map.unresolved.clear();

    let report = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "dynamic_effect_outside_scope"));

    // Equal payload cannot collapse a second RSP executable fact into static scope.
    map.rsp_microcodes.insert(microcode('b', 0x100, evidence));
    map.unresolved.clear();
    let report = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "dynamic_effect_outside_scope"));
}

#[test]
fn whole_rom_keeps_rsp_policy_open_independently() {
    let image = image(vec![0x08000000, 0]);
    let mut map = map(&image);
    let evidence = map.blocks.first().unwrap().evidence.clone();
    map.rsp_microcodes.insert(microcode('c', 0, evidence));
    map.unresolved.clear();

    let report = solve(&map, &[image], Scope::WholeRom).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unproven_rsp_policy"));
}

#[test]
fn malformed_rsp_microcode_is_rejected_before_closure() {
    let image = image(vec![0x08000000, 0]);
    let mut map = map(&image);
    let evidence = map.blocks.first().unwrap().evidence.clone();
    map.rsp_microcodes.insert(Microcode {
        sha256: "d".repeat(64),
        imem_start: 4092,
        size: 8,
        evidence,
    });
    map.unresolved.clear();

    let error = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap_err();
    assert!(error.contains("invalid RSP IMEM range"));
}
