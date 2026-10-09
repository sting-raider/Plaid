use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    merge::merge_maps,
    program::{CodeAddress, PhysicalAddr, ProgramMap, RomIdentity},
    solver::{ClosureStatus, Scope, solve},
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn image(name: &str, base: u32, generation: u64, physical: Option<u32>, delay_word: u32) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(base),
            image: name.into(),
            generation,
        },
        // J self; chosen delay-slot word is a non-memory ADDIU accepted by the
        // declared-static subset. Different delay words let the two aliases
        // carry contradictory bytes over one claimed physical backing span.
        words: vec![0x08000000, delay_word],
        rom_offset: None,
        physical_start: physical.map(PhysicalAddr),
    }
}

fn map(i: &CodeImage) -> ProgramMap {
    direct_cfg(rom(), i, &[i.base.pc], 100).unwrap().map
}

fn merge(a: &CodeImage, b: &CodeImage) -> ProgramMap {
    merge_maps(&map(a), &map(b)).unwrap()
}

#[test]
fn distinct_executable_identities_over_same_physical_backing_must_not_close() {
    let a = image("phys-a", 0x8000_0000, 0, Some(0), 0x2408_0001);
    let b = image("phys-b", 0xa000_0000, 0, Some(0), 0x2408_0002);

    assert_eq!(
        solve(&map(&a), std::slice::from_ref(&a), Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Closed
    );
    assert_eq!(
        solve(&map(&b), std::slice::from_ref(&b), Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Closed
    );

    let m = merge(&a, &b);
    m.validate().unwrap();
    let report = solve(&m, &[a, b], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(
        report.status,
        ClosureStatus::Open,
        "distinct executable identities with contradictory bytes share one explicit physical span but solver blockers were: {:#?}",
        report.blockers
    );
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "ambiguous_physical_executable_identity")
    );
}
