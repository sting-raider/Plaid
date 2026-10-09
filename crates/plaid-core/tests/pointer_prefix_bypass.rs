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

fn pointer_table_evidence_count(map: &ProgramMap) -> usize {
    map.evidence
        .values()
        .filter(|e| e.producer == "plaid-pointer-table-candidates/v0")
        .count()
}

fn add_indirect_bypass(m: &mut ProgramMap, target: CodeAddress, observed: bool) {
    let old = m.indirect_sites.first().unwrap().clone();
    let mut site = old.clone();
    let evidence = m.entries.values().next().unwrap().clone();
    m.indirect_sites.remove(&old);
    if observed {
        site.observed.insert(target, evidence);
    } else {
        site.candidates.insert(target, evidence);
    }
    m.indirect_sites.insert(site);
}

#[test]
fn every_same_generation_mid_prefix_entry_invalidates_pointer_table_evidence() {
    let i = image();
    for pc in [0x80000010, 0x80000014, 0x80000018, 0x8000001c, 0x80000020] {
        let mut m = map(&i);
        let evidence = m.entries.values().next().unwrap().clone();
        m.entries.insert(i.address(GuestAddr(pc)), evidence);
        m.validate().unwrap();

        let analyzed = analyze_indirect(&m, &i).unwrap();
        assert_eq!(
            pointer_table_evidence_count(&analyzed),
            0,
            "entry at {pc:08x} bypassed the selected guard but retained table evidence"
        );
        assert!(
            candidates(&analyzed).is_empty(),
            "entry at {pc:08x} bypassed the selected guard but received table candidates"
        );
    }
}

#[test]
fn same_generation_direct_edge_into_prefix_invalidates_pointer_table_evidence() {
    let i = image();
    let mut m = map(&i);
    let mut edge = m
        .direct_edges
        .iter()
        .find(|edge| edge.site.pc == GuestAddr(0x80000060))
        .unwrap()
        .clone();
    edge.target = i.address(GuestAddr(0x80000014));
    m.direct_edges.insert(edge);
    m.validate().unwrap();

    let analyzed = analyze_indirect(&m, &i).unwrap();
    assert_eq!(pointer_table_evidence_count(&analyzed), 0);
    assert!(candidates(&analyzed).is_empty());
}

#[test]
fn same_generation_indirect_targets_into_prefix_invalidate_pointer_table_evidence() {
    let i = image();
    for observed in [false, true] {
        let mut m = map(&i);
        add_indirect_bypass(
            &mut m,
            i.address(GuestAddr(0x80000014)),
            observed,
        );
        m.validate().unwrap();

        let analyzed = analyze_indirect(&m, &i).unwrap();
        assert_eq!(
            pointer_table_evidence_count(&analyzed),
            0,
            "{} target bypassed the guard but retained table evidence",
            if observed { "observed" } else { "candidate" }
        );
        let targets = candidates(&analyzed);
        assert!(
            !targets.iter().any(|pc| matches!(*pc, 0x80000040 | 0x80000050)),
            "{} target bypassed the guard but acquired table-derived candidates: {:?}",
            if observed { "observed" } else { "candidate" },
            targets
        );
    }
}

#[test]
fn reachability_outside_prefix_or_generation_does_not_overinvalidate() {
    let i = image();

    let mut outside = map(&i);
    let evidence = outside.entries.values().next().unwrap().clone();
    outside
        .entries
        .insert(i.address(GuestAddr(0x80000040)), evidence.clone());
    outside.validate().unwrap();
    let analyzed = analyze_indirect(&outside, &i).unwrap();
    assert_eq!(pointer_table_evidence_count(&analyzed), 1);
    assert_eq!(candidates(&analyzed), [0x80000040, 0x80000050]);

    let mut other_generation = map(&i);
    let mut target = i.address(GuestAddr(0x80000014));
    target.generation = 1;
    other_generation.entries.insert(target, evidence);
    other_generation.validate().unwrap();
    let analyzed = analyze_indirect(&other_generation, &i).unwrap();
    assert_eq!(pointer_table_evidence_count(&analyzed), 1);
    assert_eq!(candidates(&analyzed), [0x80000040, 0x80000050]);
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
    assert_eq!(pointer_table_evidence_count(&discovered.map), 0);
    assert!(
        candidates(&discovered.map).is_empty(),
        "fixed-point direct discovery should repartition the bypass as a block leader"
    );
}
