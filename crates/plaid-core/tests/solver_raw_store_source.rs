use plaid_core::{GuestAddr, discovery::*, program::*, solver::*};

fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "raw-store-source-test".into(),
            generation: 0,
        },
        // J 0x80000000; NOP. No memory instruction exists in the declared image.
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

fn raw_store(map: &ProgramMap, site: u32, destination: u32, value: u32) -> ObservedWordStore {
    ObservedWordStore {
        site: GuestAddr(site),
        destination: GuestAddr(destination),
        value,
        generation: 0,
        evidence: map.blocks.first().unwrap().evidence.clone(),
    }
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn retained_successful_store_outside_declared_universe_cannot_close_static_scope() {
    let i = image();
    let mut m = closed_map(&i);

    // Destination is ordinary non-executable RDRAM and the map has no explicit
    // physical backing, so executable-destination overlap is deliberately not
    // part of this witness. The primitive still says an SW executed at a source
    // PC absent from the declared finite executable universe.
    m.word_store_observations
        .insert(raw_store(&m, 0x9000_0000, 0x8000_1000, 0x0800_0000));
    m.validate().unwrap();

    let report = solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "dynamic_effect_outside_scope"));
}

#[test]
fn pc_epoch_and_equal_payload_cannot_launder_successful_store_execution() {
    let i = image();
    let mut m = closed_map(&i);

    // Same numeric PC and import epoch as the declared block, and a payload
    // equal to its first instruction. None of those facts proves that the J
    // instruction was really an SW. The raw primitive itself is a successful
    // memory effect, which this declared-static scope excludes.
    m.word_store_observations
        .insert(raw_store(&m, 0x8000_0000, 0x8000_1000, 0x0800_0000));
    m.validate().unwrap();

    let report = solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "dynamic_effect_outside_scope"));
}

#[test]
fn no_raw_store_control_remains_closed() {
    let i = image();
    let m = closed_map(&i);
    let report = solve(&m, &[i], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!has(&report, "dynamic_effect_outside_scope"));
}
