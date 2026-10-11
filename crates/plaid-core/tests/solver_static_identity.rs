use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    merge::merge_maps,
    program::{CodeAddress, GuestRange, PhysicalAddr, ProgramMap, Region, RomIdentity, RomOffset},
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 0x20_000,
    }
}

fn image(
    name: &str,
    base: u32,
    generation: u64,
    words: Vec<u32>,
    rom_offset: Option<u64>,
    physical_start: Option<u32>,
) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(base),
            image: name.into(),
            generation,
        },
        words,
        rom_offset: rom_offset.map(RomOffset),
        physical_start: physical_start.map(PhysicalAddr),
    }
}

fn self_loop(
    name: &str,
    base: u32,
    generation: u64,
    delay_word: u32,
    physical_start: Option<u32>,
) -> CodeImage {
    image(
        name,
        base,
        generation,
        vec![0x0800_0000 | ((base >> 2) & 0x03ff_ffff), delay_word],
        None,
        physical_start,
    )
}

fn map(i: &CodeImage) -> ProgramMap {
    direct_cfg(rom(), i, &[i.base.pc], 100).unwrap().map
}

fn report(map: &ProgramMap, images: &[CodeImage]) -> SolveReport {
    map.validate().unwrap();
    solve(map, images, Scope::DeclaredStaticImages).unwrap()
}

fn merged_report(a: CodeImage, b: CodeImage) -> SolveReport {
    let merged = merge_maps(&map(&a), &map(&b)).unwrap();
    report(&merged, &[a, b])
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|blocker| blocker.kind == kind)
}

#[test]
fn guest_overlap_requires_one_executable_identity() {
    for (a, b) in [
        (
            self_loop("guest-a", 0x8000_0000, 0, 0x2408_0001, None),
            self_loop("guest-b", 0x8000_0000, 0, 0x2408_0002, None),
        ),
        (
            self_loop("guest-generation", 0x8000_1000, 7, 0x2408_0001, None),
            self_loop("guest-generation", 0x8000_1000, 8, 0x2408_0001, None),
        ),
        (
            self_loop("guest-partial-a", 0x8000_2000, 0, 0x2408_0001, None),
            self_loop("guest-partial-b", 0x8000_2004, 0, 0x2408_0002, None),
        ),
    ] {
        let result = merged_report(a, b);
        assert_eq!(result.status, ClosureStatus::Open, "{result:#?}");
        assert!(has(&result, "ambiguous_guest_executable_identity"));
    }

    let result = merged_report(
        self_loop("guest-disjoint-a", 0x8000_3000, 0, 0x2408_0001, None),
        self_loop("guest-disjoint-b", 0x8000_4000, 0, 0x2408_0002, None),
    );
    assert_eq!(result.status, ClosureStatus::Closed, "{result:#?}");
}

#[test]
fn explicit_physical_overlap_requires_alias_lifetime_proof() {
    for (a, b) in [
        (
            self_loop("physical-a", 0x8000_5000, 0, 0x2408_0001, Some(0x1000)),
            self_loop("physical-b", 0xa000_5000, 0, 0x2408_0002, Some(0x1000)),
        ),
        (
            self_loop(
                "physical-generation",
                0x8000_6000,
                7,
                0x2408_0001,
                Some(0x2000),
            ),
            self_loop(
                "physical-generation",
                0xa000_6000,
                8,
                0x2408_0001,
                Some(0x2000),
            ),
        ),
        (
            self_loop(
                "physical-partial-a",
                0x8000_7000,
                0,
                0x2408_0001,
                Some(0x3000),
            ),
            self_loop(
                "physical-partial-b",
                0xa000_7000,
                0,
                0x2408_0002,
                Some(0x3004),
            ),
        ),
    ] {
        let result = merged_report(a, b);
        assert_eq!(result.status, ClosureStatus::Open, "{result:#?}");
        assert!(has(&result, "ambiguous_physical_executable_identity"));
    }
}

#[test]
fn physical_alias_controls_do_not_invent_missing_provenance() {
    let same_identity = merged_report(
        self_loop("physical-alias", 0x8000_8000, 3, 0x2408_0001, Some(0x4000)),
        self_loop("physical-alias", 0xa000_8000, 3, 0x2408_0001, Some(0x4000)),
    );
    assert_eq!(
        same_identity.status,
        ClosureStatus::Closed,
        "{same_identity:#?}"
    );

    let unknown = merged_report(
        self_loop("physical-known", 0x8000_9000, 0, 0x2408_0001, Some(0x5000)),
        self_loop("physical-unknown", 0xa000_9000, 0, 0x2408_0002, None),
    );
    assert_eq!(unknown.status, ClosureStatus::Closed, "{unknown:#?}");
}

fn provenance_image() -> CodeImage {
    image(
        "region-provenance",
        0x8001_0000,
        7,
        vec![0x0800_4000, 0],
        Some(0),
        Some(0x6000),
    )
}

