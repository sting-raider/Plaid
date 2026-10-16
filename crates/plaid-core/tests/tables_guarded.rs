//! Jump tables proven over every CFG path into the dispatch (ADR-0180): the
//! GCC schedules ADR-0140's shape does not accept, and paths that must fail.
use plaid_core::{GuestAddr, discovery::*, indirect::*, program::*};

const AT: u32 = 1;
const V0: u32 = 2;
const V1: u32 = 3;
const A0: u32 = 4;
const T3: u32 = 11;
const T8: u32 = 24;
const T9: u32 = 25;
const EXIT: u32 = 0x40;
const TABLE: u32 = 0x100;

fn sltiu(t: u32, s: u32, imm: u32) -> u32 {
    0x2c00_0000 | s << 21 | t << 16 | imm
}
fn sll(d: u32, t: u32) -> u32 {
    t << 16 | d << 11 | 2 << 6
}
/// A branch at `at` to `to` with primary opcode `op`.
fn branch(op: u32, s: u32, t: u32, at: u32, to: u32) -> u32 {
    op << 26 | s << 21 | t << 16 | ((to.wrapping_sub(at + 4) >> 2) & 0xffff)
}
fn lui(t: u32) -> u32 {
    0x3c00_0000 | t << 16 | 0x8000
}
fn addu(d: u32, s: u32, t: u32) -> u32 {
    s << 21 | t << 16 | d << 11 | 0x21
}
fn lw(t: u32, base: u32) -> u32 {
    0x8c00_0000 | base << 21 | t << 16 | TABLE
}
fn jr(s: u32) -> u32 {
    s << 21 | 8
}
fn addiu(t: u32, s: u32, imm: u32) -> u32 {
    0x2400_0000 | s << 21 | t << 16 | imm
}

/// `code` at 0x80000000, `jr ra` at the exit and both case targets, and a
/// three-entry table naming 0x50 and 0x60.
fn image(code: &[u32]) -> CodeImage {
    let mut words = vec![0; 0x110 / 4];
    words[..code.len()].copy_from_slice(code);
    for at in [EXIT, 0x50, 0x60] {
        words[at as usize / 4] = 0x03e0_0008;
    }
    words[TABLE as usize / 4..].copy_from_slice(&[0x80000050, 0x80000060, 0x80000050, 0]);
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "guarded".into(),
            generation: 0,
        },
        words,
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
        holes: Vec::new(),
    }
}

/// The table targets the proof gives the `jr` at `site`, if any.
fn targets(code: &[u32], entries: &[u32], site: u32) -> Option<Vec<u32>> {
    let i = image(code);
    let roots: Vec<_> = entries.iter().map(|e| GuestAddr(0x80000000 + e)).collect();
    let rom = RomIdentity {
        sha256: "e".repeat(64),
        size: 4096,
    };
    let m = analyze_indirect(&direct_cfg(rom, &i, &roots, 1000).unwrap().map, &i).unwrap();
    let s = m
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x80000000 + site)
        .unwrap();
    let proof = m.evidence.get(s.closed_proof.as_ref()?)?;
    assert!(proof.detail.contains("ADR-0180"), "{}", proof.detail);
    assert!(plaid_core::tables::verify(&m, &i, s));
    Some(s.candidates.keys().map(|a| a.pc.0 - 0x80000000).collect())
}

/// The scale sits between the compare and the guard branch.
fn scale_before_branch() -> Vec<u32> {
    vec![
        sltiu(AT, A0, 3),
        sll(T9, A0),
        branch(4, AT, 0, 0x08, EXIT), // beq at, zero: out of range leaves
        0,
        lui(AT),
        addu(AT, AT, T9),
        lw(T9, AT),
        jr(T9),
        0,
    ]
}

#[test]
fn scale_between_compare_and_guard() {
    assert_eq!(
        targets(&scale_before_branch(), &[0], 0x1c),
        Some(vec![0x50, 0x60])
    );
}

#[test]
fn branch_likely_inside_the_guard_interval_and_base_in_the_guard_slot() {
    let code = [
        sltiu(AT, A0, 3),
        sll(T3, A0),
        branch(23, V1, 0, 0x08, EXIT), // bgtzl v1: leaves; its slot runs only then
        addiu(V0, 0, 1),
        branch(4, AT, 0, 0x10, EXIT),
        lui(AT), // the guard's delay slot
        addu(AT, AT, T3),
        lw(T3, AT),
        jr(T3),
        0,
    ];
    assert_eq!(targets(&code, &[0], 0x20), Some(vec![0x50, 0x60]));
}

#[test]
fn scale_in_an_earlier_slot_and_bound_reached_through_a_likely_branch() {
    let code = [
        branch(4, A0, V1, 0x00, EXIT), // beq a0, v1
        sll(T8, A0),                   // its slot runs on both paths
        branch(21, V0, 0, 0x08, 0x18), // bnel v0, zero, guard
        sltiu(AT, A0, 3),
        0x0800_0000 | (0x80000040 >> 2 & 0x03ff_ffff), // j exit
        0,
        sltiu(AT, A0, 3), // guard block, entered only by the bnel
        branch(4, AT, 0, 0x1c, EXIT),
        lui(AT),
        addu(AT, AT, T8),
        lw(T8, AT),
        jr(T8),
        0,
    ];
    assert_eq!(targets(&code, &[0], 0x2c), Some(vec![0x50, 0x60]));
}

#[test]
fn a_guard_that_dispatches_out_of_range_fails_closed() {
    let mut code = scale_before_branch();
    code[2] = branch(5, AT, 0, 0x08, EXIT); // bne: the fallthrough has at == 0
    assert_eq!(targets(&code, &[0], 0x1c), None);
}

#[test]
fn an_index_changed_between_compare_and_scale_fails_closed() {
    let mut code = scale_before_branch();
    code.insert(1, addiu(A0, A0, 1));
    code[3] = branch(4, AT, 0, 0x0c, EXIT);
    assert_eq!(targets(&code, &[0], 0x20), None);
}

#[test]
fn an_entry_that_skips_the_compare_fails_closed() {
    assert_eq!(targets(&scale_before_branch(), &[0, 4], 0x1c), None);
}

#[test]
fn an_entry_at_the_dispatch_fails_closed() {
    assert_eq!(targets(&scale_before_branch(), &[0, 0x10], 0x1c), None);
}
