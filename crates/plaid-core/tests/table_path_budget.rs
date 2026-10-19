//! Long, finite case paths preserve the same preheader invariant.
use plaid_core::{GuestAddr, discovery::CodeImage, pipeline::discover_image, program::*};

const BASE: u32 = 0x80000000;

fn image(chain: usize, clobber: bool) -> CodeImage {
    let jump = |target: u32| 0x08000000 | ((BASE + target) >> 2 & 0x03ffffff);
    let mut words = vec![0; 0x400 / 4];
    words[..11].copy_from_slice(&[
        0x3c01_8000,
        0x2421_0300, // initialized table base
        0x8e04_0000,
        0x2c98_0002, // retry: memory index, index < 2
        0x1300_009b,
        0, // beq flag,zero,exit
        0x0004_c880,
        0x0039_1021,
        0x8c59_0000,
        0x0320_0008,
        0,
    ]);
    for n in 0..chain {
        let at = 0x40 + n * 8;
        words[at / 4] = jump(if n + 1 == chain { 8 } else { at as u32 + 8 });
        words[at / 4 + 1] = if clobber && n == chain / 2 {
            0x3c01_7000 // incompatible base on the case backedge
        } else if n + 1 == chain {
            0x2610_0004 // advance inputs after case zero
        } else {
            0
        };
    }
    words[0x240 / 4] = jump(8);
    words[0x244 / 4] = 0x2610_0004;
    words[0x280 / 4] = 0x03e0_0008;
    words[0x300 / 4] = BASE + 0x40;
    words[0x304 / 4] = BASE + 0x240;
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "long-case-path".into(),
            generation: 5,
        },
        words,
        rom_offset: None,
        physical_start: None,
        holes: Vec::new(),
        slots: Vec::new(),
    }
}

fn verified(image: &CodeImage, entries: &[GuestAddr]) -> bool {
    let map = discover_image(
        RomIdentity {
            sha256: "c".repeat(64),
            size: 4096,
        },
        image,
        entries,
        10000,
    )
    .unwrap()
    .map;
    let site = map
        .indirect_sites
        .iter()
        .find(|site| site.site.pc.0 == BASE + 0x24)
        .unwrap();
    plaid_core::tables::verify(&map, image, site)
}

#[test]
fn a_long_finite_case_path_retains_the_preheader_base() {
    let image = image(24, false);
    assert!(verified(&image, &[image.base.pc]));
}

#[test]
fn longer_search_keeps_clobber_entry_and_resource_limit_rejections() {
    let changed = image(24, true);
    assert!(!verified(&changed, &[changed.base.pc]));
    let unknown = image(24, false);
    assert!(!verified(
        &unknown,
        &[unknown.base.pc, GuestAddr(BASE + 0x80)]
    ));
    let limited = image(40, false);
    assert!(!verified(&limited, &[limited.base.pc]));
}