fn extra_region(
    map: &ProgramMap,
    start: u32,
    size: u32,
    rom_offset: Option<u64>,
    physical_start: Option<u32>,
) -> Region {
    Region {
        image: "region-provenance".into(),
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

#[test]
fn same_identity_region_provenance_must_be_affine_and_consistent() {
    let image = provenance_image();
    for extra in [
        (0x8001_0000, 8, Some(64), Some(0x6000)),
        (0x8001_0000, 8, Some(0), Some(0x7000)),
        (0x8001_0004, 4, Some(8), Some(0x6008)),
    ] {
        let mut candidate = map(&image);
        candidate
            .regions
            .insert(extra_region(&candidate, extra.0, extra.1, extra.2, extra.3));
        let result = report(&candidate, std::slice::from_ref(&image));
        assert_eq!(result.status, ClosureStatus::Open, "{result:#?}");
        assert!(has(&result, "conflicting_region_provenance"));
    }

    for extra in [
        (0x8001_0004, 4, Some(4), Some(0x6004)),
        (0x8001_0004, 4, None, None),
    ] {
        let mut candidate = map(&image);
        candidate
            .regions
            .insert(extra_region(&candidate, extra.0, extra.1, extra.2, extra.3));
        let result = report(&candidate, std::slice::from_ref(&image));
        assert_eq!(result.status, ClosureStatus::Closed, "{result:#?}");
    }
}

#[test]
fn merge_order_cannot_launder_region_provenance_conflict() {
    let image = provenance_image();
    let left = map(&image);
    let mut right = left.clone();
    right.regions.clear();
    right
        .regions
        .insert(extra_region(&left, 0x8001_0000, 8, Some(64), Some(0x7000)));
    right.validate().unwrap();

    for merged in [
        merge_maps(&left, &right).unwrap(),
        merge_maps(&right, &left).unwrap(),
    ] {
        let result = report(&merged, std::slice::from_ref(&image));
        assert_eq!(result.status, ClosureStatus::Open, "{result:#?}");
        assert!(has(&result, "conflicting_region_provenance"));
    }
}

fn fragmented_primary() -> CodeImage {
    image(
        "opaque-fragment",
        0x8002_0000,
        7,
        vec![0x2408_0001, 0x2409_0002, 0x0800_8000, 0],
        None,
        None,
    )
}

#[test]
fn same_identity_codeimage_fragments_must_be_single_valued_per_pc() {
    let primary = fragmented_primary();
    let primary_map = map(&primary);
    for conflicting in [
        image(
            "opaque-fragment",
            0x8002_0004,
            7,
            vec![0x2409_0003],
            None,
            None,
        ),
        image(
            "opaque-fragment",
            0x8002_0008,
            7,
            vec![0x0800_8001],
            None,
            None,
        ),
    ] {
        let result = report(&primary_map, &[primary.clone(), conflicting]);
        assert_eq!(result.status, ClosureStatus::Open, "{result:#?}");
        assert!(has(&result, "conflicting_instruction_sources"));
    }

    let equal = image(
        "opaque-fragment",
        0x8002_0004,
        7,
        vec![0x2409_0002],
        None,
        None,
    );
    let result = report(&primary_map, &[primary.clone(), equal]);
    assert_eq!(result.status, ClosureStatus::Closed, "{result:#?}");

    let different_generation = image(
        "opaque-fragment",
        0x8002_0004,
        8,
        vec![0x2409_0003],
        None,
        None,
    );
    let result = report(&primary_map, &[primary, different_generation]);
    assert_eq!(result.status, ClosureStatus::Closed, "{result:#?}");
}

fn content_image(words: Vec<u32>) -> CodeImage {
    let bytes: Vec<u8> = words.iter().flat_map(|word| word.to_be_bytes()).collect();
    image(
        &plaid_core::rom::sha256(&bytes),
        0x8003_0000,
        0,
        words,
        None,
        None,
    )
}

#[test]
fn self_authenticating_image_ids_must_match_supplied_words() {
    for trace_prefix in [false, true] {
        let mut original = content_image(vec![0x2408_0001, 0x0800_c000, 0]);
        if trace_prefix {
            original.base.image = format!("trace-{}", original.base.image);
        }
        let original_map = map(&original);
        assert_eq!(
            report(&original_map, std::slice::from_ref(&original)).status,
            ClosureStatus::Closed
        );

        let mut forged = original.clone();
        forged.words[0] = 0x2408_0002;
        let result = report(&original_map, &[forged]);
        assert_eq!(result.status, ClosureStatus::Open, "{result:#?}");
        assert!(has(&result, "instruction_source_identity_mismatch"));
    }
}

#[test]
fn supplied_codeimage_provenance_must_match_covering_region() {
    let declared = image(
        "supplied-provenance",
        0x8003_8000,
        9,
        vec![0x0800_e000, 0],
        Some(0x100),
        Some(0x7000),
    );
    let declared_map = map(&declared);

    for (rom_offset, physical_start) in [
        (Some(RomOffset(0x200)), declared.physical_start),
        (declared.rom_offset, Some(PhysicalAddr(0x8000))),
        (Some(RomOffset(0x200)), Some(PhysicalAddr(0x8000))),
    ] {
        let mut decoy = declared.clone();
        decoy.rom_offset = rom_offset;
        decoy.physical_start = physical_start;
        let result = report(&declared_map, &[decoy]);
        assert_eq!(result.status, ClosureStatus::Open, "{result:#?}");
        assert!(has(&result, "supplied_image_provenance_conflict"));
    }

    let result = report(&declared_map, std::slice::from_ref(&declared));
    assert_eq!(result.status, ClosureStatus::Closed, "{result:#?}");

    let mut no_rom = declared.clone();
    no_rom.rom_offset = None;
    let mut no_physical = declared.clone();
    no_physical.physical_start = None;
    let mut bytes_only = declared.clone();
    bytes_only.rom_offset = None;
    bytes_only.physical_start = None;
    for compatible in [no_rom, no_physical, bytes_only] {
        let result = report(&declared_map, &[compatible]);
        assert_eq!(result.status, ClosureStatus::Closed, "{result:#?}");
        assert!(!has(&result, "supplied_image_provenance_conflict"));
    }
}

#[test]
fn generation_labels_alone_do_not_invent_lifecycle_chronology() {
    let image = self_loop("opaque-generation", 0x8004_0000, 7, 0x2408_0001, None);
    let result = report(&map(&image), &[image]);
    assert_eq!(result.status, ClosureStatus::Closed, "{result:#?}");
}
