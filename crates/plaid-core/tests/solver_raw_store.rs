use plaid_core::{GuestAddr, discovery::*, program::*, solver::*};

fn image(physical_start: Option<PhysicalAddr>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0xa0000000),
            image: "solver-raw-store".into(),
            generation: 0,
        },
        // J 0xa0000000; NOP. The high target nibble comes from PC+4.
        words: vec![0x08000000, 0],
        rom_offset: None,
        physical_start,
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

fn add_raw_store(map: &mut ProgramMap, destination: GuestAddr) -> EvidenceRefs {
    let evidence = map.blocks.first().unwrap().evidence.clone();
    map.word_store_observations.insert(ObservedWordStore {
        site: GuestAddr(0x80000100),
        destination,
        // Same value as the first executable word on purpose: payload equality
        // must not erase the successful mutation event.
        value: 0x08000000,
        generation: 0,
        evidence: evidence.clone(),
    });
    evidence
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|blocker| blocker.kind == kind)
}

fn solve_static(map: &ProgramMap, image: &CodeImage) -> SolveReport {
    solve(
        map,
        std::slice::from_ref(image),
        Scope::DeclaredStaticImages,
    )
    .unwrap()
}

#[test]
fn deleting_derived_write_cannot_close_overlapping_raw_store() {
    // The executable image is KSEG1-mapped at physical 0. The retained raw store
    // uses its KSEG0 alias, so virtual-range comparison alone cannot see overlap.
    let image = image(Some(PhysicalAddr(0)));
    let mut map = map(&image);
    add_raw_store(&mut map, GuestAddr(0x80000000));

    // Model a hand-edited/partial ProgramMap that kept the primitive successful
    // store observation but deleted import_trace's derived ExecutableWrite fact.
    assert!(map.executable_writes.is_empty());
    map.validate().unwrap();

    let report = solve_static(&map, &image);
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_executable_write"));
}

#[test]
fn nonoverlapping_raw_store_does_not_gain_executable_write_blocker() {
    let image = image(Some(PhysicalAddr(0x1000)));
    let mut map = map(&image);
    add_raw_store(&mut map, GuestAddr(0x80000000));

    let report = solve_static(&map, &image);
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "unresolved_executable_write"));
}

#[test]
fn missing_physical_mapping_is_not_guessed_from_virtual_aliases() {
    let image = image(None);
    let mut map = map(&image);
    add_raw_store(&mut map, GuestAddr(0x80000000));

    let report = solve_static(&map, &image);
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "unresolved_executable_write"));
}

#[test]
fn retained_derived_write_does_not_duplicate_the_existing_blocker() {
    let image = image(Some(PhysicalAddr(0)));
    let mut map = map(&image);
    let evidence = add_raw_store(&mut map, GuestAddr(0x80000000));
    map.executable_writes.insert(ExecutableWrite {
        range: Some(GuestRange {
            start: GuestAddr(0x80000000),
            size: 4,
        }),
        kind: WriteKind::Unknown,
        evidence,
    });

    let report = solve_static(&map, &image);
    assert_eq!(report.status, ClosureStatus::Open);
    assert_eq!(
        report
            .blockers
            .iter()
            .filter(|blocker| blocker.kind == "unresolved_executable_write")
            .count(),
        1
    );
}
