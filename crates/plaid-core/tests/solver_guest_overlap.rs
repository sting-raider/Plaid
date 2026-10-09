use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    merge::merge_maps,
    program::{CodeAddress, GuestRange, ProgramMap, Region, RomIdentity},
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn image(name: &str, base: u32, generation: u64, delay_word: u32) -> CodeImage {
    let jump_target = (base >> 2) & 0x03ff_ffff;
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(base),
            image: name.into(),
            generation,
        },
        // J self + an allowed integer delay-slot instruction keeps each image
        // independently CLOSED while permitting equal/conflicting payload controls.
        words: vec![0x0800_0000 | jump_target, delay_word],
        rom_offset: None,
        physical_start: None,
    }
}

fn map(i: &CodeImage) -> ProgramMap {
    direct_cfg(rom(), i, &[i.base.pc], 100).unwrap().map
}

fn report(a: CodeImage, b: CodeImage) -> SolveReport {
    let m = merge_maps(&map(&a), &map(&b)).unwrap();
    m.validate().unwrap();
    solve(&m, &[a, b], Scope::DeclaredStaticImages).unwrap()
}

fn has(r: &SolveReport, kind: &str) -> bool {
    r.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn distinct_identities_on_same_guest_range_must_not_close() {
    let a = image("guest-a", 0x8000_0000, 0, 0x2408_0001);
    let b = image("guest-b", 0x8000_0000, 0, 0x2408_0002);

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

    let r = report(a, b);
    assert_eq!(
        r.status,
        ClosureStatus::Open,
        "two executable identities occupy the same guest PCs without a selector, but blockers were: {:#?}",
        r.blockers
    );
    assert!(has(&r, "ambiguous_guest_executable_identity"));
}

#[test]
fn equal_payload_different_generation_still_needs_guest_identity_selection() {
    let a = image("same-image", 0x8000_1000, 7, 0x2408_0001);
    let b = image("same-image", 0x8000_1000, 8, 0x2408_0001);
    let r = report(a, b);
    assert_eq!(r.status, ClosureStatus::Open, "{:#?}", r.blockers);
    assert!(has(&r, "ambiguous_guest_executable_identity"));
}

#[test]
fn partial_guest_overlap_between_distinct_identities_is_open() {
    let a = image("partial-a", 0x8000_2000, 0, 0x2408_0001);
    let b = image("partial-b", 0x8000_2004, 0, 0x2408_0002);
    let r = report(a, b);
    assert_eq!(r.status, ClosureStatus::Open, "{:#?}", r.blockers);
    assert!(has(&r, "ambiguous_guest_executable_identity"));
}

#[test]
fn disjoint_guest_ranges_are_not_overclassified() {
    let a = image("disjoint-a", 0x8000_3000, 0, 0x2408_0001);
    let b = image("disjoint-b", 0x8000_4000, 0, 0x2408_0002);
    let r = report(a, b);
    assert_eq!(r.status, ClosureStatus::Closed, "{:#?}", r.blockers);
    assert!(!has(&r, "ambiguous_guest_executable_identity"));
}

#[test]
fn overlapping_region_descriptions_for_one_identity_are_not_overclassified() {
    let i = image("one-identity", 0x8000_5000, 3, 0x2408_0001);
    let mut m = map(&i);
    let refs = m.regions.iter().next().unwrap().evidence.clone();
    m.regions.insert(Region {
        image: i.base.image.clone(),
        generation: i.base.generation,
        range: GuestRange {
            start: GuestAddr(0x8000_5004),
            size: 4,
        },
        rom_offset: None,
        physical_start: None,
        overlay: None,
        evidence: refs,
    });
    m.validate().unwrap();
    let r = solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(r.status, ClosureStatus::Closed, "{:#?}", r.blockers);
    assert!(!has(&r, "ambiguous_guest_executable_identity"));
}
