use plaid_core::{GuestAddr, discovery::*, indirect::*, pipeline::*, program::*};

fn image() -> CodeImage {
    let mut words = vec![0; 67];
    words[..10].copy_from_slice(&[
        0x2c890003, // sltiu t1,a0,3
        0x11200016, // beq t1,zero,exit; selected table path is fallthrough
        0,          // branch delay slot
        0x3c088000, // dispatch block starts here
        0x25080100,
        0x00045080,
        0x010a4021,
        0x8d080000,
        0x01000008,
        0,
    ]);
    for offset in [0x40, 0x50, 0x60] {
        words[offset / 4] = 0x08000000 | (offset as u32 / 4);
    }
    words[64..].copy_from_slice(&[0x80000040, 0x80000050, 0x80000040]);
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "guard-predecessor-bypass".into(),
            generation: 0,
        },
        words,
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
    }
}

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "c".repeat(64),
        size: 4096,
    }
}

fn map(i: &CodeImage) -> ProgramMap {
    direct_cfg(rom(), i, &[i.base.pc], 1000).unwrap().map
}

fn pointer_table_evidence_count(map: &ProgramMap) -> usize {
    map.evidence
        .values()
        .filter(|e| e.producer == "plaid-pointer-table-candidates/v0")
        .count()
}

fn table_targets(map: &ProgramMap) -> Vec<u32> {
    map.indirect_sites
        .iter()
        .find(|site| site.site.pc == GuestAddr(0x80000020))
        .unwrap()
        .candidates
        .iter()
        .filter(|(_, refs)| {
            refs.iter().any(|id| {
                map.evidence
                    .get(id)
                    .is_some_and(|e| e.producer == "plaid-pointer-table-candidates/v0")
            })
        })
        .map(|(address, _)| address.pc.0)
        .collect()
}

fn add_indirect_target(map: &mut ProgramMap, target: CodeAddress, observed: bool) {
    let old = map.indirect_sites.first().unwrap().clone();
    let mut site = old.clone();
    let evidence = map.entries.values().next().unwrap().clone();
    map.indirect_sites.remove(&old);
    if observed {
        site.observed.insert(target, evidence);
    } else {
        site.candidates.insert(target, evidence);
    }
    map.indirect_sites.insert(site);
}

fn assert_no_table_evidence(map: &ProgramMap, context: &str) {
    let analyzed = analyze_indirect(map, &image()).unwrap();
    assert_eq!(
        pointer_table_evidence_count(&analyzed),
        0,
        "{context} bypassed the SLTIU guard but retained table evidence"
    );
    assert!(
        table_targets(&analyzed).is_empty(),
        "{context} bypassed the SLTIU guard but received table-derived targets: {:?}",
        table_targets(&analyzed)
    );
}

#[test]
fn entry_at_guard_branch_invalidates_pointer_table_guard_evidence() {
    let i = image();
    let mut m = map(&i);
    let evidence = m.entries.values().next().unwrap().clone();
    m.entries
        .insert(i.address(GuestAddr(0x80000004)), evidence);
    m.validate().unwrap();

    // Entering at BEQ skips SLTIU. A stale nonzero t1 falls through into the
    // dispatch even when a0 is outside the recognized [0,3) table bound.
    assert_no_table_evidence(&m, "entry at guard branch");
}

#[test]
fn direct_edge_to_guard_branch_invalidates_pointer_table_guard_evidence() {
    let i = image();
    let mut m = map(&i);
    let mut edge = m
        .direct_edges
        .iter()
        .find(|edge| edge.site.pc == GuestAddr(0x80000060))
        .unwrap()
        .clone();
    edge.target = i.address(GuestAddr(0x80000004));
    m.direct_edges.insert(edge);
    m.validate().unwrap();

    assert_no_table_evidence(&m, "direct edge to guard branch");
}

#[test]
fn indirect_target_to_guard_branch_invalidates_pointer_table_guard_evidence() {
    let i = image();
    for observed in [false, true] {
        let mut m = map(&i);
        add_indirect_target(&mut m, i.address(GuestAddr(0x80000004)), observed);
        m.validate().unwrap();
        assert_no_table_evidence(
            &m,
            if observed {
                "observed indirect target at guard branch"
            } else {
                "candidate indirect target at guard branch"
            },
        );
    }
}

#[test]
fn compare_entry_and_other_generation_branch_do_not_overinvalidate() {
    let i = image();

    // The normal entry at the compare itself executes SLTIU and must remain valid.
    let baseline = analyze_indirect(&map(&i), &i).unwrap();
    assert_eq!(pointer_table_evidence_count(&baseline), 1);
    assert_eq!(table_targets(&baseline), [0x80000040, 0x80000050]);

    // Same guest PC in another image generation is a different executable identity.
    let mut other_generation = map(&i);
    let evidence = other_generation.entries.values().next().unwrap().clone();
    let mut branch = i.address(GuestAddr(0x80000004));
    branch.generation = 1;
    other_generation.entries.insert(branch, evidence);
    other_generation.validate().unwrap();
    let analyzed = analyze_indirect(&other_generation, &i).unwrap();
    assert_eq!(pointer_table_evidence_count(&analyzed), 1);
    assert_eq!(table_targets(&analyzed), [0x80000040, 0x80000050]);
}

#[test]
fn fixed_point_discovery_with_guard_branch_root_must_not_certify_the_table_bound() {
    let i = image();
    let discovered = discover_image(
        rom(),
        &i,
        &[i.base.pc, GuestAddr(0x80000004)],
        1000,
    )
    .unwrap();

    assert!(discovered.map.entries.contains_key(&i.address(GuestAddr(0x80000004))));
    assert_eq!(
        pointer_table_evidence_count(&discovered.map),
        0,
        "fixed-point discovery preserved a table bound even though guard-branch entry skips SLTIU"
    );
    assert!(table_targets(&discovered.map).is_empty());
}
