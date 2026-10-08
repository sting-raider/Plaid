use plaid_core::{GuestAddr, discovery::*, program::*};

fn image(base: u32, words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(base),
            image: "synthetic".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
    }
}
fn discover(i: &CodeImage) -> Discovery {
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
}
fn j(target: u32) -> u32 {
    0x08000000 | ((target >> 2) & 0x03ffffff)
}

#[test]
fn branch_likely_annulment_and_negative_offsets() {
    let i = image(0x80000000, vec![0x5109ffff, 0, j(0x80000008), 0]);
    let d = discover(&i);
    assert!(d.map.unresolved.is_empty());
    assert!(d.map.direct_edges.iter().any(|e| e.site.pc.0 == 0x80000000
        && e.target.pc.0 == 0x80000000
        && e.delay_slot == DelaySlot::TakenOnly));
    assert!(
        d.map
            .direct_edges
            .iter()
            .any(|e| e.kind == EdgeKind::Fallthrough && e.delay_slot == DelaySlot::None)
    );
    assert_eq!(d.map.blocks.len(), 2);
}

#[test]
fn jal_discovers_call_and_return_continuation_without_function_claims() {
    let i = image(
        0x80000000,
        vec![0x0c000004, 0, j(0x80000008), 0, 0x03e00008, 0],
    );
    let d = discover(&i);
    assert_eq!(d.map.blocks.len(), 3);
    assert!(
        d.map
            .direct_edges
            .iter()
            .any(|e| e.kind == EdgeKind::Call && e.target.pc.0 == 0x80000010)
    );
    assert!(
        d.map
            .direct_edges
            .iter()
            .any(|e| e.kind == EdgeKind::ReturnContinuation && e.target.pc.0 == 0x80000008)
    );
    assert_eq!(d.map.indirect_sites.len(), 1);
    assert!(
        d.map
            .indirect_sites
            .iter()
            .all(|s| s.closed_proof.is_none())
    );
}

#[test]
fn newly_discovered_target_splits_linear_block() {
    let i = image(0x80000000, vec![0, 0, j(0x80000004), 0]);
    let d = discover(&i);
    assert_eq!(d.map.blocks.len(), 2);
    assert!(
        d.map
            .blocks
            .iter()
            .any(|b| b.start.pc.0 == 0x80000000 && b.size == 4)
    );
    assert!(
        d.map
            .blocks
            .iter()
            .any(|b| b.start.pc.0 == 0x80000004 && b.size == 12)
    );
}

#[test]
fn direct_entry_into_a_delay_slot_is_preserved_as_normal_execution() {
    let i = image(0x80000000, vec![0x10000000, j(0x80000004), 0]);
    let d = discover(&i);
    assert!(d.map.blocks.iter().any(|b| b.start.pc.0 == 0x80000004));
    assert!(
        d.map
            .unresolved
            .iter()
            .any(|u| u.kind == "unsupported_delay_slot")
    );
}

#[test]
fn missing_slots_external_targets_exceptions_and_budget_remain_visible() {
    assert!(
        discover(&image(0x80000000, vec![j(0x80001000)]))
            .map
            .unresolved
            .iter()
            .any(|u| u.kind == "unsupported_delay_slot")
    );
    assert!(
        discover(&image(0x80000000, vec![j(0x80001000), 0]))
            .map
            .unresolved
            .iter()
            .any(|u| u.kind == "unmapped_target")
    );
    assert!(
        discover(&image(0x80000000, vec![0x0000000c]))
            .map
            .unresolved
            .iter()
            .any(|u| u.kind == "exception_or_unsupported_instruction")
    );
    let i = image(0x80000000, vec![0, 0, 0]);
    let d = direct_cfg(
        RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        },
        &i,
        &[i.base.pc],
        1,
    )
    .unwrap();
    assert!(d.map.unresolved.iter().any(|u| u.kind == "resource_limit"));
}

#[test]
fn direct_jump_uses_pc_plus_four_region_even_at_zero_or_boundary() {
    let zero = discover(&image(0, vec![j(0), 0]));
    assert_eq!(zero.map.direct_edges.first().unwrap().target.pc.0, 0);
    let boundary = discover(&image(0x8ffffffc, vec![j(0x90000020), 0]));
    assert_eq!(
        boundary.map.direct_edges.first().unwrap().target.pc.0,
        0x90000020
    );
}

#[test]
fn cop1_branch_is_classified_by_decoder() {
    let d = discover(&image(0x80000000, vec![0x4503ffff, 0, j(0x80000008), 0]));
    assert!(
        d.map
            .direct_edges
            .iter()
            .any(|e| e.kind == EdgeKind::Branch && e.delay_slot == DelaySlot::TakenOnly)
    );
}

#[test]
fn jalr_zero_link_register_has_no_return_continuation() {
    let d = discover(&image(0x80000000, vec![0x01000009, 0]));
    assert!(d.map.direct_edges.is_empty());
    assert!(
        d.map
            .indirect_sites
            .first()
            .unwrap()
            .link_register
            .is_none()
    );
}
