use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    merge::merge_maps,
    program::{CodeAddress, RomIdentity},
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn fragment(base: u32, image: &str, generation: u64, words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(base),
            image: image.into(),
            generation,
        },
        words,
        rom_offset: None,
        physical_start: None,
    }
}

fn discovered(image: &CodeImage) -> plaid_core::program::ProgramMap {
    direct_cfg(rom(), image, &[image.base.pc], 100).unwrap().map
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn split_image_jump_requires_cross_fragment_edge_even_when_target_block_exists() {
    // j 0x80000010; nop
    let source = fragment(0x8000_0000, "split", 0, vec![0x0800_0004, 0]);
    // j 0x80000010; nop (closed self-loop target fragment)
    let target = fragment(0x8000_0010, "split", 0, vec![0x0800_0004, 0]);
    let mut map = merge_maps(&discovered(&source), &discovered(&target)).unwrap();
    let images = [source.clone(), target.clone()];

    let baseline = solve(&map, &images, Scope::DeclaredStaticImages).unwrap();
    assert_eq!(baseline.status, ClosureStatus::Closed);
    assert!(!has(&baseline, "unmapped_target"));

    map.direct_edges.retain(|edge| {
        !(edge.site == source.base
            && edge.target == target.base
            && edge.kind == plaid_core::program::EdgeKind::Jump)
    });
    let attacked = solve(&map, &images, Scope::DeclaredStaticImages).unwrap();
    assert_eq!(attacked.status, ClosureStatus::Open);
    assert!(has(&attacked, "missing_decoded_edge"));
}

#[test]
fn equal_payload_different_generation_target_cannot_discharge_split_jump() {
    // The source instruction still names generation 0 because direct CFG identity
    // follows the source image. An equal-byte target fragment in generation 1 is
    // deliberately not a substitute for that CodeAddress identity.
    let source = fragment(0x8000_0000, "split", 0, vec![0x0800_0004, 0]);
    let target_decoy = fragment(0x8000_0010, "split", 1, vec![0x0800_0004, 0]);
    let map = merge_maps(&discovered(&source), &discovered(&target_decoy)).unwrap();
    let report = solve(
        &map,
        &[source, target_decoy],
        Scope::DeclaredStaticImages,
    )
    .unwrap();

    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_direct_target"));
    assert!(has(&report, "unmapped_target"));
}

#[test]
fn split_image_fallthrough_requires_cross_fragment_edge() {
    // addiu t0,zero,1 at the final word forces a fallthrough into the next
    // non-overlapping fragment.
    let source = fragment(0x8000_0000, "split", 0, vec![0x2408_0001]);
    // j 0x80000004; nop
    let target = fragment(0x8000_0004, "split", 0, vec![0x0800_0001, 0]);
    let mut map = merge_maps(&discovered(&source), &discovered(&target)).unwrap();
    let images = [source.clone(), target.clone()];

    assert_eq!(
        solve(&map, &images, Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Closed
    );

    map.direct_edges.retain(|edge| edge.site != source.base);
    let attacked = solve(&map, &images, Scope::DeclaredStaticImages).unwrap();
    assert_eq!(attacked.status, ClosureStatus::Open);
    assert!(has(&attacked, "missing_decoded_edge"));
}
