use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    program::{CodeAddress, PhysicalAddr, ProgramMap, RomIdentity, RomOffset},
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "supplied-image-provenance-test".into(),
            generation: 7,
        },
        // J 0x8000_0000; NOP. Both are allowed in DeclaredStaticImages.
        words: vec![0x0800_0000, 0],
        rom_offset: Some(RomOffset(0x100)),
        physical_start: Some(PhysicalAddr(0x1000)),
    }
}

fn map(image: &CodeImage) -> ProgramMap {
    direct_cfg(
        RomIdentity {
            sha256: "a".repeat(64),
            size: 0x1000,
        },
        image,
        &[image.base.pc],
        32,
    )
    .unwrap()
    .map
}

fn report(map: &ProgramMap, image: &CodeImage) -> SolveReport {
    map.validate().unwrap();
    solve(
        map,
        std::slice::from_ref(image),
        Scope::DeclaredStaticImages,
    )
    .unwrap()
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn matching_explicit_source_metadata_can_close() {
    let image = image();
    let report = report(&map(&image), &image);
    assert_eq!(report.status, ClosureStatus::Closed);
}

#[test]
fn equal_payload_from_different_rom_offset_must_not_close() {
    let declared = image();
    let map = map(&declared);
    let mut decoy = declared.clone();
    decoy.rom_offset = Some(RomOffset(0x200));

    let report = report(&map, &decoy);
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "supplied_image_provenance_conflict"));
}

#[test]
fn equal_payload_from_different_physical_backing_must_not_close() {
    let declared = image();
    let map = map(&declared);
    let mut decoy = declared.clone();
    decoy.physical_start = Some(PhysicalAddr(0x2000));

    let report = report(&map, &decoy);
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "supplied_image_provenance_conflict"));
}

#[test]
fn equal_payload_with_both_explicit_origins_wrong_must_not_close() {
    let declared = image();
    let map = map(&declared);
    let mut decoy = declared.clone();
    decoy.rom_offset = Some(RomOffset(0x200));
    decoy.physical_start = Some(PhysicalAddr(0x2000));

    let report = report(&map, &decoy);
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "supplied_image_provenance_conflict"));
}

#[test]
fn one_sided_missing_metadata_is_not_guessed_into_a_conflict() {
    let declared = image();
    let map = map(&declared);

    let mut no_rom = declared.clone();
    no_rom.rom_offset = None;
    let mut no_physical = declared.clone();
    no_physical.physical_start = None;
    let mut bytes_only = declared.clone();
    bytes_only.rom_offset = None;
    bytes_only.physical_start = None;

    for supplied in [no_rom, no_physical, bytes_only] {
        let report = report(&map, &supplied);
        assert_eq!(report.status, ClosureStatus::Closed);
        assert!(!has(&report, "supplied_image_provenance_conflict"));
    }
}

#[test]
fn disjoint_region_provenance_does_not_poison_the_source_join() {
    let declared = image();
    let mut map = map(&declared);
    let mut disjoint = map.regions.first().unwrap().clone();
    disjoint.range.start = GuestAddr(0x8000_1000);
    disjoint.rom_offset = Some(RomOffset(0x300));
    disjoint.physical_start = Some(PhysicalAddr(0x3000));
    map.regions.insert(disjoint);

    let report = report(&map, &declared);
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "supplied_image_provenance_conflict"));
}
