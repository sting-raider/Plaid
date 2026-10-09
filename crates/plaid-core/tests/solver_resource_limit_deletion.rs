use plaid_core::{
    GuestAddr,
    discovery::CodeImage,
    pipeline::discover_image,
    program::{CodeAddress, RomIdentity},
    solver::{ClosureStatus, Scope, solve},
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "resource-limit".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
    }
}

fn without_resource_limit(
    mut map: plaid_core::program::ProgramMap,
) -> plaid_core::program::ProgramMap {
    map.unresolved.retain(|u| u.kind != "resource_limit");
    map
}

#[test]
fn deleting_direct_cfg_resource_limit_cannot_manufacture_closure() {
    // NOP; J 0x80000004; NOP. With budget=1 only the first instruction is
    // retained. A complete pass is otherwise a finite closed static loop.
    let i = image(vec![0x0000_0000, 0x0800_0001, 0x0000_0000]);
    let limited = discover_image(rom(), &i, &[i.base.pc], 1).unwrap();
    assert!(
        limited
            .map
            .unresolved
            .iter()
            .any(|u| u.kind == "resource_limit" && u.site.is_some())
    );

    let edited = without_resource_limit(limited.map);
    let report = solve(
        &edited,
        std::slice::from_ref(&i),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(!report.blockers.iter().any(|b| b.kind == "resource_limit"));
    assert!(report.blockers.iter().any(|b| {
        matches!(
            b.kind.as_str(),
            "missing_decoded_block" | "missing_decoded_edge" | "unexpected_block_extent"
        )
    }));

    let complete = discover_image(rom(), &i, &[i.base.pc], 16).unwrap();
    assert!(
        !complete
            .map
            .unresolved
            .iter()
            .any(|u| u.kind == "resource_limit")
    );
    assert_eq!(
        solve(
            &complete.map,
            std::slice::from_ref(&i),
            Scope::DeclaredStaticImages,
        )
        .unwrap()
        .status,
        ClosureStatus::Closed
    );
}

#[test]
fn inferred_target_survives_direct_limit_and_keeps_deleted_limit_open() {
    // LUI/ORI/JR infers 0x80000020. Budget=3 completes the source block and
    // learns that candidate, then the next fixed-point pass exhausts the direct
    // instruction budget before traversing the target block.
    let i = image(vec![
        0x3c08_8000,
        0x3508_0020,
        0x0100_0008,
        0x0000_0000,
        0,
        0,
        0,
        0,
        0x0800_0008,
        0x0000_0000,
    ]);
    let limited = discover_image(rom(), &i, &[i.base.pc], 3).unwrap();
    let site = limited
        .map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x8000_0008)
        .expect("source indirect site retained");
    assert!(site.candidates.keys().any(|a| a.pc.0 == 0x8000_0020));
    assert!(
        limited
            .map
            .unresolved
            .iter()
            .any(|u| u.kind == "resource_limit" && u.site.is_some())
    );

    let edited = without_resource_limit(limited.map);
    let report = solve(
        &edited,
        std::slice::from_ref(&i),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(!report.blockers.iter().any(|b| b.kind == "resource_limit"));
    assert!(report.blockers.iter().any(|b| {
        matches!(
            b.kind.as_str(),
            "unresolved_indirect_target" | "missing_decoded_block" | "missing_decoded_edge"
        )
    }));
}

fn indirect_chain(stages: usize) -> CodeImage {
    assert!(stages >= 2);
    let mut words = vec![0u32; stages * 4];
    for stage in 0..(stages - 1) {
        let next = ((stage + 1) * 0x10) as u16;
        let at = stage * 4;
        words[at] = 0x3c08_8000; // LUI t0, 0x8000
        words[at + 1] = 0x3508_0000 | u32::from(next); // ORI t0,t0,next
        words[at + 2] = 0x0100_0008; // JR t0
        words[at + 3] = 0;
    }
    let last = (stages - 1) * 4;
    let target_field = (((stages - 1) * 0x10) >> 2) as u32;
    words[last] = 0x0800_0000 | target_field; // J last-stage start
    words[last + 1] = 0;
    image(words)
}

#[test]
fn chained_indirect_roots_hit_direct_budget_before_outer_fixed_point_limit() {
    // This attacks the apparently separate outer fixed-point resource-limit row.
    // Across budgets below and above convergence, every actual resource-limit
    // emitted by this multi-pass chain is the direct-CFG form (site=Some). The
    // fixed-point form (site=None) never appears: each external root adds decoded
    // instructions, so the shared instruction budget becomes the tighter bound.
    let i = indirect_chain(8);
    let mut saw_limit = false;
    let mut saw_converged = false;
    for budget in 1..=32 {
        let d = discover_image(rom(), &i, &[i.base.pc], budget).unwrap();
        let limits: Vec<_> = d
            .map
            .unresolved
            .iter()
            .filter(|u| u.kind == "resource_limit")
            .collect();
        if limits.is_empty() {
            saw_converged = true;
        } else {
            saw_limit = true;
            assert!(
                limits.iter().all(|u| u.site.is_some()),
                "outer fixed-point limit unexpectedly reachable at budget {budget}: {limits:?}"
            );
        }
    }
    assert!(saw_limit);
    assert!(saw_converged);
}
