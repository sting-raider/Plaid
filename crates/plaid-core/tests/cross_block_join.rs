use plaid_core::{GuestAddr, discovery::*, indirect::*, program::*, solver::*};

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
        holes: Vec::new(),
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
        0x3c088000,                        // lui   t0,0x8000
        0x152a0004,                        // bne   t1,t2,right (avoid Rabbitizer bnez pseudo)
        0x34000000, // ori   zero,zero,0 (semantic nop with canonical scalar opcode)
        0x35080040, // ori   t0,t0,0x40 (left)
        0x0800000a, // j     join
        0x34000000, // ori   zero,zero,0
        0x35080000 | u32::from(right_imm), // ori t0,t0,right_imm
        0x0800000a, // j     join
        0x34000000, // ori   zero,zero,0
        0x00000000, // unreachable padding
        0x01000008, // join: jr t0
        0x00000000, // final JR slot is outside target-value proof
    ])
}

fn entry_target_diamond() -> CodeImage {
    let mut i = diamond(0x0000);
    i.words[3] = 0x35080000; // left also targets 0x80000000
    i
}

fn site(m: &ProgramMap) -> &IndirectSite {
    m.indirect_sites.first().unwrap()
}

#[test]
fn equal_two_predecessor_join_is_certified_and_rechecked() {
    let i = diamond(0x0040);
    let m = analyze_indirect(&map(&i), &i).unwrap();
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
fn deleting_one_required_edge_invalidates_join_proof() {
    let i = diamond(0x0040);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let mut deleted = m.clone();
    deleted
        .direct_edges
        .retain(|edge| edge.site.pc.0 != 0x8000001c);
    assert!(!verify_constant(&deleted, &i, site(&m)));
}

#[test]
fn alternate_entry_into_one_arm_invalidates_join_proof() {
    let i = diamond(0x0040);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let mut bypass = m.clone();
    bypass
        .entries
        .insert(i.address(GuestAddr(0x80000018)), site(&m).evidence.clone());
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
    i.words[4] = 0x0c00000a; // jal join, not a plain non-linking edge
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert!(site(&m).closed_proof.is_none());
}

#[test]
fn loop_on_path_is_rejected() {
    let i = image(vec![
        0x3c088000, // entry: lui t0,0x8000
        0x152affff, // loop: bne t1,t2,loop
        0x34000000, // delay slot
        0x35080040, // exit: ori t0,t0,0x40
        0x01000008, // jr t0
        0x00000000,
    ]);
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

#[test]
fn equal_join_removes_declared_static_indirect_blocker() {
    let i = entry_target_diamond();
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert!(verify_constant(&m, &i, site(&m)));
    assert_eq!(
        solve(&m, std::slice::from_ref(&i), Scope::DeclaredStaticImages)
            .unwrap()
            .status,
        ClosureStatus::Closed
    );
}

#[test]
fn final_jr_delay_slot_remains_separate_closure_obligation() {
    let mut i = entry_target_diamond();
    i.words[11] = 0x0000000c; // syscall in JR delay slot
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert!(site(&m).closed_proof.is_some());
    assert_eq!(
        solve(&m, &[i], Scope::DeclaredStaticImages).unwrap().status,
        ClosureStatus::Open
    );
}

#[test]
fn unsupported_effect_on_an_arm_is_not_admitted_into_join_proof() {
    for word in [0x8d080000, 0x40886000, 0x0000000c] {
        let mut i = entry_target_diamond();
        i.words[6] = word; // LW, MTC0 or SYSCALL is outside scalar transfer scope
        let m = analyze_indirect(&map(&i), &i).unwrap();
        if let Some(proof) = &site(&m).closed_proof {
            // SYSCALL terminates one CFG arm. The older single-path prover can
            // still certify the other arm's target; it cannot waive the effect.
            assert_ne!(m.evidence[proof].producer, "plaid-cross-block-join/v0");
        }
        let report = solve(&m, &[i], Scope::DeclaredStaticImages).unwrap();
        assert_eq!(report.status, ClosureStatus::Open);
        assert!(
            report
                .blockers
                .iter()
                .any(|b| b.kind == "unsupported_scope_effect")
        );
    }
}

#[test]
fn three_equal_paths_exceed_the_declared_certificate_bound() {
    let mut i = diamond(0x0040);
    i.words.resize(28, 0);
    i.words[24..28].copy_from_slice(&[0x3c088000, 0x35080040, 0x0800000a, 0x34000000]);
    let m = direct_cfg(map(&i).rom, &i, &[i.base.pc, GuestAddr(0x80000060)], 256)
        .unwrap()
        .map;
    let analyzed = analyze_indirect(&m, &i).unwrap();
    assert!(site(&analyzed).closed_proof.is_none());
}

#[test]
fn altered_path_digest_is_rejected_by_certificate_reconstruction() {
    let i = diamond(0x0040);
    let mut m = analyze_indirect(&map(&i), &i).unwrap();
    let s = site(&m).clone();
    let e = m
        .evidence
        .get_mut(s.closed_proof.as_ref().unwrap())
        .unwrap();
    let mut proof: serde_json::Value = serde_json::from_str(&e.detail).unwrap();
    proof["words_sha256"] = "0".repeat(64).into();
    e.detail = serde_json::to_string(&proof).unwrap();
    m.validate().unwrap();
    assert!(!verify_constant(&m, &i, &s));
}
