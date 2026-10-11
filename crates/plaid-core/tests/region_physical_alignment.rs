use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    program::{CodeAddress, PhysicalAddr, ProgramMap, RomIdentity},
    solver::{ClosureStatus, Scope, solve},
};

fn image(physical_start: Option<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
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
        let i = image(None);
        let mut m = map(&i);
        let mut region = m.regions.iter().next().cloned().unwrap();
        m.regions.clear();
        region.physical_start = Some(PhysicalAddr(physical));
        m.regions.insert(region);

        assert_eq!(
            m.validate().unwrap_err(),
            "unaligned executable physical mapping"
        );
        assert_eq!(
            solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap_err(),
            "unaligned executable physical mapping"
        );
    }
}

#[test]
fn aligned_and_absent_physical_code_mappings_remain_valid() {
    for physical in [None, Some(0), Some(4), Some(0xffff_fff8)] {
        let i = image(physical);
        let m = map(&i);
        m.validate().unwrap();
        let report = solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap();
        assert_eq!(report.status, ClosureStatus::Closed);
    }
}
