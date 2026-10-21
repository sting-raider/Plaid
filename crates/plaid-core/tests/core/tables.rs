use plaid_core::{GuestAddr, discovery::*, indirect::*, pipeline::*, program::*, solver::*};

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
            image: "table".into(),
            generation: 0,
        },
        words,
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
        holes: Vec::new(),
        slots: Vec::new(),
    }
}
fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}
fn map(i: &CodeImage) -> ProgramMap {
    direct_cfg(rom(), i, &[i.base.pc], 1000).unwrap().map
}

#[test]
fn virtual_slot_tables_discover_their_own_placed_case_blocks() {
    let mut i = image();
    let placed = 0x8001_0000;
    let linked = 0xe000_0000;
    i.base.pc = GuestAddr(placed);
    i.words[3] = 0x3c08_e000;
    i.words[64..].copy_from_slice(&[linked + 0x40, linked + 0x50, linked + 0x40]);
    i.slots = vec![(
        GuestRange {
            start: i.base.pc,
            size: i.words.len() as u32 * 4,
        },
        linked,
        0x100,
    )];
    let d = discover_image(rom(), &i, &[i.base.pc], 1000).unwrap();
    let s = d
        .map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == placed + 0x20)
        .unwrap();
    assert!(plaid_core::tables::verify(&d.map, &i, s));
    assert_eq!(
        s.candidates.keys().map(|a| a.pc.0).collect::<Vec<_>>(),
        [placed + 0x40, placed + 0x50]
    );
    for offset in [0x40, 0x50] {
        assert!(d.map.blocks.iter().any(|b| b.start.pc.0 == placed + offset));
    }
    let mut changed = i;
    changed.words[65] = linked + 0x60;
    assert!(!plaid_core::tables::verify(&d.map, &changed, s));
}

#[test]
fn guarded_pointer_table_closes_only_under_the_guarded_scope() {
    let i = image();
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = m.indirect_sites.first().unwrap();
    assert_eq!(
        s.candidates.keys().map(|a| a.pc.0).collect::<Vec<_>>(),
        [0x80000040, 0x80000050]
    );
    // The proof is a rechecked claim; only the guarded scope accepts it (ADR-0132).
    assert!(plaid_core::tables::verify(&m, &i, s));
    assert!(
        s.candidates
            .values()
            .flatten()
            .all(|id| m.evidence[id].producer == "plaid-pointer-table-candidates/v0")
    );
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "pointer_table_immutability_unproven")
    );
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "pointer_table_target_identity_unproven")
    );
    assert_eq!(m, ProgramMap::from_json(&m.to_json().unwrap()).unwrap());
    let d = discover_image(rom(), &i, &[i.base.pc], 1000).unwrap();
    assert!(d.map.blocks.iter().any(|b| b.start.pc.0 == 0x80000040));
    assert!(d.map.blocks.iter().any(|b| b.start.pc.0 == 0x80000050));
    let guarded = solve(
        &d.map,
        std::slice::from_ref(&i),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert!(
        !guarded.blockers.iter().any(|b| {
            b.kind == "unresolved_indirect_site" || b.kind.starts_with("pointer_table")
        })
    );
    assert!(
        guarded
            .assumptions
            .iter()
            .any(|a| a.contains("jump tables"))
    );
    let report = solve(&d.map, &[i], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_indirect_site")
    );
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "pointer_table_target_identity_unproven")
    );
}

#[test]
fn incomplete_or_invalid_table_snapshots_remain_explicit() {
    let mut i = image();
    i.words.pop();
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert!(m.indirect_sites.first().unwrap().candidates.is_empty());
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "pointer_table_source_missing")
    );
    let mut i = image();
    i.words[65] = 0x80000051;
    let m = analyze_indirect(&map(&i), &i).unwrap();
    assert_eq!(m.indirect_sites.first().unwrap().candidates.len(), 1);
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "invalid_pointer_table_entry")
    );
    let mut changed = image();
    changed.words[65] = 0x80000060;
    let changed = analyze_indirect(&map(&changed), &changed).unwrap();
    assert_ne!(
        m.indirect_sites.first().unwrap().candidates,
        changed.indirect_sites.first().unwrap().candidates
    );
}

