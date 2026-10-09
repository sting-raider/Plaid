use plaid_core::{GuestAddr, discovery::*, indirect::*, pipeline::*, program::*};

fn image() -> CodeImage {
    let mut words = vec![0; 67];
    words[..10].copy_from_slice(&[
        0x2c890003, 0x11200016, 0, 0x3c088000, 0x25080100, 0x00045080, 0x010a4021, 0x8d080000,
        0x01000008, 0,
    ]);
    for offset in [0x40, 0x50, 0x60] {
        words[offset / 4] = 0x08000000 | (offset as u32 / 4);
    }
    words[64..].copy_from_slice(&[0x80000040, 0x80000050, 0x80000040]);
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "prefix-bypass".into(),
            generation: 0,
        },
        words,
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
    }
}

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "b".repeat(64),
        size: 4096,
    }
}

fn map(i: &CodeImage) -> ProgramMap {
    direct_cfg(rom(), i, &[i.base.pc], 1000).unwrap().map
}

fn candidates(map: &ProgramMap) -> Vec<u32> {
    map.indirect_sites
        .iter()
        .find(|site| site.site.pc == GuestAddr(0x80000020))
        .unwrap()
        .candidates
        .keys()
        .map(|address| address.pc.0)
        .collect()
}

#[test]
fn baseline_valid_mid_prefix_entry_still_receives_pointer_candidates() {
    let i = image();
    let mut m = map(&i);
    let evidence = m.entries.values().next().unwrap().clone();
    m.entries
        .insert(i.address(GuestAddr(0x80000014)), evidence);

    // The portable ProgramMap contract accepts this provenance-bearing entry even
    // though it lands after the selected guard edge and before the JR site.
    m.validate().unwrap();

    let analyzed = analyze_indirect(&m, &i).unwrap();
    assert_eq!(
        candidates(&analyzed),
        [0x80000040, 0x80000050],
        "baseline changed: the unpatched recognizer no longer reproduces the bypass"
    );
}

#[test]
fn direct_discovery_repartitions_a_declared_mid_prefix_root() {
    let i = image();
    let discovered = discover_image(
        rom(),
        &i,
        &[i.base.pc, GuestAddr(0x80000014)],
        1000,
    )
    .unwrap();

    assert!(
        discovered
            .map
            .blocks
            .iter()
            .any(|block| block.start.pc == GuestAddr(0x80000014))
    );
    assert!(
        candidates(&discovered.map).is_empty(),
        "fixed-point direct discovery should repartition the bypass as a block leader"
    );
}
