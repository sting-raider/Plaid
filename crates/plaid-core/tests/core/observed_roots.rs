//! Targets an unproven indirect call took in the analysis-time replay root
//! address-taken discovery without certifying the call (ADR-0222).
use plaid_core::{
    GuestAddr,
    data_roots::discover_address_taken_with_loads,
    discovery::CodeImage,
    program::{CodeAddress, PhysicalAddr, ProgramMap, RomIdentity, RomOffset},
    solver::{Scope, solve},
};
use std::collections::BTreeSet;

const BASE: u32 = 0x8000_0000;
const F: u32 = BASE + 8 * 4;

/// main calls through a RAM value plus an offset; no word names f.
fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "observed-roots".into(),
            generation: 0,
        },
        words: vec![
            0x8f88_0000, // lw t0, 0(gp)
            0x2519_0028, // addiu t9, t0, 0x28
            0x0320_f809, // jalr t9
            0,
            0x1000_ffff, // b .
            0,
            0x03e0_0008, // pad: jr ra
            0,
            0x2482_0001, // f: addiu v0, a0, 1
            0x03e0_0008, // jr ra
            0,
        ],
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
        holes: Vec::new(),
        slots: Vec::new(),
    }
}

fn discover(image: &CodeImage, observed: &[u32]) -> ProgramMap {
    let bytes: Vec<u8> = image.words.iter().flat_map(|w| w.to_be_bytes()).collect();
    discover_address_taken_with_loads(
        RomIdentity {
            sha256: "f".repeat(64),
            size: 4096,
        },
        &bytes,
        image,
        &[GuestAddr(BASE)],
        &[],
        None,
        &Default::default(),
        None,
        &observed
            .iter()
            .copied()
            .map(GuestAddr)
            .collect::<BTreeSet<_>>(),
        100,
    )
    .unwrap()
    .map
}

fn blocker(map: &ProgramMap, image: &CodeImage, scope: Scope, kind: &str) -> bool {
    solve(map, std::slice::from_ref(image), scope)
        .unwrap()
        .blockers
        .iter()
        .any(|b| b.kind == kind)
}

#[test]
fn an_observed_target_is_discovered_and_dispatched_but_not_certified() {
    let image = image();
    let f = image.address(GuestAddr(F));
    let unseen = discover(&image, &[]);
    assert!(!unseen.address_taken.contains_key(&f));
    assert!(unseen.blocks.iter().all(|b| b.start != f));

    let map = discover(&image, &[F]);
    assert!(map.address_taken.contains_key(&f));
    assert!(map.blocks.iter().any(|b| b.start == f));
    let site = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc == GuestAddr(BASE + 8))
        .unwrap();
    assert!(
        site.closed_proof.is_none(),
        "an observation is not a target set"
    );
    assert!(blocker(
        &map,
        &image,
        Scope::WholeRom,
        "unresolved_indirect_site"
    ));
    assert!(!blocker(
        &map,
        &image,
        Scope::DeclaredStaticImagesGuardedRamAddressTaken,
        "unresolved_indirect_site"
    ));
}

#[test]
fn an_executed_target_needs_no_preceding_return() {
    // f follows a wait loop, not a return: no layout clue, yet it was called.
    let mut image = image();
    image.words[6] = 0x1000_ffff; // b .
    let f = image.address(GuestAddr(F));
    assert!(!plaid_core::data_roots::plausible(&image, GuestAddr(F)));
    let map = discover(&image, &[F]);
    assert!(map.address_taken.contains_key(&f));
    let scope = Scope::DeclaredStaticImagesGuardedRamAddressTaken;
    assert!(!blocker(&map, &image, scope, "unresolved_indirect_site"));
    // Without the replay's evidence the same entry voids the address-taken set.
    let mut unseen = map.clone();
    for refs in unseen.address_taken.values_mut() {
        refs.retain(|id| !id.starts_with("observed-call:"));
    }
    assert!(blocker(&unseen, &image, scope, "unresolved_indirect_site"));
}

#[test]
fn implausible_observed_targets_are_not_roots() {
    let image = image();
    for target in [BASE + 0x1000, F + 2] {
        let map = discover(&image, &[target]);
        assert!(
            map.address_taken.keys().all(|a| a.pc != GuestAddr(target)),
            "{target:08x}"
        );
    }
}

#[test]
fn observed_targets_that_fail_executed_start_are_not_roots() {
    let mut image = image();
    image.words[8] = 0; // aligned, in-image, but not an executed instruction
    assert!(!plaid_core::data_roots::executed_start(
        &image,
        GuestAddr(F)
    ));
    let map = discover(&image, &[F]);
    assert!(
        !map.address_taken
            .keys()
            .any(|address| address.pc == GuestAddr(F))
    );
    assert!(
        !map.blocks
            .iter()
            .any(|block| block.start == image.address(GuestAddr(F)))
    );
}
