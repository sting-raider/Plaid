use plaid_core::{GuestAddr, discovery::*, indirect::*, program::*};

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "cross-block-join".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
    }
}

fn map(i: &CodeImage) -> ProgramMap {
    direct_cfg(
        RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        },
        i,
        &[i.base.pc],
        256,
    )
    .unwrap()
    .map
}

fn diamond(right_imm: u16) -> CodeImage {
    image(vec![
        0x3c088000,             // lui   t0,0x8000
        0x15200004,             // bnez  t1,right
        0x00000000,             // nop
        0x35080040,             // ori   t0,t0,0x40   (left)
        0x0800000a,             // j     join
        0x00000000,             // nop
        0x35080000 | u32::from(right_imm), // ori t0,t0,right_imm
        0x0800000a,             // j     join
        0x00000000,             // nop
        0x00000000,             // padding
        0x01000008,             // join: jr t0
        0x00000000,             // nop
    ])
}

fn site<'a>(m: &'a ProgramMap) -> &'a IndirectSite {
    m.indirect_sites.first().unwrap()
}

#[test]
fn equal_two_predecessor_join_is_certified_and_rechecked() {
    let i = diamond(0x0040);
    let base = map(&i);
    println!("entries={:#?}", base.entries.keys().collect::<Vec<_>>());
    println!("blocks={:#?}", base.blocks);
    println!("edges={:#?}", base.direct_edges);
    println!("indirect={:#?}", base.indirect_sites);
    let m = analyze_indirect(&base, &i).unwrap();
    println!("analyzed_indirect={:#?}", m.indirect_sites);
    let s = site(&m);
    assert_eq!(s.site.pc.0, 0x80000028);
    assert_eq!(s.candidates.first_key_value().unwrap().0.pc.0, 0x80000040);
    assert!(s.closed_proof.is_some());
    assert!(verify_constant(&m, &i, s));
    assert_eq!(
        m.evidence[s.closed_proof.as_ref().unwrap()].producer,
        "plaid-cross-block-join/v0"
    );
}

#[test]
fn divergent_two_predecessor_join_is_not_certified() {
    let i = diamond(0x0080);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = site(&m);
    assert!(s.closed_proof.is_none());
    assert!(s.candidates.is_empty());
}

#[test]
fn stale_join_proof_fails_when_one_arm_changes() {
    let i = diamond(0x0040);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert!(site(&m).closed_proof.is_some());
    let mut changed = i.clone();
    changed.words[6] = 0x35080080;
    assert!(!verify_constant(&m, &changed, site(&m)));
}

#[test]
fn alternate_entry_into_one_arm_invalidates_join_proof() {
    let i = diamond(0x0040);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let mut bypass = m.clone();
    bypass.entries.insert(
        i.address(GuestAddr(0x80000018)),
        site(&m).evidence.clone(),
    );
    assert!(!verify_constant(&bypass, &i, site(&m)));
}

#[test]
fn indirect_candidate_into_one_arm_invalidates_join_proof() {
    let i = diamond(0x0040);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let mut bypass = m.clone();
    let mut extra = site(&m).clone();
    extra.site = i.address(GuestAddr(0x80000030));
    extra.closed_proof = None;
    extra.candidates = [(
        i.address(GuestAddr(0x80000018)),
        site(&m).evidence.clone(),
    )]
    .into();
    bypass.indirect_sites.insert(extra);
    assert!(!verify_constant(&bypass, &i, site(&m)));
}

#[test]
fn linking_control_on_one_arm_is_rejected() {
    let mut i = diamond(0x0040);
    i.words[4] = 0x0c00000a; // jal join, not a plain non-linking edge
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert!(site(&m).closed_proof.is_none());
}

#[test]
fn equal_target_from_different_scalar_computation_is_allowed() {
    let mut i = diamond(0x0040);
    i.words[6] = 0x25080040; // addiu t0,t0,0x40 instead of ori; same target value
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = site(&m);
    assert_eq!(s.candidates.first_key_value().unwrap().0.pc.0, 0x80000040);
    assert!(verify_constant(&m, &i, s));
}
