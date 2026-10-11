use plaid_core::{GuestAddr, discovery::*, program::*, solver::*};

fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "region-physical-span".into(),
            generation: 0,
        },
        words: vec![0x08000000, 0],
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

fn with_physical_start(mut map: ProgramMap, physical_start: Option<u32>) -> ProgramMap {
    let mut region = map.regions.pop_first().unwrap();
    region.physical_start = physical_start.map(PhysicalAddr);
    map.regions.insert(region);
    map
}

fn closed(map: &ProgramMap, image: &CodeImage) -> bool {
    solve(
        map,
        std::slice::from_ref(image),
        Scope::DeclaredStaticImages,
    )
    .is_ok_and(|report| report.status == ClosureStatus::Closed)
}

#[test]
fn executable_region_physical_span_cannot_cross_u32_namespace() {
    let i = image();
    let map = with_physical_start(map(&i), Some(0xffff_fffc));

    assert!(
        map.validate().is_err(),
        "explicit 8-byte physical span starting at 0xffff_fffc must not wrap past 2^32"
    );
    assert!(
        solve(&map, &[i], Scope::DeclaredStaticImages).is_err(),
        "solver must reject malformed physical backing before considering closure"
    );
}

#[test]
fn exactly_ending_physical_span_remains_valid_and_closed() {
    let i = image();
    let map = with_physical_start(map(&i), Some(0xffff_fff8));

    assert!(map.validate().is_ok());
    assert!(closed(&map, &i));
}

#[test]
fn ordinary_low_physical_span_remains_valid_and_closed() {
    let i = image();
    let map = with_physical_start(map(&i), Some(0x0010_0000));

    assert!(map.validate().is_ok());
    assert!(closed(&map, &i));
}

#[test]
fn absent_physical_mapping_remains_valid_and_closed() {
    let i = image();
    let map = with_physical_start(map(&i), None);

    assert!(map.validate().is_ok());
    assert!(closed(&map, &i));
}
