use plaid_core::{GuestAddr, discovery::*, indirect::*, program::*};

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "constant-test".into(),
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
        100,
    )
    .unwrap()
    .map
}

#[test]
fn local_constant_target_is_certified_before_delay_slot_write() {
    let i = image(vec![0x3c088000, 0x35080020, 0x01000008, 0x35080040]);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = m.indirect_sites.first().unwrap();
    assert_eq!(s.candidates.keys().next().unwrap().pc.0, 0x80000020);
    assert!(verify_constant(&m, &i, s));
    let mut changed = i.clone();
    changed.words[1] = 0x35080024;
    assert!(!verify_constant(&m, &changed, s));
}

#[test]
fn loads_kill_values_and_midblock_entries_prevent_a_proof() {
    let i = image(vec![0x3c088000, 0x8d080000, 0x01000008, 0]);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert!(m.indirect_sites.first().unwrap().closed_proof.is_none());
    let i = image(vec![0x3c088000, 0x35080020, 0x01000008, 0]);
    let mut m = map(&i);
    m.entries.insert(
        i.address(GuestAddr(0x80000004)),
        m.entries.values().next().unwrap().clone(),
    );
    let m = analyze_indirect(&m, &i).unwrap();
    assert!(m.indirect_sites.first().unwrap().closed_proof.is_none());
}

#[test]
fn finite_observation_disagreement_prevents_closure() {
    let i = image(vec![0x3c088000, 0x35080020, 0x01000008, 0]);
    let mut m = map(&i);
    let mut s = m.indirect_sites.pop_first().unwrap();
    s.observed
        .insert(i.address(GuestAddr(0x80000040)), s.evidence.clone());
    m.indirect_sites.insert(s);
    let m = analyze_indirect(&m, &i).unwrap();
    let s = m.indirect_sites.first().unwrap();
    assert_eq!(s.observed.len(), 1);
    assert_eq!(s.candidates.len(), 1);
    assert!(s.closed_proof.is_none());
}

#[test]
fn zero_register_and_word_sign_extension_are_preserved() {
    let i = image(vec![0x3c088001, 0x2508fff0, 0x01000008, 0]);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert_eq!(
        m.indirect_sites
            .first()
            .unwrap()
            .candidates
            .keys()
            .next()
            .unwrap()
            .pc
            .0,
        0x8000fff0
    );
    let i = image(vec![0x34008000, 0x00000008, 0]); // attempted write to zero then JR zero
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert_eq!(
        m.indirect_sites
            .first()
            .unwrap()
            .candidates
            .keys()
            .next()
            .unwrap()
            .pc
            .0,
        0
    );
}

#[test]
fn unaligned_or_unknown_targets_never_get_a_certificate() {
    let i = image(vec![0x34080001, 0x01000008, 0]);
    assert!(
        analyze_indirect(&map(&i), &i)
            .unwrap()
            .indirect_sites
            .first()
            .unwrap()
            .closed_proof
            .is_none()
    );
    let i = image(vec![0x03e00008, 0]);
    assert!(
        analyze_indirect(&map(&i), &i)
            .unwrap()
            .indirect_sites
            .first()
            .unwrap()
            .closed_proof
            .is_none()
    );
}

#[test]
fn candidate_reentry_into_its_own_prefix_prevents_closure() {
    let i = image(vec![0x3c088000, 0x35080004, 0x01000008, 0]);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = m.indirect_sites.first().unwrap();
    assert_eq!(s.candidates.len(), 1);
    assert!(s.closed_proof.is_none());
}

#[test]
fn jalr_target_precedes_link_write_and_link_metadata_is_rechecked() {
    let i = image(vec![0x3c088000, 0x35080000, 0x01004009, 0]);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = m.indirect_sites.first().unwrap();
    assert_eq!(s.link_register, Some(8));
    assert_eq!(s.candidates.keys().next().unwrap().pc.0, 0x80000000);
    assert!(verify_constant(&m, &i, s));
    let mut bad = s.clone();
    bad.link_register = None;
    assert!(!verify_constant(&m, &i, &bad));
}

