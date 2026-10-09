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

fn analyzed_count(map: &ProgramMap, i: &CodeImage) -> (usize, Vec<u32>) {
    let analyzed = analyze_indirect(map, i).unwrap();
    (
        pointer_table_evidence_count(&analyzed),
        table_targets(&analyzed),
    )
}

#[test]
fn entries_after_compare_on_fallthrough_guard_path_invalidate_table_bound() {
    let i = image();
    let outcomes: Vec<_> = [0x80000004, 0x80000008]
        .into_iter()
        .map(|pc| {
            let mut m = map(&i);
            let evidence = m.entries.values().next().unwrap().clone();
            m.entries.insert(i.address(GuestAddr(pc)), evidence);
            m.validate().unwrap();
            (pc, analyzed_count(&m, &i))
        })
        .collect();

    // Branch entry skips SLTIU and can reuse stale t1. Delay-slot entry skips
    // both compare and branch, then falls sequentially into block 0x8000000c.
    assert_eq!(
        outcomes,
        vec![(0x80000004, (0, vec![])), (0x80000008, (0, vec![]))]
    );
}

#[test]
fn direct_edges_after_compare_on_fallthrough_guard_path_invalidate_table_bound() {
    let i = image();
    let outcomes: Vec<_> = [0x80000004, 0x80000008]
        .into_iter()
        .map(|pc| {
            let mut m = map(&i);
            let mut edge = m
                .direct_edges
                .iter()
                .find(|edge| edge.site.pc == GuestAddr(0x80000060))
                .unwrap()
                .clone();
            edge.target = i.address(GuestAddr(pc));
            m.direct_edges.insert(edge);
            m.validate().unwrap();
            (pc, analyzed_count(&m, &i))
        })
        .collect();

    assert_eq!(
        outcomes,
        vec![(0x80000004, (0, vec![])), (0x80000008, (0, vec![]))]
    );
}

#[test]
fn indirect_targets_after_compare_on_fallthrough_guard_path_invalidate_table_bound() {
    let i = image();
    let mut outcomes = Vec::new();
    for observed in [false, true] {
        for pc in [0x80000004, 0x80000008] {
            let mut m = map(&i);
            add_indirect_target(&mut m, i.address(GuestAddr(pc)), observed);
            m.validate().unwrap();
            outcomes.push((observed, pc, analyzed_count(&m, &i)));
        }
    }

    assert_eq!(
        outcomes,
        vec![
            (false, 0x80000004, (0, vec![])),
            (false, 0x80000008, (0, vec![])),
            (true, 0x80000004, (0, vec![])),
            (true, 0x80000008, (0, vec![])),
        ]
    );
}

#[test]
fn compare_entry_and_other_generation_predecessors_do_not_overinvalidate() {
    let i = image();

    // The normal entry at the compare itself executes SLTIU and must remain valid.
    let baseline = analyze_indirect(&map(&i), &i).unwrap();
    assert_eq!(pointer_table_evidence_count(&baseline), 1);
    assert_eq!(table_targets(&baseline), [0x80000040, 0x80000050]);

    // Same guest PCs in another image generation are different identities.
    for pc in [0x80000004, 0x80000008] {
        let mut other_generation = map(&i);
        let evidence = other_generation.entries.values().next().unwrap().clone();
        let mut target = i.address(GuestAddr(pc));
        target.generation = 1;
        other_generation.entries.insert(target, evidence);
        other_generation.validate().unwrap();
        let analyzed = analyze_indirect(&other_generation, &i).unwrap();
        assert_eq!(pointer_table_evidence_count(&analyzed), 1);
        assert_eq!(table_targets(&analyzed), [0x80000040, 0x80000050]);
    }
}

#[test]
fn fixed_point_discovery_with_post_compare_roots_must_not_certify_table_bound() {
    let i = image();
    let outcomes: Vec<_> = [0x80000004, 0x80000008]
        .into_iter()
        .map(|pc| {
            let discovered = discover_image(rom(), &i, &[i.base.pc, GuestAddr(pc)], 1000).unwrap();
            assert!(discovered.map.entries.contains_key(&i.address(GuestAddr(pc))));
            (
                pc,
                pointer_table_evidence_count(&discovered.map),
                table_targets(&discovered.map),
            )
        })
        .collect();

    assert_eq!(
        outcomes,
        vec![(0x80000004, 0, vec![]), (0x80000008, 0, vec![])]
    );
}
