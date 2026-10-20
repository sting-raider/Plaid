//! Stack-cell forwarding must prove bytes, frame ownership and every incoming path.
use plaid_core::{GuestAddr, discovery::CodeImage, pipeline::discover_image, program::*};

const BASE: u32 = 0x8000_0000;

fn image() -> CodeImage {
    let mut words = vec![0; 0x200 / 4];
    words[..20].copy_from_slice(&[
        0x27bd_ffe0, // allocate 32-byte frame
        0x3c09_8000,
        0x2529_0180, // table base
        0x0004_5080, // t2 = a0 << 2
        0x012a_5821, // t3 = base + scaled index
        0xafab_0010, // sw t3,16(sp)
        0x240b_0063, // destroy source after saving
        0,           // intervening instruction, mutated by negatives
        0x2c8c_0002, // sltiu t4,a0,2
        0x1180_0007, // invalid -> return
        0,
        0x8fad_0010, // lw t5,16(sp)
        0x8da2_0000, // lw v0,0(t5)
        0x0040_0008,
        0,
        0,
        0,
        0x03e0_0008,
        0x27bd_0020,
        0,
    ]);
    words[0x80 / 4..0x90 / 4].copy_from_slice(&[0x2402_0001, 0x0800_0011, 0, 0]);
    words[0xa0 / 4..0xb0 / 4].copy_from_slice(&[0x2402_000a, 0x0800_0011, 0, 0]);
    words[0x180 / 4..0x188 / 4].copy_from_slice(&[BASE + 0x80, BASE + 0xa0]);
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "stack-pointer-test".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
        holes: vec![],
        slots: vec![],
    }
}

fn map(image: &CodeImage, extra: &[GuestAddr]) -> ProgramMap {
    let mut entries = vec![image.base.pc];
    entries.extend(extra);
    discover_image(
        RomIdentity {
            sha256: "0".repeat(64),
            size: 4096,
        },
        image,
        &entries,
        10000,
    )
    .unwrap()
    .map
}

fn site(map: &ProgramMap) -> &IndirectSite {
    map.indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == BASE + 0x34)
        .unwrap()
}

fn verifies(image: &CodeImage) -> bool {
    let map = map(image, &[]);
    plaid_core::tables::verify(&map, image, site(&map))
}

#[test]
fn frame_local_pointer_survives_source_clobber_and_a_guard_edge() {
    let image = image();
    let map = map(&image, &[]);
    assert!(plaid_core::tables::verify(&map, &image, site(&map)));
    let mut changed = image.clone();
    changed.words[6] = 0x240b_0064; // still dead, but source certificate must change
    assert!(!plaid_core::tables::verify(&map, &changed, site(&map)));
}

#[test]
fn unknown_writes_sp_changes_and_non_frame_cells_refuse() {
    for (index, word) in [
        (2, 0x1480_0005),  // one incoming path skips the spill
        (7, 0x4080_6000),  // mapping/Status change
        (7, 0xac8b_0000),  // arbitrary argument may alias the cell
        (7, 0xafab_0010),  // overwrites with the clobbered source
        (7, 0xafa0_0018),  // even another virtual stack cell lacks a physical-alias proof
        (7, 0xaba0_0011),  // partial word store
        (7, 0xa3a0_0011),  // byte overwrite
        (7, 0xe7a0_0010),  // floating store
        (7, 0xbfa0_0010),  // cache operation
        (7, 0x27bd_fff8),  // changed SP
        (7, 0x0080_e82d),  // arbitrary SP definition
        (5, 0xafab_0014),  // wrong cell
        (0, 0x27bd_fff0),  // cell outside allocation
        (0, 0),            // no allocation
        (0, 0x27bd_0020),  // deallocation is not ownership
        (11, 0x8fad_0011), // unaligned cell
        (11, 0x8fad_fff0), // outside own frame
    ] {
        let mut input = image();
        input.words[index] = word;
        assert!(!verifies(&input), "accepted mutation {index}: {word:08x}");
    }
}

#[test]
fn independent_entry_cannot_skip_spill_or_allocation() {
    for offset in [4, 24, 44] {
        let image = image();
        let map = map(&image, &[GuestAddr(BASE + offset)]);
        assert!(!plaid_core::tables::verify(&map, &image, site(&map)));
    }
}

#[test]
fn a_call_cannot_carry_an_unproven_stack_cell() {
    let mut image = image();
    image.words[6] = 0x0c00_0030; // leaf itself writes no GPR or memory
    image.words[7] = 0;
    image.words[0xc0 / 4] = 0x03e0_0008;
    assert!(!verifies(&image));
}