#[test]
fn cross_block_jump_propagates_slot_value_and_rechecks_new_entries() {
    let i = image(vec![
        0x3c088000, 0x08000004, 0x35080040, 0, 0x01000008, 0x35080080,
    ]);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = m.indirect_sites.first().unwrap();
    assert_eq!(s.candidates.first_key_value().unwrap().0.pc.0, 0x80000040);
    assert!(verify_constant(&m, &i, s));
    assert_eq!(
        m.evidence[s.closed_proof.as_ref().unwrap()].producer,
        "plaid-cross-block-constant/v0"
    );
    let mut changed = i.clone();
    changed.words[2] = 0x35080080;
    assert!(!verify_constant(&m, &changed, s));
    let mut bypass = m.clone();
    bypass
        .entries
        .insert(i.address(GuestAddr(0x80000010)), s.evidence.clone());
    assert!(!verify_constant(&bypass, &i, s));
    let mut candidate = m.clone();
    let mut extra = s.clone();
    extra.site = i.address(GuestAddr(0x80000030));
    extra.closed_proof = None;
    extra.candidates = [(i.address(GuestAddr(0x80000010)), s.evidence.clone())].into();
    candidate.indirect_sites.insert(extra);
    assert!(!verify_constant(&candidate, &i, s));
}

#[test]
fn cross_block_branch_likely_propagates_distinct_slot_paths() {
    let i = image(vec![
        0x3c088000, 0x35080040, 0x512a0005, 0x35080080, 0x01000008, 0, 0, 0, 0x01000008, 0,
    ]);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert_eq!(m.indirect_sites.len(), 2);
    for s in &m.indirect_sites {
        let target = if s.site.pc.0 == 0x80000010 {
            0x80000040
        } else {
            0x800000c0
        };
        assert_eq!(s.candidates.first_key_value().unwrap().0.pc.0, target);
        assert!(verify_constant(&m, &i, s));
    }
    let mut ordinary = i.clone();
    ordinary.words[2] = 0x152a0005;
    let m = analyze_indirect(&map(&ordinary), &ordinary).unwrap();
    assert!(
        m.indirect_sites
            .iter()
            .all(|s| s.candidates.first_key_value().unwrap().0.pc.0 == 0x800000c0)
    );
}

#[test]
fn cross_block_joins_calls_and_effects_remain_unknown_even_if_edges_are_deleted() {
    let join = image(vec![
        0x3c088000, 0x15200004, 0, 0x35080040, 0x0800000a, 0, 0x35080080, 0x0800000a, 0, 0,
        0x01000008, 0,
    ]);
    let mut m = map(&join);
    assert!(
        analyze_indirect(&m, &join)
            .unwrap()
            .indirect_sites
            .first()
            .unwrap()
            .closed_proof
            .is_none()
    );
    m.direct_edges.retain(|e| e.site.pc.0 != 0x8000001c);
    assert!(
        analyze_indirect(&m, &join)
            .unwrap()
            .indirect_sites
            .first()
            .unwrap()
            .closed_proof
            .is_none()
    );
    let calls = image(vec![
        0x3c088000, 0x0c000008, 0, 0x08000005, 0, 0x01000008, 0, 0, 0x03e00008, 0,
    ]);
    assert!(
        analyze_indirect(&map(&calls), &calls)
            .unwrap()
            .indirect_sites
            .iter()
            .all(|s| s.closed_proof.is_none())
    );
    let store = image(vec![0x3c088000, 0xad000000, 0x08000004, 0, 0x01000008, 0]);
    assert!(
        analyze_indirect(&map(&store), &store)
            .unwrap()
            .indirect_sites
            .first()
            .unwrap()
            .closed_proof
            .is_none()
    );
}
