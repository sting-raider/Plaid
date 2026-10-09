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

fn add_raw_store(map: &mut ProgramMap, destination: GuestAddr) {
    let evidence = map.blocks.first().unwrap().evidence.clone();
    map.word_store_observations.insert(ObservedWordStore {
        site: GuestAddr(0x80000100),
        destination,
        value: 0x08000000,
        generation: 0,
        evidence,
    });
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|blocker| blocker.kind == kind)
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

    let report = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_executable_write"));
}