#[test]
fn guard_bypasses_changed_indices_and_unbounded_counts_are_rejected() {
    let i = image();
    let mut m = map(&i);
    m.entries.insert(
        i.address(GuestAddr(0x8000000c)),
        m.entries.values().next().unwrap().clone(),
    );
    assert!(
        analyze_indirect(&m, &i)
            .unwrap()
            .indirect_sites
            .first()
            .unwrap()
            .candidates
            .is_empty()
    );
    for (index, word) in [
        (0, 0x2c890101),
        (0, 0x2c890000),
        (1, 0x15200016),
        (2, 0x24840001),
        (4, 0x24840100),
    ] {
        let mut changed = image();
        changed.words[index] = word;
        assert!(
            analyze_indirect(&map(&changed), &changed)
                .unwrap()
                .indirect_sites
                .first()
                .unwrap()
                .candidates
                .is_empty()
        );
    }
}

/// GCC's scheduled shape (ADR-0140): an unrelated instruction between the
/// bound and its branch, the table-base LUI between the scale and the add,
/// and a loop branch-likely back into the guard with the bound in its slot.
fn scheduled(patch: &[(usize, u32)]) -> CodeImage {
    let mut i = image();
    i.words.fill(0);
    i.words[..16].copy_from_slice(&[
        0x2c810003, 0x256b0001, 0x10200009, 0, 0x00045080, 0x3c018000, 0x002a0821, 0x8c2a0100,
        0x01400008, 0, 0, 0, 0x54a0fff5, 0x2c810003, 0x0800000e, 0,
    ]);
    for offset in [0x40, 0x50] {
        i.words[offset / 4] = 0x08000000 | (offset as u32 / 4);
    }
    i.words[64..].copy_from_slice(&[0x80000040, 0x80000050, 0x80000040]);
    for &(index, word) in patch {
        i.words[index] = word;
    }
    i
}

fn table_targets(i: &CodeImage) -> Option<Vec<u32>> {
    let m = analyze_indirect(&map(i), i).unwrap();
    let s = m
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x80000020)?;
    plaid_core::tables::verify(&m, i, s).then(|| s.candidates.keys().map(|a| a.pc.0).collect())
}

#[test]
fn scheduled_gcc_table_shapes_close() {
    assert_eq!(
        table_targets(&scheduled(&[])),
        Some(vec![0x80000040, 0x80000050])
    );
}

#[test]
fn a_scheduled_loop_may_retain_its_original_bound() {
    // A zero AT loops forever; only the original nonzero guard can dispatch.
    let i = scheduled(&[(13, 0)]);
    assert_eq!(table_targets(&i), Some(vec![0x80000040, 0x80000050]));
    let mut m = map(&i);
    m.entries.insert(
        i.address(GuestAddr(0x80000030)),
        m.entries.values().next().unwrap().clone(),
    );
    let m = analyze_indirect(&m, &i).unwrap();
    let site = m
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x80000020)
        .unwrap();
    assert!(!plaid_core::tables::verify(&m, &i, site));
}

#[test]
fn scheduled_shapes_that_break_the_bound_are_rejected() {
    for patch in [
        (1, 0x24840001),  // the interval rewrites the index
        (13, 0x2c810007), // the rebound slot is a different bound
        (13, 0x24840001), // the loop changes the guarded index
        (13, 0x24010001), // the loop overwrites the zero flag
        (5, 0x254a0004),  // the scaled index is rewritten before the add
    ] {
        assert_eq!(table_targets(&scheduled(&[patch])), None, "{patch:x?}");
    }
}

/// IDO's shape (ADR-0151): the bound sits in the delay slot of the previous
/// non-likely branch, whose fallthrough reaches the guard.
fn ido(likely: bool) -> CodeImage {
    let mut i = image();
    i.words.fill(0);
    let bnez = if likely { 0x5420000a } else { 0x1420000a };
    i.words[..14].copy_from_slice(&[
        0x28810010, bnez, 0x2c810003, 0x10200008, 0x00045080, 0x3c018000, 0x002a0821, 0x8c2a0100,
        0x01400008, 0, 0, 0, 0x0800000c, 0,
    ]);
    for offset in [0x40, 0x50] {
        i.words[offset / 4] = 0x08000000 | (offset as u32 / 4);
    }
    i.words[64..].copy_from_slice(&[0x80000040, 0x80000050, 0x80000040]);
    i
}

