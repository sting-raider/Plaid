use plaid_core::{
    GuestAddr,
    discovery::CodeImage,
    pipeline::discover_image,
    program::{CodeAddress, PhysicalAddr, RomIdentity, RomOffset},
    solver::{ClosureStatus, Scope, solve},
};

fn image(words: &[u32]) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "traps".into(),
            generation: 0,
        },
        words: words.to_vec(),
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
        holes: Vec::new(),
        slots: Vec::new(),
    }
}

#[test]
fn conditional_trap_falls_through_and_closes_only_when_guarded() {
    // teq a0, zero; addiu v0, zero, 1; b .; nop (ADR-0145)
    let i = image(&[0x0080_0034, 0x2402_0001, 0x1000_ffff, 0]);
    let rom = RomIdentity {
        sha256: "b".repeat(64),
        size: 4096,
    };
    let map = discover_image(rom, &i, &[i.base.pc], 100).unwrap().map;
    // Discovery continues past the trap: its fallthrough is code.
    assert!(
        map.blocks
            .iter()
            .any(|b| b.start.pc.0 <= 0x8000_0004 && 0x8000_0004 < b.start.pc.0 + b.size)
    );
    let guarded = solve(
        &map,
        std::slice::from_ref(&i),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert_eq!(
        guarded.status,
        ClosureStatus::Closed,
        "{:?}",
        guarded.blockers
    );
    assert!(
        guarded
            .assumptions
            .iter()
            .any(|a| a.contains("Conditional traps"))
    );
    assert!(!guarded.assumptions.iter().any(|a| a.contains("BREAK")));
    let plain = solve(&map, &[i], Scope::DeclaredStaticImages).unwrap();
    assert_ne!(plain.status, ClosureStatus::Closed);
}
