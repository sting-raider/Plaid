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
        0x3c088000,
        0x15200004,
        0x34000000,
        0x35080040,
        0x0800000a,
        0x34000000,
        0x35080000 | u32::from(right_imm),
        0x0800000a,
        0x34000000,
        0x00000000,
        0x01000008,
        0x00000000,
    ])
}

fn site<'a>(m: &'a ProgramMap) -> &'a IndirectSite {
    m.indirect_sites.first().unwrap()
}

#[test]
fn equal_two_predecessor_join_is_certified_and_rechecked() {
    let i = diamond(0x0040);
    println!(
        "names branch={} slot={} jump={} jr={} nop={}",
        decode(i.words[1], GuestAddr(0x80000004)).opcode_name(),
        decode(i.words[2], GuestAddr(0x80000008)).opcode_name(),
        decode(i.words[4], GuestAddr(0x80000010)).opcode_name(),
        decode(i.words[10], GuestAddr(0x80000028)).opcode_name(),
        decode(0, GuestAddr(0x80000030)).opcode_name(),
    );
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = site(&m);
    assert_eq!(s.site.pc.0, 0x80000028);
    assert_eq!(s.candidates.first_key_value().unwrap().0.pc.0, 0x80000040);
    assert!(s.closed_proof.is_some());
    assert!(verify_constant(&m, &i, s));
    assert_eq!(m.evidence[s.closed_proof.as_ref().unwrap()].producer, "plaid-cross-block-join/v0");
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
    bypass.entries.insert(i.address(GuestAddr(0x80000018)), site(&m).evidence.clone());
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
    extra.candidates = [(i.address(GuestAddr(0x80000018)), site(&m).evidence.clone())].into();
    bypass.indirect_sites.insert(extra);
    assert!(!verify_constant(&bypass, &i, site(&m)));
}

#[test]
fn linking_control_on_one_arm_is_rejected() {
    let mut i = diamond(0x0040);
    i.words[4] = 0x0c00000a;
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert!(site(&m).closed_proof.is_none());
}

#[test]
fn equal_target_from_different_scalar_computation_is_allowed() {
    let mut i = diamond(0x0040);
    i.words[6] = 0x25080040;
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = site(&m);
    assert_eq!(s.candidates.first_key_value().unwrap().0.pc.0, 0x80000040);
    assert!(verify_constant(&m, &i, s));
}