#[test]
fn ido_bound_in_a_previous_branch_slot_closes_only_when_it_always_runs() {
    assert_eq!(
        table_targets(&ido(false)),
        Some(vec![0x80000040, 0x80000050])
    );
    // a branch-likely's fallthrough skips its slot, so the bound may be stale
    assert_eq!(table_targets(&ido(true)), None);
}

/// IDO's unscheduled shape: `lw; <gap>; jr` with `gap` a load-delay `nop`.
fn delay_nop(gap: u32) -> CodeImage {
    let mut i = image();
    i.words.fill(0);
    i.words[..14].copy_from_slice(&[
        0x2c810003, 0x1020000a, 0, 0x00045080, 0x3c018000, 0x002a0821, 0x8c2a0100, gap, 0x01400008,
        0, 0, 0, 0x0800000c, 0,
    ]);
    for offset in [0x40, 0x50] {
        i.words[offset / 4] = 0x08000000 | (offset as u32 / 4);
    }
    i.words[64..].copy_from_slice(&[0x80000040, 0x80000050, 0x80000040]);
    i
}

#[test]
fn a_load_delay_nop_before_the_jump_still_closes_the_table() {
    assert_eq!(
        table_targets(&delay_nop(0)),
        Some(vec![0x80000040, 0x80000050])
    );
    // anything else between the load and the jump can change the target
    assert_eq!(table_targets(&delay_nop(0x254a0004)), None); // addiu t2, t2, 4
}

/// IDO's audio shape (ADR-0156): `sltiu` bounds the index, then a taken
/// `bnez` is the guard block's only way in. `slot` is the `bnez` delay slot
/// and `other` the word before the guard.
fn hop(slot: u32, other: u32) -> CodeImage {
    let mut i = image();
    i.words.fill(0);
    i.words[..14].copy_from_slice(&[
        0x2c810003, 0x14a00003, slot, other, 0, 0x10200006, 0x00045080, 0x3c018000, 0x002a0821,
        0x8c2a0100, 0x01400008, 0, 0x0800000c, 0,
    ]);
    for offset in [0x40, 0x50] {
        i.words[offset / 4] = 0x08000000 | (offset as u32 / 4);
    }
    i.words[64..].copy_from_slice(&[0x80000040, 0x80000050, 0x80000040]);
    i
}

fn hop_targets(i: &CodeImage) -> Option<Vec<u32>> {
    let m = analyze_indirect(&map(i), i).unwrap();
    let s = m
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x80000028)?;
    plaid_core::tables::verify(&m, i, s).then(|| s.candidates.keys().map(|a| a.pc.0).collect())
}

#[test]
fn a_bound_before_the_only_branch_to_the_guard_closes_the_table() {
    let leave = 0x10000008; // b out, skipping the guard
    assert_eq!(
        hop_targets(&hop(0, leave)),
        Some(vec![0x80000040, 0x80000050])
    );
    // the branch's slot redefines the index after the bound
    assert_eq!(hop_targets(&hop(0x24840001, leave)), None);
    // A second branch into the guard (b at 0x0c) is reached only through the
    // compare at 0x00 too, so every path bounds the index (ADR-0180)...
    assert_eq!(
        hop_targets(&hop(0, 0x10000001)),
        Some(vec![0x80000040, 0x80000050])
    );
    // ...but an entry at that branch skips the bound.
    let i = hop(0, 0x10000001);
    let mut m = map(&i);
    let evidence = m.entries.values().next().unwrap().clone();
    m.entries.insert(i.address(GuestAddr(0x8000000c)), evidence);
    let m = analyze_indirect(&m, &i).unwrap();
    let s = m
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x80000028)
        .unwrap();
    assert!(!plaid_core::tables::verify(&m, &i, s));
}

