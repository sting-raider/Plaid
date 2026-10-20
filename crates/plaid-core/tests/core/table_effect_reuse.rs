//! Repeated calls reuse a source-bound effect, never authority from another walk.
use plaid_core::{GuestAddr, discovery::CodeImage, pipeline::discover_image, program::*};

fn fixture() -> CodeImage {
    let mut words = vec![0; 0x2000 / 4];
    words[..11].copy_from_slice(&[
        0x3c11_8000,
        0x2631_1800, // table base lives across every case
        0x8e04_0000,
        0x2c98_0002,
        0x1300_00fa,
        0,
        0x0004_c880,
        0x0239_1021,
        0x8c59_0000,
        0x0320_0008,
        0,
    ]);
    for case in [0x100, 0x200] {
        for n in 0..8 {
            words[case / 4 + n * 2] = 0x0c00_0400; // same ordinary guest leaf
        }
        words[case / 4 + 16..case / 4 + 20].copy_from_slice(&[0x2610_0004, 0x0800_0002, 0, 0]);
    }
    words[0x400 / 4] = 0x03e0_0008;
    words[0x1000 / 4 + 300] = 0x03e0_0008;
    words[0x1800 / 4] = 0x8000_0100;
    words[0x1804 / 4] = 0x8000_0200;
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "effect-reuse".into(),
            generation: 2,
        },
        words,
        rom_offset: None,
        physical_start: None,
        holes: Vec::new(),
        slots: Vec::new(),
    }
}

fn discover(image: &CodeImage) -> ProgramMap {
    discover_image(
        RomIdentity {
            sha256: "c".repeat(64),
            size: 0x2000,
        },
        image,
        &[image.base.pc],
        10000,
    )
    .unwrap()
    .map
}

fn verified(map: &ProgramMap, image: &CodeImage) -> bool {
    let site = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x8000_0024)
        .unwrap();
    plaid_core::tables::verify(map, image, site)
}

#[test]
fn identical_effect_queries_do_not_exhaust_the_shared_read_budget() {
    let image = fixture();
    let map = discover(&image);
    assert!(verified(&map, &image));
    let mut changed = image.clone();
    changed.words[0x1000 / 4 + 100] = 0x2402_0001; // harmless write still changes the source hash
    assert!(!verified(&map, &changed));
    assert!(verified(&discover(&changed), &changed));
}

#[test]
fn changed_callee_and_caller_delay_slot_effects_are_never_reused() {
    for offset in [0x1000 + 100 * 4, 0x104, 0x204] {
        let mut image = fixture();
        image.words[offset / 4] = 0x2411_0000; // clobber the required table base
        assert!(!verified(&discover(&image), &image));
    }
    let mut image = fixture();
    image.words[0x200 / 4] = 0x0c00_0580; // a different leaf that writes the base
    image.words[0x1600 / 4] = 0x2411_0000;
    image.words[0x1604 / 4] = 0x03e0_0008;
    assert!(!verified(&discover(&image), &image));
}

#[test]
fn distinct_entries_with_a_shared_return_require_distinct_effects() {
    for case in [0x100, 0x200] {
        let mut image = fixture();
        image.words[case / 4] = 0x0c00_03ff; // clobbering prefix, then the ordinary leaf
        image.words[0xffc / 4] = 0x2411_0000;
        // Later calls in this arm query the nonwriting entry first, backwards.
        // Both entries share a return witness, so it cannot distinguish them.
        assert!(!verified(&discover(&image), &image));
    }
}
