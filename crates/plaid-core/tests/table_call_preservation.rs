//! A call may carry a base invariant only with a rechecked callee effect proof.
use plaid_core::{GuestAddr, discovery::CodeImage, pipeline::discover_image, program::*};

const BASE: u32 = 0x80000000;

fn image() -> CodeImage {
    let mut words = vec![0; 0x400 / 4];
    words[..11].copy_from_slice(&[
        0x3c11_8000,
        0x2631_0300, // s1 table base
        0x8e04_0000,
        0x2c98_0002,
        0x1300_009b,
        0,
        0x0004_c880,
        0x0239_1021,
        0x8c59_0000,
        0x0320_0008,
        0,
    ]);
    words[0x40 / 4..0x54 / 4].copy_from_slice(&[0x0c00_0060, 0, 0x2610_0004, 0x0800_0002, 0]);
    words[0x60 / 4..0x74 / 4].copy_from_slice(&[0x0c00_0070, 0, 0x2610_0004, 0x0800_0002, 0]);
    words[0x180 / 4..0x190 / 4].copy_from_slice(&[
        0x2402_002a,
        0xae42_0000,
        0x03e0_0008,
        0x2463_0001,
    ]);
    words[0x1c0 / 4..0x1dc / 4].copy_from_slice(&[
        0x27bd_fff8,
        0xafbf_0004,
        0x0c00_0060,
        0,
        0x8fbf_0004,
        0x03e0_0008,
        0x27bd_0008,
    ]);
    words[0x280 / 4] = 0x03e0_0008;
    words[0x300 / 4] = BASE + 0x40;
    words[0x304 / 4] = BASE + 0x60;
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "callee-base".into(),
            generation: 7,
        },
        words,
        rom_offset: None,
        physical_start: None,
        holes: Vec::new(),
        slots: Vec::new(),
    }
}

fn map(image: &CodeImage, entries: &[GuestAddr]) -> ProgramMap {
    discover_image(
        RomIdentity {
            sha256: "e".repeat(64),
            size: 4096,
        },
        image,
        entries,
        10000,
    )
    .unwrap()
    .map
}

fn site(map: &ProgramMap) -> &IndirectSite {
    map.indirect_sites
        .iter()
        .find(|site| site.site.pc.0 == BASE + 0x24)
        .unwrap()
}

#[test]
fn a_table_base_survives_leaf_and_nested_calls_that_never_write_it() {
    let image = image();
    let map = map(&image, &[image.base.pc]);
    assert!(plaid_core::tables::verify(&map, &image, site(&map)));
    for offset in [0x44, 0x180, 0x18c, 0x1cc] {
        let mut changed = image.clone();
        changed.words[offset / 4] = 0x3c11_7000; // direct, return-slot or nested-call-slot clobber
        let map = self::map(&changed, &[changed.base.pc]);
        assert!(!plaid_core::tables::verify(&map, &changed, site(&map)));
    }
}

#[test]
fn callee_bytes_and_unknown_entry_paths_are_rechecked() {
    let image = image();
    let map = map(&image, &[image.base.pc]);
    assert!(plaid_core::tables::verify(&map, &image, site(&map)));
    let mut different = image.clone();
    different.words[0x180 / 4] = 0x2402_002b; // still preserves base, but changes the proof's source
    assert!(!plaid_core::tables::verify(&map, &different, site(&map)));
    let mut missing = map.clone();
    missing
        .blocks
        .retain(|block| block.start.pc.0 < BASE + 0x180);
    assert!(!plaid_core::tables::verify(&missing, &image, site(&map)));
    let entered = self::map(&image, &[image.base.pc, GuestAddr(BASE + 0x44)]);
    assert!(!plaid_core::tables::verify(
        &entered,
        &image,
        site(&entered)
    ));
    let mut unknown = image.clone();
    unknown.words[0x180 / 4] = 0x0100_0008; // unclosed jr t0 in the callee
    let map = self::map(&unknown, &[unknown.base.pc]);
    assert!(!plaid_core::tables::verify(&map, &unknown, site(&map)));
}

#[test]
fn an_unrelated_return_cannot_supply_a_call_continuation() {
    let image = image();
    let mut map = map(&image, &[image.base.pc]);
    assert!(plaid_core::tables::verify(&map, &image, site(&map)));
    let mut unrelated = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == BASE + 0x280)
        .unwrap()
        .clone();
    map.indirect_sites.remove(&unrelated);
    let mut continuation = image.base.clone();
    continuation.pc = GuestAddr(BASE + 0x48);
    unrelated
        .candidates
        .insert(continuation, unrelated.evidence.clone());
    map.indirect_sites.insert(unrelated);
    assert!(!plaid_core::tables::verify(&map, &image, site(&map)));
}