/// A separate entry reaches the guard without establishing the table base.
/// The initialized path still supplies candidates, never an exhaustive proof.
#[test]
fn incomplete_table_paths_retain_only_candidate_evidence() {
    let mut i = image();
    i.words[..10].copy_from_slice(&[
        0x3c088000, 0x25080100, // initialized path's table base
        0x2c890003, 0x1120000c, 0, // guard, default at +0x40
        0x00045080, 0x010a1021, 0x8c420000, 0x00400008, 0,
    ]);
    i.words[0x70 / 4] = 0x08000002; // independent entry -> guard
    let roots = [i.base.pc, GuestAddr(0x80000070)];
    let initial = direct_cfg(rom(), &i, &roots, 1000).unwrap().map;
    let m = analyze_indirect(&initial, &i).unwrap();
    let s = m
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x80000020)
        .unwrap();
    assert_eq!(
        s.candidates.keys().map(|a| a.pc.0).collect::<Vec<_>>(),
        [0x80000040, 0x80000050]
    );
    assert!(s.closed_proof.is_none());
    assert!(!plaid_core::tables::verify(&m, &i, s));
    let id = s.candidates.values().next().unwrap().first().unwrap();
    let detail: serde_json::Value = serde_json::from_str(&m.evidence[id].detail).unwrap();
    assert_eq!(detail["incomplete_paths"], true);
    let mut forged = s.clone();
    forged.closed_proof = Some(id.clone());
    assert!(!plaid_core::tables::verify(&m, &i, &forged));
    let d = discover_image(rom(), &i, &roots, 1000).unwrap();
    assert!(d.map.blocks.iter().any(|b| b.start.pc.0 == 0x80000050));
    let report = solve(
        &d.map,
        std::slice::from_ref(&i),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_indirect_site")
    );
    // The exact same witnesses read only their own placed overlay's table.
    let mut placed = i.clone();
    placed.base.pc = GuestAddr(0x80020000);
    placed.slots = vec![(
        GuestRange {
            start: placed.base.pc,
            size: placed.size().unwrap(),
        },
        0x80000000,
        0x100,
    )];
    let placed_roots = [placed.base.pc, GuestAddr(0x80020070)];
    let d = discover_image(rom(), &placed, &placed_roots, 1000).unwrap();
    let site = d
        .map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x80020020)
        .unwrap();
    assert_eq!(
        site.candidates.keys().map(|a| a.pc.0).collect::<Vec<_>>(),
        [0x80020040, 0x80020050]
    );
    assert!(site.closed_proof.is_none());
    assert!(!plaid_core::tables::verify(&d.map, &placed, site));
    assert!(d.map.blocks.iter().any(|b| b.start.pc.0 == 0x80020050));
    let initial = direct_cfg(rom(), &placed, &placed_roots, 1000).unwrap().map;
    placed.holes.push(GuestRange {
        start: GuestAddr(0x80020104),
        size: 4,
    });
    let missing = analyze_indirect(&initial, &placed).unwrap();
    let site = missing
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x80020020)
        .unwrap();
    assert!(site.candidates.is_empty());
    assert!(site.closed_proof.is_none());
    // Nullable call arrays are not switch tables: preserve their old behavior.
    let mut call = i.clone();
    call.words[8] = 0x0040f809; // jalr v0
    call.words[10] = 0x03e00008; // continuation returns
    call.words[64] = 0; // optional entry in an otherwise recognizable array
    let initial = direct_cfg(rom(), &call, &roots, 1000).unwrap().map;
    let m = analyze_indirect(&initial, &call).unwrap();
    let site = m
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x80000020)
        .unwrap();
    assert!(site.candidates.is_empty());
    assert!(site.closed_proof.is_none());
    // A path that never establishes a base supplies no table at all.
    i.words[0] = 0;
    let m = direct_cfg(rom(), &i, &roots, 1000).unwrap().map;
    let m = analyze_indirect(&m, &i).unwrap();
    assert!(
        m.indirect_sites
            .iter()
            .find(|s| s.site.pc.0 == 0x80000020)
            .unwrap()
            .candidates
            .is_empty()
    );
}
