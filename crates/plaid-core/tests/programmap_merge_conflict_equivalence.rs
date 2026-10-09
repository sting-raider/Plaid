use plaid_core::{
    EvidenceKind, GuestAddr,
    merge::merge_maps,
    program::{
        BasicBlock, CodeAddress, DelaySlot, DirectEdge, EdgeKind, Evidence, EvidenceRefs,
        ProgramMap, RomIdentity,
    },
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn addr(pc: u32) -> CodeAddress {
    CodeAddress {
        pc: GuestAddr(pc),
        image: "semantic-matrix".into(),
        generation: 7,
    }
}

fn one_ref(id: &str) -> EvidenceRefs {
    [id.to_string()].into()
}

fn empty_with_evidence(id: &str) -> ProgramMap {
    let mut map = ProgramMap::new(rom());
    map.evidence.insert(
        id.into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "programmap-merge-scalability".into(),
            revision: "semantic-matrix".into(),
            detail: format!("independent evidence {id}"),
        },
    );
    map
}

fn block_map(id: &str, size: u32, delay_slot_entry: bool) -> ProgramMap {
    let mut map = empty_with_evidence(id);
    map.blocks.insert(BasicBlock {
        start: addr(0x8000_0000),
        size,
        delay_slot_entry,
        evidence: one_ref(id),
    });
    map.validate().unwrap();
    map
}

fn edge_map(id: &str, target: u32, delay_slot: DelaySlot) -> ProgramMap {
    let mut map = empty_with_evidence(id);
    map.direct_edges.insert(DirectEdge {
        site: addr(0x8000_0000),
        target: addr(target),
        kind: EdgeKind::Jump,
        delay_slot,
        evidence: one_ref(id),
    });
    map.validate().unwrap();
    map
}

#[test]
fn duplicate_semantics_union_provenance_without_fabricating_conflicts() {
    let a = block_map("a", 4, false);
    let b = block_map("b", 4, false);
    let merged = merge_maps(&a, &b).unwrap();
    assert_eq!(merged.blocks.len(), 1);
    let block = merged.blocks.first().unwrap();
    assert_eq!(block.evidence, ["a".to_string(), "b".to_string()].into());
    assert!(
        !merged
            .unresolved
            .iter()
            .any(|u| u.kind == "conflicting_block")
    );
}

#[test]
fn three_way_block_conflict_unions_every_participating_evidence_and_is_order_stable() {
    let a = block_map("a", 4, false);
    let b = block_map("b", 8, false);
    let c = block_map("c", 4, true);
    let abc = merge_maps(&merge_maps(&a, &b).unwrap(), &c).unwrap();
    let cba = merge_maps(&c, &merge_maps(&b, &a).unwrap()).unwrap();
    assert_eq!(abc, cba);
    let conflicts: Vec<_> = abc
        .unresolved
        .iter()
        .filter(|u| u.kind == "conflicting_block")
        .collect();
    assert_eq!(conflicts.len(), 1);
    assert_eq!(
        conflicts[0].evidence,
        ["a".to_string(), "b".to_string(), "c".to_string()].into()
    );
}

#[test]
fn three_way_direct_edge_conflict_unions_every_participating_evidence_and_is_order_stable() {
    let a = edge_map("a", 0x8000_0010, DelaySlot::Always);
    let b = edge_map("b", 0x8000_0020, DelaySlot::Always);
    let c = edge_map("c", 0x8000_0010, DelaySlot::TakenOnly);
    let abc = merge_maps(&merge_maps(&a, &b).unwrap(), &c).unwrap();
    let cba = merge_maps(&c, &merge_maps(&b, &a).unwrap()).unwrap();
    assert_eq!(abc, cba);
    let conflicts: Vec<_> = abc
        .unresolved
        .iter()
        .filter(|u| u.kind == "conflicting_direct_edge")
        .collect();
    assert_eq!(conflicts.len(), 1);
    assert_eq!(
        conflicts[0].evidence,
        ["a".to_string(), "b".to_string(), "c".to_string()].into()
    );
}

#[test]
fn different_conflict_keys_remain_independent() {
    let mut a = block_map("a", 4, false);
    let mut b = block_map("b", 8, false);
    let second = addr(0x8000_0040);
    a.blocks.insert(BasicBlock {
        start: second.clone(),
        size: 4,
        delay_slot_entry: false,
        evidence: one_ref("a"),
    });
    b.blocks.insert(BasicBlock {
        start: second.clone(),
        size: 4,
        delay_slot_entry: false,
        evidence: one_ref("b"),
    });
    let merged = merge_maps(&a, &b).unwrap();
    assert_eq!(
        merged
            .unresolved
            .iter()
            .filter(|u| u.kind == "conflicting_block")
            .count(),
        1
    );
    let second_block = merged
        .blocks
        .iter()
        .find(|block| block.start == second)
        .unwrap();
    assert_eq!(
        second_block.evidence,
        ["a".to_string(), "b".to_string()].into()
    );
}
