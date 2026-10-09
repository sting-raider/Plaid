use plaid_core::{GuestAddr, discovery::*, program::*, solver::*};

fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "mapping-conflict".into(),
            generation: 7,
        },
        words: vec![0x0800_0000, 0],
        rom_offset: None,
        physical_start: None,
    }
}

fn closed_map(i: &CodeImage) -> ProgramMap {
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

fn region(template: &Region, start: u32, size: u32, physical_start: Option<u32>) -> Region {
    let mut out = template.clone();
    out.range = GuestRange {
        start: GuestAddr(start),
        size,
    };
    out.physical_start = physical_start.map(PhysicalAddr);
    out
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn same_executable_bytes_cannot_have_two_explicit_physical_backings() {
    let i = image();
    let mut m = closed_map(&i);
    let template = m.regions.first().unwrap().clone();
    m.regions.clear();
    m.regions
        .insert(region(&template, 0x8000_0000, 8, Some(0x0000_0000)));
    m.regions
        .insert(region(&template, 0x8000_0000, 8, Some(0x0000_1000)));

    // The contradiction is semantic, not a schema-shape error.
    m.validate().unwrap();
    let report = solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "ambiguous_executable_physical_mapping"));
}

#[test]
fn partial_guest_overlap_with_incompatible_affine_mapping_is_open() {
    let i = image();
    let mut m = closed_map(&i);
    let template = m.regions.first().unwrap().clone();
    m.regions.clear();
    m.regions
        .insert(region(&template, 0x8000_0000, 8, Some(0x0000_0000)));
    // Guest 0x8000_0004 maps to physical 0x0000_2000 here, but 0x0000_0004 above.
    m.regions
        .insert(region(&template, 0x8000_0004, 4, Some(0x0000_2000)));

    m.validate().unwrap();
    let report = solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "ambiguous_executable_physical_mapping"));
}

#[test]
fn overlapping_regions_with_the_same_affine_mapping_remain_closed() {
    let i = image();
    let mut m = closed_map(&i);
    let template = m.regions.first().unwrap().clone();
    m.regions.clear();
    m.regions
        .insert(region(&template, 0x8000_0000, 8, Some(0x0000_0000)));
    // Same backing relation over the overlap: 0x8000_0004 -> physical 0x0000_0004.
    m.regions
        .insert(region(&template, 0x8000_0004, 4, Some(0x0000_0004)));

    m.validate().unwrap();
    let report = solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "ambiguous_executable_physical_mapping"));
}

#[test]
fn unknown_or_disjoint_physical_mapping_is_not_fabricated_into_a_conflict() {
    let i = image();
    let template = closed_map(&i).regions.first().unwrap().clone();

    let mut unknown = closed_map(&i);
    unknown.regions.clear();
    unknown
        .regions
        .insert(region(&template, 0x8000_0000, 8, Some(0x0000_0000)));
    unknown
        .regions
        .insert(region(&template, 0x8000_0000, 8, None));
    unknown.validate().unwrap();
    let report = solve(
        &unknown,
        std::slice::from_ref(&i),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "ambiguous_executable_physical_mapping"));

    let mut disjoint = closed_map(&i);
    disjoint.regions.clear();
    disjoint
        .regions
        .insert(region(&template, 0x8000_0000, 8, Some(0x0000_0000)));
    disjoint
        .regions
        .insert(region(&template, 0x8000_1000, 8, Some(0x0000_2000)));
    disjoint.validate().unwrap();
    let report = solve(&disjoint, &[i], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "ambiguous_executable_physical_mapping"));
}
