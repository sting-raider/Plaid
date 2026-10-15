//! Callbacks forwarded through a wrapper's argument (ADR-0149).
use plaid_core::{
    EvidenceKind, GuestAddr,
    callbacks::callbacks,
    discovery::CodeImage,
    pipeline::discover_image_with_runtime,
    program::{CodeAddress, Evidence, PhysicalAddr, RomIdentity, RomOffset},
    solver::{Scope, solve},
};
use std::collections::BTreeSet;

const BASE: u32 = 0x8000_0000;
const CB1: u32 = BASE + 10 * 4;
const CB2: u32 = BASE + 12 * 4;
const GO: u32 = BASE + 14 * 4;
const SPAWN: u32 = BASE + 24 * 4;

fn jal(target: u32) -> u32 {
    0x0c00_0000 | (target >> 2 & 0x03ff_ffff)
}

/// main calls go(cb1) and go(cb2); go spills a0 IDO-style, stores through
/// $gp, reloads a0 and calls the runtime function spawn(a0 = guest code).
fn program() -> Vec<u32> {
    vec![
        0x3c04_8000,
        0x2484_0000 | (CB1 & 0xffff),
        jal(GO),
        0,
        0x3c04_8000,
        0x2484_0000 | (CB2 & 0xffff),
        jal(GO),
        0,
        0x1000_ffff, // b .
        0,
        0x03e0_0008, // cb1: jr ra
        0,
        0x03e0_0008, // cb2: jr ra
        0,
        0x27bd_ffe8, // go: addiu sp, sp, -24
        0xafbf_0014, // sw ra, 20(sp)
        0xafa4_0018, // sw a0, 24(sp)
        0xaf80_0000, // sw zero, 0(gp)
        0x8fa4_0018, // lw a0, 24(sp)
        jal(SPAWN),
        0,
        0x8fbf_0014, // lw ra, 20(sp)
        0x03e0_0008, // jr ra
        0x27bd_0018, // addiu sp, sp, 24
        0x03e0_0008, // spawn (runtime; never decoded)
        0,
    ]
}

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "forwarded".into(),
            generation: 0,
        },
        words,
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
        holes: Vec::new(),
    }
}

/// Proven callback targets and the number of unproven callbacks.
fn measure(words: Vec<u32>, entries: &[u32]) -> (BTreeSet<u32>, usize, CodeImage) {
    let i = image(words);
    let rom = RomIdentity {
        sha256: "f".repeat(64),
        size: 4096,
    };
    let evidence = Evidence {
        kind: EvidenceKind::Signature,
        producer: "test".into(),
        revision: "0".into(),
        detail: "forwarded callback test".into(),
    };
    let entries: Vec<_> = entries.iter().map(|&e| GuestAddr(e)).collect();
    let map = discover_image_with_runtime(
        rom,
        &i,
        &entries,
        &[(GuestAddr(SPAWN), "spawn".into(), vec![4])],
        Some(("runtime".into(), evidence)),
        1000,
    )
    .unwrap()
    .map;
    let found = callbacks(&map, &i);
    let proven = found
        .iter()
        .filter_map(|c| c.target.as_ref().map(|t| t.pc.0))
        .collect();
    let unproven = found.iter().filter(|c| c.target.is_none()).count();
    (proven, unproven, i)
}

#[test]
fn a_spilled_argument_forwards_every_callers_constant() {
    let (proven, unproven, i) = measure(program(), &[BASE]);
    assert_eq!(proven, BTreeSet::from([CB1, CB2]));
    assert_eq!(unproven, 0);
    let rom = RomIdentity {
        sha256: "f".repeat(64),
        size: 4096,
    };
    let evidence = Evidence {
        kind: EvidenceKind::Signature,
        producer: "test".into(),
        revision: "0".into(),
        detail: "forwarded callback test".into(),
    };
    let map = discover_image_with_runtime(
        rom,
        &i,
        &[GuestAddr(BASE)],
        &[(GuestAddr(SPAWN), "spawn".into(), vec![4])],
        Some(("runtime".into(), evidence)),
        1000,
    )
    .unwrap()
    .map;
    // both callbacks are discovered as functions the runtime enters
    for cb in [CB1, CB2] {
        assert!(map.blocks.iter().any(|b| b.start.pc.0 == cb));
    }
    let report = solve(
        &map,
        std::slice::from_ref(&i),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert!(
        !report
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_runtime_callback"),
        "{:?}",
        report.blockers
    );
    assert!(report.assumptions.iter().any(|a| a.contains("ADR-0149")));
}

#[test]
fn forwarding_fails_closed() {
    // the frame address escapes into t0
    let mut escape = program();
    escape[17] = 0x03a0_4021; // addu t0, sp, zero
    assert_eq!(measure(escape, &[BASE]).1, 1);
    // a byte store into the spill slot clobbers it
    let mut clobber = program();
    clobber[17] = 0xa3a0_001a; // sb zero, 26(sp)
    assert_eq!(measure(clobber, &[BASE]).1, 1);
    // one caller passes a value loaded from memory: only that call is open
    let mut unknown = program();
    unknown[4] = 0x8f84_0000; // lw a0, 0(gp)
    unknown[5] = 0;
    let (proven, unproven, _) = measure(unknown, &[BASE]);
    assert_eq!((proven, unproven), (BTreeSet::from([CB1]), 1));
    // the wrapper is also a program entry, so it has callers nobody sees
    assert_eq!(measure(program(), &[BASE, GO]).1, 1);
}
