//! Register calls dispatch over the address-taken functions (ADR-0153).
use plaid_core::{
    GuestAddr,
    data_roots::discover_address_taken,
    discovery::CodeImage,
    program::{CodeAddress, PhysicalAddr, RomIdentity, RomOffset},
    solver::{Scope, solve},
};

const BASE: u32 = 0x8000_0000;
const F: u32 = BASE + 10 * 4;

/// main stores f's address through $gp, reloads it and calls it.
fn image() -> CodeImage {
    let words = vec![
        0x3c08_8000,                // lui t0, 0x8000
        0x2508_0000 | (F & 0xffff), // addiu t0, t0, f
        0xaf88_0000,                // sw t0, 0(gp)
        0x8f99_0000,                // lw t9, 0(gp)
        0x0320_f809,                // jalr t9
        0,
        0x1000_ffff, // b .
        0,
        0x03e0_0008, // pad: jr ra
        0,
        0x2482_0001, // f: addiu v0, a0, 1
        0x03e0_0008, // jr ra
        0,
    ];
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "address-taken".into(),
            generation: 0,
        },
        words,
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
        holes: Vec::new(),
    }
}

fn open_sites(map: &plaid_core::program::ProgramMap, image: &CodeImage, scope: Scope) -> usize {
    solve(map, std::slice::from_ref(image), scope)
        .unwrap()
        .blockers
        .iter()
        .filter(|b| b.kind == "unresolved_indirect_site")
        .count()
}

#[test]
fn register_calls_close_only_over_plausible_address_taken_functions() {
    let image = image();
    let rom = RomIdentity {
        sha256: "e".repeat(64),
        size: 4096,
    };
    let bytes: Vec<u8> = image.words.iter().flat_map(|w| w.to_be_bytes()).collect();
    let mut map = discover_address_taken(
        rom,
        &bytes,
        &image,
        &[GuestAddr(BASE)],
        &[],
        None,
        &Default::default(),
        100,
    )
    .unwrap()
    .map;
    assert_eq!(
        map.address_taken.keys().map(|a| a.pc).collect::<Vec<_>>(),
        [GuestAddr(F)]
    );
    // the register call, and f's return
    assert_eq!(map.indirect_sites.len(), 2);
    assert_eq!(
        open_sites(
            &map,
            &image,
            Scope::DeclaredStaticImagesGuardedRamAddressTaken
        ),
        0
    );
    // the guarded scope makes no address-taken assumption
    assert_eq!(
        open_sites(&map, &image, Scope::DeclaredStaticImagesGuardedRam),
        1
    );
    // a recorded address that is not a plausible function start voids the set
    let mid = image.address(GuestAddr(F + 4));
    map.address_taken
        .insert(mid, map.address_taken.values().next().unwrap().clone());
    assert_eq!(
        open_sites(
            &map,
            &image,
            Scope::DeclaredStaticImagesGuardedRamAddressTaken
        ),
        1
    );
}

#[test]
fn a_constant_built_across_blocks_is_address_taken() {
    // GCC schedules the `lui` into a branch delay slot and the `addiu` into
    // the branch target's block (ADR-0182)
    let f = BASE + 12 * 4;
    let mut image = image();
    image.words = vec![
        0x1480_0002,                // bne a0, zero, +2
        0x3c08_8000,                // lui t0, 0x8000 (delay slot)
        0x2402_0001,                // addiu v0, zero, 1
        0x2508_0000 | (f & 0xffff), // addiu t0, t0, f
        0xaf88_0000,                // sw t0, 0(gp)
        0x8f99_0000,                // lw t9, 0(gp)
        0x0320_f809,                // jalr t9
        0,
        0x1000_ffff, // b .
        0,
        0x03e0_0008, // pad: jr ra
        0,
        0x2482_0001, // f: addiu v0, a0, 1
        0x03e0_0008, // jr ra
        0,
    ];
    let rom = RomIdentity {
        sha256: "e".repeat(64),
        size: 4096,
    };
    let bytes: Vec<u8> = image.words.iter().flat_map(|w| w.to_be_bytes()).collect();
    let map = discover_address_taken(
        rom,
        &bytes,
        &image,
        &[GuestAddr(BASE)],
        &[],
        None,
        &Default::default(),
        100,
    )
    .unwrap()
    .map;
    assert_eq!(
        map.address_taken.keys().map(|a| a.pc).collect::<Vec<_>>(),
        [GuestAddr(f)]
    );
    assert_eq!(
        open_sites(
            &map,
            &image,
            Scope::DeclaredStaticImagesGuardedRamAddressTaken
        ),
        0
    );
}
