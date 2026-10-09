use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    merge::merge_maps,
    program::{CodeAddress, PhysicalAddr, ProgramMap, RomIdentity},
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn image(
    name: &str,
    base: u32,
    generation: u64,
    physical: Option<u32>,
    delay_word: u32,
) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(base),
            image: name.into(),
            generation,
        },
        // J self; chosen delay-slot word is a non-memory ADDIU accepted by the
        // declared-static subset. Changing this word changes executable content
        // without introducing a separate unsupported-effect blocker.
        words: vec![0x0800_0000, delay_word],
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

fn report(a: CodeImage, b: CodeImage) -> SolveReport {
    let m = merge(&a, &b);
    m.validate().unwrap();
    solve(&m, &[a, b], Scope::DeclaredStaticImages).unwrap()
}

fn has(r: &SolveReport, kind: &str) -> bool {
    r.blockers.iter().any(|b| b.kind == kind)
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

    let r = report(a, b);
    assert_eq!(
        r.status,
        ClosureStatus::Open,
        "distinct executable identities with contradictory bytes share one explicit physical span but solver blockers were: {:#?}",
        r.blockers
    );
    assert!(has(&r, "ambiguous_physical_executable_identity"));
}

#[test]
fn equal_payload_different_generation_still_needs_alias_lifetime_proof() {
    let a = image("same-image", 0x8000_0000, 7, Some(0x1000), 0x2408_0001);
    let b = image("same-image", 0xa000_0000, 8, Some(0x1000), 0x2408_0001);
    let r = report(a, b);
    assert_eq!(r.status, ClosureStatus::Open);
    assert!(has(&r, "ambiguous_physical_executable_identity"));
}

#[test]
fn partial_physical_overlap_between_distinct_identities_is_open() {
    let a = image("partial-a", 0x8000_0000, 0, Some(0x2000), 0x2408_0001);
    let b = image("partial-b", 0xa000_0000, 0, Some(0x2004), 0x2408_0002);
    let r = report(a, b);
    assert_eq!(r.status, ClosureStatus::Open);
    assert!(has(&r, "ambiguous_physical_executable_identity"));
}

#[test]
fn same_identity_explicit_alias_is_not_overclassified() {
    let a = image("alias", 0x8000_0000, 3, Some(0x3000), 0x2408_0001);
    let b = image("alias", 0xa000_0000, 3, Some(0x3000), 0x2408_0001);
    let r = report(a, b);
    assert_eq!(r.status, ClosureStatus::Closed, "{:#?}", r.blockers);
    assert!(!has(&r, "ambiguous_physical_executable_identity"));
}

#[test]
fn disjoint_explicit_backing_is_not_overclassified() {
    let a = image("disjoint-a", 0x8000_0000, 0, Some(0x4000), 0x2408_0001);
    let b = image("disjoint-b", 0xa000_0000, 0, Some(0x5000), 0x2408_0002);
    let r = report(a, b);
    assert_eq!(r.status, ClosureStatus::Closed, "{:#?}", r.blockers);
    assert!(!has(&r, "ambiguous_physical_executable_identity"));
}

#[test]
fn missing_physical_mapping_is_not_guessed_from_virtual_alias_shape() {
    let a = image("known-a", 0x8000_0000, 0, Some(0x6000), 0x2408_0001);
    let b = image("unknown-b", 0xa000_0000, 0, None, 0x2408_0002);
    let r = report(a, b);
    assert_eq!(r.status, ClosureStatus::Closed, "{:#?}", r.blockers);
    assert!(!has(&r, "ambiguous_physical_executable_identity"));
}
