use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    merge::merge_maps,
    program::{CodeAddress, GuestRange, PhysicalAddr, ProgramMap, Region, RomIdentity, RomOffset},
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "region-provenance-test".into(),
            generation: 7,
        },
        words: vec![0x0800_0000, 0], // J self; NOP delay slot
        rom_offset: Some(RomOffset(0)),
        physical_start: Some(PhysicalAddr(0x1000)),
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

fn extra_region(
    map: &ProgramMap,
    start: u32,
    size: u32,
    rom_offset: Option<u64>,
    physical_start: Option<u32>,
) -> Region {
    Region {
        image: "region-provenance-test".into(),
        generation: 7,
        range: GuestRange {
            start: GuestAddr(start),
            size,
        },
        rom_offset: rom_offset.map(RomOffset),
        physical_start: physical_start.map(PhysicalAddr),
        overlay: None,
        evidence: map.regions.first().unwrap().evidence.clone(),
    }
}

fn report(map: &ProgramMap, image: &CodeImage) -> SolveReport {
    map.validate().unwrap();
    solve(map, std::slice::from_ref(image), Scope::DeclaredStaticImages).unwrap()
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn conflicting_rom_mapping_for_same_identity_must_not_close() {
    let image = image();
    let mut map = map(&image);
    map.regions
        .insert(extra_region(&map, 0x8000_0000, 8, Some(64), Some(0x1000)));

    let report = report(&map, &image);
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "conflicting_region_provenance"));
}

#[test]
fn conflicting_physical_mapping_for_same_identity_must_not_close() {
    let image = image();
    let mut map = map(&image);
    map.regions
        .insert(extra_region(&map, 0x8000_0000, 8, Some(0), Some(0x2000)));

    let report = report(&map, &image);
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "conflicting_region_provenance"));
}

#[test]
fn partially_overlapping_affine_disagreement_must_not_close() {
    let image = image();
    let mut map = map(&image);
    // At guest 0x8000_0004 the canonical row implies ROM+4 / physical+4.
    // This row deliberately claims ROM+8 / physical+8 instead.
    map.regions.insert(extra_region(
        &map,
        0x8000_0004,
        4,
        Some(8),
        Some(0x1008),
    ));

    let report = report(&map, &image);
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "conflicting_region_provenance"));
}

#[test]
fn consistent_partial_overlap_and_unknown_metadata_are_not_false_blockers() {
    let image = image();

    let mut consistent = map(&image);
    consistent.regions.insert(extra_region(
        &consistent,
        0x8000_0004,
        4,
        Some(4),
        Some(0x1004),
    ));
    assert_eq!(report(&consistent, &image).status, ClosureStatus::Closed);

    let mut unknown = map(&image);
    unknown
        .regions
        .insert(extra_region(&unknown, 0x8000_0004, 4, None, None));
    assert_eq!(report(&unknown, &image).status, ClosureStatus::Closed);
}

#[test]
fn disjoint_same_identity_regions_are_not_a_conflict() {
    let image = image();
    let mut map = map(&image);
    map.regions.insert(extra_region(
        &map,
        0x8000_1000,
        4,
        Some(128),
        Some(0x3000),
    ));
    assert_eq!(report(&map, &image).status, ClosureStatus::Closed);
}

#[test]
fn merge_order_cannot_launder_same_identity_provenance_conflict() {
    let image = image();
    let left = map(&image);
    let mut right = left.clone();
    right.regions.clear();
    right
        .regions
        .insert(extra_region(&left, 0x8000_0000, 8, Some(64), Some(0x2000)));
    right.validate().unwrap();

    for merged in [merge_maps(&left, &right).unwrap(), merge_maps(&right, &left).unwrap()] {
        let report = report(&merged, &image);
        assert_eq!(report.status, ClosureStatus::Open);
        assert!(has(&report, "conflicting_region_provenance"));
    }
}
