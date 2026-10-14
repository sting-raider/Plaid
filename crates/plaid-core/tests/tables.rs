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
