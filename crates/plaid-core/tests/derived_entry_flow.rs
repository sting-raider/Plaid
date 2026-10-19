//! Decoder roots retain their control-flow origins; explicit entries stay barriers.
use plaid_core::{
    GuestAddr,
    discovery::CodeImage,
    pipeline::discover_image,
    program::{CodeAddress, RomIdentity},
};
use std::collections::BTreeSet;

const BASE: u32 = 0x80000000;

fn fixture() -> CodeImage {
    let mut words = vec![0; 0x200 / 4];
    let head = [
        0x3c01_8000, // lui at,8000
        0x2421_0100, // addiu at,at,table
        0x8e04_0000, // retry: lw a0,0(s0)
        0x2c98_0002, // sltiu t8,a0,2
        0x1300_001b, // beq t8,zero,exit(80)
        0,
        0x0004_c880, // sll t9,a0,2
        0x0039_1021, // addu v0,at,t9
        0x8c59_0000, // lw t9,0(v0)
        0x0320_0008, // jr t9
        0,
    ];
    words[..head.len()].copy_from_slice(&head);
    words[0x40 / 4..0x4c / 4].copy_from_slice(&[
        0x2610_0004, // case0: addiu s0,s0,4
        0x0800_0002, // j retry
        0,
    ]);
    words[0x50 / 4..0x64 / 4].copy_from_slice(&[
        0x3c0d_8000, // case1: a newly decoded function pointer
        0x25ad_0180,
        0x2610_0004,
        0x0800_0002,
        0,
    ]);
    words[0x80 / 4] = 0x03e0_0008;
    words[0x100 / 4] = BASE + 0x40;
    words[0x104 / 4] = BASE + 0x50;
    words[0x178 / 4] = 0x03e0_0008;
    words[0x180 / 4] = 0x03e0_0008;
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "derived-entry-flow".into(),
            generation: 3,
        },
        words,
        rom_offset: None,
        physical_start: None,
        holes: Vec::new(),
        slots: Vec::new(),
    }
}

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "d".repeat(64),
        size: 4096,
    }
}

#[test]
fn case_backedges_preserve_the_initialized_base() {
    let image = fixture();
    let map = discover_image(rom(), &image, &[image.base.pc], 10000)
        .unwrap()
        .map;
    let site = map
        .indirect_sites
        .iter()
        .find(|site| site.site.pc.0 == BASE + 0x24)
        .unwrap();
    assert!(plaid_core::tables::verify(&map, &image, site));

    for extra in [BASE + 0x40, BASE + 0x18] {
        let map = discover_image(rom(), &image, &[image.base.pc, GuestAddr(extra)], 10000)
            .unwrap()
            .map;
        let site = map
            .indirect_sites
            .iter()
            .find(|site| site.site.pc.0 == BASE + 0x24)
            .unwrap();
        assert!(!plaid_core::tables::verify(&map, &image, site));
    }
}

#[test]
fn a_forged_tag_cannot_erase_a_merged_explicit_entry() {
    let image = fixture();
    let ordinary = discover_image(rom(), &image, &[image.base.pc], 10000)
        .unwrap()
        .map;
    let explicit = discover_image(
        rom(),
        &image,
        &[image.base.pc, GuestAddr(BASE + 0x40)],
        10000,
    )
    .unwrap()
    .map;
    let mut merged = plaid_core::merge::merge_maps(&ordinary, &explicit).unwrap();
    let proof = ordinary
        .indirect_sites
        .iter()
        .find(|site| site.site.pc.0 == BASE + 0x24)
        .unwrap();
    assert!(!plaid_core::tables::verify(&merged, &image, proof));
    merged.derived_entries.insert(
        image.address(GuestAddr(BASE + 0x40)),
        [proof.site.clone()].into(),
    );
    assert!(!plaid_core::tables::verify(&merged, &image, proof));
}

#[test]
fn another_address_taken_round_retains_candidate_origins() {
    let image = fixture();
    let bytes: Vec<u8> = image.words.iter().flat_map(|w| w.to_be_bytes()).collect();
    let map = plaid_core::data_roots::discover_address_taken(
        rom(),
        &bytes,
        &image,
        &[image.base.pc],
        &[],
        None,
        &BTreeSet::new(),
        10000,
    )
    .unwrap()
    .map;
    assert!(
        map.address_taken
            .contains_key(&image.address(GuestAddr(BASE + 0x180)))
    );
    let site = map
        .indirect_sites
        .iter()
        .find(|site| site.site.pc.0 == BASE + 0x24)
        .unwrap();
    assert_eq!(site.candidates.len(), 2);
    assert!(plaid_core::tables::verify(&map, &image, site));
}

