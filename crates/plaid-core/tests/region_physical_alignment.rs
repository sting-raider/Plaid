use plaid_core::{
    GuestAddr, PhysicalAddr,
    discovery::{CodeImage, direct_cfg},
    program::{ProgramMap, RomIdentity},
    solver::{ClosureStatus, Scope, solve},
};

fn image(physical_start: Option<u32>) -> CodeImage {
    CodeImage {
        base: plaid_core::program::CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "region-physical-alignment".into(),
            generation: 0,
        },
        words: vec![0x0800_0000, 0],
        rom_offset: None,
        physical_start: physical_start.map(PhysicalAddr),
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

#[test]
fn unaligned_explicit_physical_code_mapping_is_rejected() {
    for physical in [1, 2, 3] {
        let i = image(Some(physical));
        let m = map(&i);
        assert!(
            m.validate().is_err(),
            "physical_start={physical:#010x} unexpectedly passed ProgramMap validation"
        );
        assert!(
            solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).is_err(),
            "physical_start={physical:#010x} unexpectedly reached a solver report"
        );
    }
}

#[test]
fn aligned_and_absent_physical_code_mappings_remain_valid() {
    for physical in [None, Some(0), Some(4), Some(0xffff_fff8)] {
        let i = image(physical);
        let m = map(&i);
        m.validate().unwrap();
        let report = solve(
            &m,
            std::slice::from_ref(&i),
            Scope::DeclaredStaticImages,
        )
        .unwrap();
        assert_eq!(report.status, ClosureStatus::Closed);
    }
}
