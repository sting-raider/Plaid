use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, decode, direct_cfg},
    indirect::{analyze_indirect, verify_constant},
    program::{CodeAddress, ProgramMap, RomIdentity},
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "indirect-delay-slot-test".into(),
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
    report.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn local_closed_target_never_discharges_unsupported_delay_slot() {
    // Every case has a locally constant JR target back to the entry block.  The
    // final word varies only the JR delay slot.
    let cases = [
        ("teq", 0x0000_0034),
        ("syscall", 0x0000_000c),
        ("break", 0x0000_000d),
        ("eret", 0x4200_0018),
        ("nested_j", 0x0800_0000),
    ];

    for (name, slot) in cases {
        let image = image(vec![0x3c08_8000, 0x3508_0000, 0x0100_0008, slot]);
        let direct = map(&image);
        assert!(
            direct
                .unresolved
                .iter()
                .any(|u| u.kind == "unsupported_delay_slot"),
            "{name}: direct CFG must retain the delay-slot obligation"
        );

        let analyzed = analyze_indirect(&direct, &image).unwrap();
        let site = analyzed.indirect_sites.first().unwrap();
        assert!(site.closed_proof.is_some(), "{name}: target proof is target-only");
        assert!(verify_constant(&analyzed, &image, site), "{name}: proof rechecks");
        assert_eq!(site.candidates.first_key_value().unwrap().0.pc.0, 0x8000_0000);

        let report = solve(
            &analyzed,
            std::slice::from_ref(&image),
            Scope::DeclaredStaticImages,
        )
        .unwrap();
        assert_eq!(report.status, ClosureStatus::Open, "{name}: must not close");
        assert!(
            has(&report, "unsupported_delay_slot"),
            "{name}: closed target must not waive delay-slot blocker"
        );
    }
}

#[test]
fn changed_delay_slot_cannot_launder_a_preexisting_certificate_into_closure() {
    let clean = image(vec![0x3c08_8000, 0x3508_0000, 0x0100_0008, 0]);
    let analyzed = analyze_indirect(&map(&clean), &clean).unwrap();
    let site = analyzed.indirect_sites.first().unwrap();
    assert!(verify_constant(&analyzed, &clean, site));
    assert_eq!(
        solve(
            &analyzed,
            std::slice::from_ref(&clean),
            Scope::DeclaredStaticImages,
        )
        .unwrap()
        .status,
        ClosureStatus::Closed
    );

    // The certificate hash deliberately covers the value-producing prefix and
    // JR, not its slot.  Reusing that target certificate after slot mutation is
    // therefore allowed, but the solver must independently re-derive the slot
    // obligation from the supplied bytes.
    for (name, slot) in [("teq", 0x0000_0034), ("nested_j", 0x0800_0000)] {
        let mut changed = clean.clone();
        changed.words[3] = slot;
        assert!(
            verify_constant(&analyzed, &changed, site),
            "{name}: target itself is unchanged"
        );
        let report = solve(
            &analyzed,
            std::slice::from_ref(&changed),
            Scope::DeclaredStaticImages,
        )
        .unwrap();
        assert_eq!(report.status, ClosureStatus::Open, "{name}: stale map must not close");
        assert!(has(&report, "unsupported_delay_slot"));
    }
}

#[test]
fn cross_block_closed_target_never_discharges_final_delay_slot() {
    // LUI; J final; ORI in the J slot builds t0=0x80000000 across blocks.
    // The final JR then has an exceptional TEQ slot.
    let image = image(vec![
        0x3c08_8000,
        0x0800_0004,
        0x3508_0000,
        0,
        0x0100_0008,
        0x0000_0034,
    ]);
    let direct = map(&image);
    assert!(
        direct
            .unresolved
            .iter()
            .any(|u| u.kind == "unsupported_delay_slot")
    );
    let analyzed = analyze_indirect(&direct, &image).unwrap();
    let site = analyzed.indirect_sites.first().unwrap();
    let proof = site.closed_proof.as_ref().unwrap();
    assert_eq!(
        analyzed.evidence[proof].producer,
        "plaid-cross-block-constant/v0"
    );
    assert!(verify_constant(&analyzed, &image, site));
    assert_eq!(site.candidates.first_key_value().unwrap().0.pc.0, 0x8000_0000);

    let report = solve(
        &analyzed,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unsupported_delay_slot"));
}

#[test]
fn pinned_decoder_classification_and_normal_slot_control() {
    let teq = decode(0x0000_0034, GuestAddr(0x8000_000c));
    assert_eq!(teq.opcode_name(), "teq");
    assert!(teq.is_trap());
    let nested = decode(0x0800_0000, GuestAddr(0x8000_000c));
    assert!(nested.has_delay_slot());

    let image = image(vec![0x3c08_8000, 0x3508_0000, 0x0100_0008, 0]);
    let analyzed = analyze_indirect(&map(&image), &image).unwrap();
    let report = solve(
        &analyzed,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "unsupported_delay_slot"));
}