#[test]
fn case_origins_never_override_unknown_entries_or_changed_bytes() {
    let image = fixture();
    let map = discover_image(rom(), &image, &[image.base.pc], 10000)
        .unwrap()
        .map;
    let site = map
        .indirect_sites
        .iter()
        .find(|site| site.site.pc.0 == BASE + 0x24)
        .unwrap();
    assert!(plaid_core::tables::verify(&map, &image, site));
    let case = image.address(GuestAddr(BASE + 0x40));
    assert!(map.derived_entries.contains_key(&case));

    let mut missing = map.clone();
    missing.derived_entries.remove(&case);
    assert!(!plaid_core::tables::verify(&missing, &image, site));

    let mut foreign = map.clone();
    let mut parent = site.site.clone();
    parent.generation += 1;
    foreign
        .derived_entries
        .insert(case.clone(), [parent].into());
    assert!(!plaid_core::tables::verify(&foreign, &image, site));

    let mut taken = map.clone();
    taken.address_taken.insert(case, site.evidence.clone());
    assert!(!plaid_core::tables::verify(&taken, &image, site));

    for offset in [0x40, 0x48] {
        let mut changed = image.clone();
        changed.words[offset / 4] = 0x3c01_7000; // case body or JR delay slot clobbers base
        assert!(!plaid_core::tables::verify(&map, &changed, site));
    }
    let mut rebound = image.clone();
    rebound.slots.push((
        plaid_core::program::GuestRange {
            start: GuestAddr(BASE + 0x40),
            size: 0x0c,
        },
        BASE + 0x40,
        0x0c,
    ));
    assert!(!plaid_core::tables::verify(&map, &rebound, site));
}

#[test]
fn every_incoming_indirect_edge_must_preserve_the_predicate() {
    use plaid_core::program::{BasicBlock, DelaySlot, IndirectSite};
    let mut image = fixture();
    image.words[0x1c0 / 4] = 0x0100_0008; // jr t0 from an otherwise unknown-state root
    let mut map = discover_image(rom(), &image, &[image.base.pc], 10000)
        .unwrap()
        .map;
    let dispatch = map
        .indirect_sites
        .iter()
        .find(|site| site.site.pc.0 == BASE + 0x24)
        .unwrap()
        .clone();
    assert!(plaid_core::tables::verify(&map, &image, &dispatch));
    let source = image.address(GuestAddr(BASE + 0x1c0));
    map.entries
        .insert(source.clone(), dispatch.evidence.clone());
    map.blocks.insert(BasicBlock {
        start: source.clone(),
        size: 8,
        delay_slot_entry: false,
        evidence: dispatch.evidence.clone(),
    });
    let case = image.address(GuestAddr(BASE + 0x40));
    for observed in [false, true] {
        let mut altered = map.clone();
        altered.indirect_sites.insert(IndirectSite {
            site: source.clone(),
            link_register: None,
            delay_slot: DelaySlot::Always,
            candidates: if observed {
                Default::default()
            } else {
                [(case.clone(), dispatch.evidence.clone())].into()
            },
            observed: if observed {
                [(case.clone(), dispatch.evidence.clone())].into()
            } else {
                Default::default()
            },
            closed_proof: None,
            evidence: dispatch.evidence.clone(),
        });
        assert!(
            !plaid_core::tables::verify(&altered, &image, &dispatch),
            "observed={observed}"
        );
    }
}

#[test]
fn callback_entries_remain_external_even_with_a_forged_origin_tag() {
    use plaid_core::{EvidenceKind, program::Evidence};
    let mut image = fixture();
    image.words[0x1a0 / 4..0x1b8 / 4].copy_from_slice(&[
        0x3c04_8000,
        0x2484_0040, // a0 = case0 callback
        0x0c00_0078,
        0, // jal declared runtime function at 1e0
        0x0800_0000,
        0, // j initialized preheader
    ]);
    image.words[0x1e0 / 4] = 0x03e0_0008;
    let ordinary = discover_image(rom(), &image, &[image.base.pc], 10000)
        .unwrap()
        .map;
    let dispatch = ordinary
        .indirect_sites
        .iter()
        .find(|site| site.site.pc.0 == BASE + 0x24)
        .unwrap()
        .clone();
    assert!(plaid_core::tables::verify(&ordinary, &image, &dispatch));
    let mut callbacks = plaid_core::pipeline::discover_image_with_runtime(
        rom(),
        &image,
        &[GuestAddr(BASE + 0x1a0)],
        &[(
            GuestAddr(BASE + 0x1e0),
            "synthetic_callback".into(),
            vec![4],
        )],
        Some((
            "sdk".into(),
            Evidence {
                kind: EvidenceKind::Signature,
                producer: "authored".into(),
                revision: "0".into(),
                detail: "authored callback declaration".into(),
            },
        )),
        10000,
    )
    .unwrap()
    .map;
    let case = image.address(GuestAddr(BASE + 0x40));
    assert!(plaid_core::callbacks::targets(&callbacks, &image).contains(&case));
    assert!(!callbacks.derived_entries.contains_key(&case));
    // Even a formerly valid internal-entry witness cannot hide a callback
    // newly established by the current SDK call facts and instruction bytes.
    callbacks
        .entries
        .insert(case.clone(), ordinary.entries[&case].clone());
    callbacks
        .derived_entries
        .insert(case, [dispatch.site.clone()].into());
    callbacks.evidence.extend(ordinary.evidence.clone());
    // A current byte/CFG verification must still reject the former certificate.
    assert!(!plaid_core::tables::verify(&callbacks, &image, &dispatch));
}
