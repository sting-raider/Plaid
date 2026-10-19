//! Branch requirements can rule out a loop path only while their GPR survives.
use plaid_core::{GuestAddr, discovery::CodeImage, pipeline::discover_image, program::*};
const BASE: u32 = 0x80000000;

fn image() -> CodeImage {
    let mut words = vec![0; 0x120 / 4];
    words[..11].copy_from_slice(&[
        0x8e04_0000, // load an unconstrained index
        0x2c94_0002, // s4 = index < 2
        0x3c03_8000,
        0x2463_0100,
        0x0004_1080,
        0x0043_9021, // s2 = table + index*4
        0x5280_0009,
        0, // header: beql s4,zero,body
        0x8e42_0000,
        0x0040_0008,
        0,
    ]);
    words[0x40 / 4..0x58 / 4].copy_from_slice(&[
        0x2508_0001,
        0x2409_0003,
        0x1509_fff3,
        0,
        0x0800_0020,
        0,
    ]);
    words[0x60 / 4..0x68 / 4].copy_from_slice(&[0x0800_0020, 0]);
    words[0x70 / 4..0x78 / 4].copy_from_slice(&[0x0800_0020, 0]);
    words[0x80 / 4] = 0x03e0_0008;
    words[0x100 / 4] = BASE + 0x60;
    words[0x104 / 4] = BASE + 0x70;
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "flag-paths".into(),
            generation: 8,
        },
        words,
        rom_offset: None,
        physical_start: None,
        holes: Vec::new(),
        slots: Vec::new(),
    }
}
fn verified(image: &CodeImage, extra: Option<u32>) -> bool {
    let mut entries = vec![image.base.pc];
    if let Some(pc) = extra {
        entries.push(GuestAddr(BASE + pc));
    }
    let map = discover_image(
        RomIdentity {
            sha256: "f".repeat(64),
            size: 4096,
        },
        image,
        &entries,
        10000,
    )
    .unwrap()
    .map;
    let site = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == BASE + 0x24)
        .unwrap();
    plaid_core::tables::verify(&map, image, site)
}
#[test]
fn an_unchanged_zero_flag_cannot_later_take_the_nonzero_dispatch_path() {
    let image = image();
    assert!(verified(&image, None));
}
#[test]
fn flag_writes_and_unknown_entries_keep_the_bad_path_possible() {
    for offset in [0x40, 0x4c] {
        let mut changed = image();
        changed.words[offset / 4] = 0x2414_0001;
        assert!(!verified(&changed, None));
    }
    assert!(!verified(&image(), Some(0x40)));
}
#[test]
fn a_pointer_definition_cannot_preserve_its_old_branch_flag() {
    for register in [2u32, 18] {
        let mut changed = image();
        changed.words[1] = 0x2c80_0002 | register << 16;
        // The pointer or shift overwrites the boolean before it is tested.
        changed.words[0x18 / 4] = 0x5000_0009 | register << 21;
        assert!(!verified(&changed, None), "stale flag in r{register}");
    }
}

#[test]
fn overwriting_a_guard_with_a_pointer_is_invalid_even_without_a_cycle() {
    for register in [2u32, 18] {
        let mut changed = image();
        changed.words[1] = 0x2c80_0002 | register << 16;
        changed.words[0x18 / 4] = 0x5000_0009 | register << 21;
        changed.words[0x48 / 4] = 0x0800_0020; // invalid branch path exits rather than looping
        assert!(
            !verified(&changed, None),
            "stale straight-path flag in r{register}"
        );
    }
}

fn call_image() -> CodeImage {
    let mut image = image();
    for at in [0x60usize, 0x70] {
        image.words[at / 4..(at + 16) / 4].copy_from_slice(&[0x0c00_0024, 0, 0x0800_0010, 0]);
    }
    image.words[0x90 / 4..0xa0 / 4].copy_from_slice(&[0x2404_0063, 0x2403_0055, 0x03e0_0008, 0]);
    image
}
#[test]
fn captured_pointer_and_flag_survive_a_nonwriting_callee() {
    assert!(verified(&call_image(), None));
}
#[test]
fn the_callee_must_preserve_every_pending_value() {
    for register in [18u32, 20] {
        let mut changed = call_image();
        changed.words[0x90 / 4] = 0x2400_0001 | register << 16;
        assert!(!verified(&changed, None));
    }
    let mut slot = call_image();
    slot.words[0x64 / 4] = 0x2412_0001; // corrupt the captured pointer in the caller slot
    assert!(!verified(&slot, None));
    // This slot runs only after a valid dispatch, so setting its flag to one
    // cannot enable an out-of-range first dispatch. Ordinary transfer kills it.
    slot.words[0x64 / 4] = 0x2414_0001;
    assert!(verified(&slot, None));
}
#[test]
fn a_callee_may_use_the_current_slot_but_never_another_alternate() {
    let mut same = call_image();
    same.slots.push((
        GuestRange {
            start: GuestAddr(BASE),
            size: 0x120,
        },
        BASE,
        0x100,
    ));
    assert!(verified(&same, None));
    let mut other = call_image();
    other.slots.push((
        GuestRange {
            start: GuestAddr(BASE),
            size: 0x90,
        },
        BASE,
        0x90,
    ));
    other.slots.push((
        GuestRange {
            start: GuestAddr(BASE + 0x90),
            size: 0x10,
        },
        BASE + 0x90,
        0x10,
    ));
    assert!(!verified(&other, None));
}
