//! The offset and guarded index can advance together without another SLL.
use plaid_core::{GuestAddr, discovery::CodeImage, pipeline::discover_image, program::*};
const BASE: u32 = 0x80000000;
fn image() -> CodeImage {
    let mut words = vec![0; 0x120 / 4];
    words[..12].copy_from_slice(&[
        0x0000_982d, // s3 = 0
        0x0260_a02d, // s4 = s3 (index)
        0x0260_a82d, // s5 = s3 (byte offset)
        0,
        0x2e82_0003,
        0x1040_001e,
        0,
        0x3c02_8000,
        0x0055_1021,
        0x8c42_0100,
        0x0040_0008,
        0,
    ]);
    for (offset, value) in [(0x40, 1), (0x50, 10), (0x60, 100)] {
        words[offset / 4..offset / 4 + 3].copy_from_slice(&[0x2631_0000 | value, 0x0800_001c, 0]);
    }
    words[0x70 / 4..0x80 / 4].copy_from_slice(&[0x26b5_0004, 0x2694_0001, 0x0800_0004, 0]);
    words[0x90 / 4] = 0x03e0_0008;
    words[0xb0 / 4..0xbc / 4].copy_from_slice(&[0x2404_0063, 0x03e0_0008, 0]);
    words[0x100 / 4..0x10c / 4].copy_from_slice(&[BASE + 0x40, BASE + 0x50, BASE + 0x60]);
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "affine-index".into(),
            generation: 1,
        },
        words,
        rom_offset: None,
        physical_start: None,
        holes: vec![],
        slots: vec![],
    }
}
fn mapped(image: &CodeImage, extra: Option<u32>) -> ProgramMap {
    let mut entries = vec![image.base.pc];
    entries.extend(extra.map(|pc| GuestAddr(BASE + pc)));
    discover_image(
        RomIdentity {
            sha256: "f".repeat(64),
            size: 4096,
        },
        image,
        &entries,
        10000,
    )
    .unwrap()
    .map
}
fn verified(image: &CodeImage, extra: Option<u32>) -> bool {
    let map = mapped(image, extra);
    let site = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == BASE + 0x28)
        .unwrap();
    plaid_core::tables::verify(&map, image, site)
}
#[test]
fn paired_index_and_offset_updates_retain_the_scale_relation() {
    assert!(verified(&image(), None));
}
#[test]
fn the_initial_values_and_every_update_must_satisfy_the_same_relation() {
    for (at, word) in [(8, 0x2415_0004), (0x70, 0x26b5_0008), (0x74, 0x2694_0002)] {
        let mut changed = image();
        changed.words[at / 4] = word;
        assert!(!verified(&changed, None), "mismatched relation at {at:x}");
    }
}
#[test]
fn an_external_loop_entry_cannot_assume_the_relation() {
    assert!(!verified(&image(), Some(0x10)));
}
#[test]
fn variable_shift_constants_are_transferred_once_while_a_relation_is_live() {
    for (initial, expected) in [(0, false), (1, true)] {
        let mut changed = image();
        changed.words[..4].copy_from_slice(&[
            0x0280_402d, // t0 copies the still-unknown guarded index s4
            0x2406_0000 | initial,
            0x24c6_0001, // amount += 1, exactly once
            0x00c8_a804, // s5 = t0 << amount
        ]);
        assert_eq!(
            verified(&changed, None),
            expected,
            "initial shift {initial}"
        );
    }
}
#[test]
fn calls_must_preserve_all_live_relation_registers() {
    let mut call = image();
    call.words[0x40 / 4..0x50 / 4].copy_from_slice(&[0x0c00_002c, 0, 0x0800_001c, 0]);
    assert!(verified(&call, None));
    for r in [20u32, 21] {
        let mut changed = call.clone();
        changed.words[0xb0 / 4] = 0x2400_0063 | r << 16;
        assert!(!verified(&changed, None), "callee clobbers r{r}");
    }
}

#[test]
fn a_slot_call_to_fixed_text_checks_the_callee_return() {
    let mut call = image();
    call.words[0x40 / 4..0x50 / 4].copy_from_slice(&[0x0c00_002c, 0, 0x0800_001c, 0]);
    call.slots.push((
        GuestRange {
            start: GuestAddr(BASE),
            size: 0xa0,
        },
        BASE,
        0xa0,
    ));
    assert!(verified(&call, None));
    call.words[0xb0 / 4] = 0x2415_0063; // fixed callee corrupts the offset
    assert!(!verified(&call, None));
}

#[test]
fn an_unrelated_fixed_return_still_needs_a_callee_witness() {
    let mut call = image();
    call.words[0x40 / 4..0x50 / 4].copy_from_slice(&[0x0c00_002c, 0, 0x0800_001c, 0]);
    call.words[0xd0 / 4] = 0x03e0_0008;
    call.slots.push((
        GuestRange {
            start: GuestAddr(BASE),
            size: 0xa0,
        },
        BASE,
        0xa0,
    ));
    assert!(verified(&call, Some(0xd0)));
    let mut map = mapped(&call, Some(0xd0));
    let mut other = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == BASE + 0xd0)
        .unwrap()
        .clone();
    map.indirect_sites.remove(&other);
    other
        .candidates
        .insert(call.address(GuestAddr(BASE + 0x48)), other.evidence.clone());
    map.indirect_sites.insert(other);
    let map = plaid_core::indirect::analyze_indirect(&map, &call).unwrap();
    let site = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == BASE + 0x28)
        .unwrap();
    assert!(!plaid_core::tables::verify(&map, &call, site));
}

#[test]
fn fixed_return_reads_do_not_admit_another_alternate_or_a_data_tail() {
    let mut call = image();
    call.words[0x40 / 4..0x50 / 4].copy_from_slice(&[0x0c00_002c, 0, 0x0800_001c, 0]);
    call.slots.push((
        GuestRange {
            start: GuestAddr(BASE),
            size: 0xa0,
        },
        BASE,
        0xa0,
    ));
    assert!(verified(&call, None));
    let mut other = call.clone();
    other.slots.push((
        GuestRange {
            start: GuestAddr(BASE + 0xb0),
            size: 0x10,
        },
        BASE + 0xb0,
        0x10,
    ));
    assert!(!verified(&other, None));
    call.slots[0].0.size = 0x120; // leaf bytes now lie beyond this binding's text
    assert!(!verified(&call, None));
}
