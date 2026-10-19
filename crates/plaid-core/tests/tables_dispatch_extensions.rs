//! Bounded table proofs for pointer expressions scheduled across guards and
//! constant-proven variable shifts.
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
fn sllv(d: u32, t: u32, s: u32) -> u32 {
    s << 21 | t << 16 | d << 11 | 4
}
fn branch(op: u32, s: u32, t: u32, at: u32, to: u32) -> u32 {
    op << 26 | s << 21 | t << 16 | ((to.wrapping_sub(at + 4) >> 2) & 0xffff)
}
fn lui(t: u32) -> u32 {
    0x3c00_0000 | t << 16 | 0x8000
}
fn addu(d: u32, s: u32, t: u32) -> u32 {
    s << 21 | t << 16 | d << 11 | 0x21
}
fn lw(t: u32, base: u32, offset: u32) -> u32 {
    0x8c00_0000 | base << 21 | t << 16 | offset
}
fn addiu(t: u32, s: u32, imm: u32) -> u32 {
    0x2400_0000 | s << 21 | t << 16 | imm
}
fn jr(s: u32) -> u32 {
    s << 21 | 8
}

fn image(code: &[u32]) -> CodeImage {
    let mut words = vec![0; 0x110 / 4];
    words[..code.len()].copy_from_slice(code);
    for at in [EXIT, 0x50, 0x60] {
        words[at as usize / 4] = jr(31);
    }
    words[TABLE as usize / 4..].copy_from_slice(&[0x80000050, 0x80000060, 0x80000050, 0]);
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "table-dispatch-extensions".into(),
            generation: 7,
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
        sha256: "d".repeat(64),
        size: 4096,
    }
}

fn analyzed(code: &[u32]) -> (CodeImage, ProgramMap) {
    let image = image(code);
    let roots = [image.base.pc];
    let map = direct_cfg(rom(), &image, &roots, 1000).unwrap().map;
    let map = analyze_indirect(&map, &image).unwrap();
    (image, map)
}

fn targets(code: &[u32], site: u32) -> Option<Vec<u32>> {
    let (image, map) = analyzed(code);
    let site = map
        .indirect_sites
        .iter()
        .find(|candidate| candidate.site.pc.0 == 0x80000000 + site)?;
    plaid_core::tables::verify(&map, &image, site).then(|| {
        site.candidates
            .keys()
            .map(|target| target.pc.0 - 0x80000000)
            .collect()
    })
}

/// The table address is formed before the guard; the load itself follows the
/// guard's always-executed delay slot.
fn precomputed_address() -> Vec<u32> {
    vec![
        sltiu(T8, A0, 3),
        sll(T9, A0),
        lui(AT),
        addu(V0, AT, T9),
        branch(4, T8, 0, 0x10, EXIT),
        0,
        lw(T9, V0, TABLE),
        jr(T9),
        0,
    ]
}

#[test]
fn a_precomputed_table_pointer_survives_a_current_index_guard() {
    assert_eq!(
        targets(&precomputed_address(), 0x1c),
        Some(vec![0x50, 0x60])
    );

    let mut wrong_index = precomputed_address();
    wrong_index[0] = sltiu(T8, V1, 3);
    assert_eq!(targets(&wrong_index, 0x1c), None);

    let mut stale_flag = precomputed_address();
    stale_flag[0] = sltiu(V1, A0, 3);
    stale_flag[4] = branch(4, T8, 0, 0x10, EXIT);
    assert_eq!(targets(&stale_flag, 0x1c), None);
}

#[test]
fn the_nearest_load_must_define_the_jr_register() {
    let mut code = precomputed_address();
    code.insert(7, addiu(V0, V0, 1)); // unrelated work between lw and jr
    assert_eq!(targets(&code, 0x20), Some(vec![0x50, 0x60]));

    code[7] = addiu(T9, T9, 0);
    assert_eq!(targets(&code, 0x20), None);
}

fn variable_shift(amount: u32) -> Vec<u32> {
    vec![
        addiu(T3, 0, amount),
        sltiu(T8, A0, 3),
        sllv(T9, A0, T3),
        lui(AT),
        addu(V0, AT, T9),
        branch(4, T8, 0, 0x14, EXIT),
        0,
        lw(T9, V0, TABLE),
        jr(T9),
        0,
    ]
}

#[test]
fn sllv_is_accepted_only_when_its_effective_amount_is_proven_two() {
    assert_eq!(targets(&variable_shift(2), 0x20), Some(vec![0x50, 0x60]));
    assert_eq!(targets(&variable_shift(3), 0x20), None);

    let mut changed_before_shift = variable_shift(2);
    changed_before_shift.insert(1, addiu(T3, T3, 1));
    assert_eq!(targets(&changed_before_shift, 0x24), None);
}

#[test]
fn sllv_amount_constants_follow_delay_slot_execution() {
    let non_likely = [
        sltiu(T8, A0, 3),
        branch(4, V0, V1, 0x04, EXIT),
        addiu(T3, 0, 2), // always executes
        sllv(T9, A0, T3),
        lui(AT),
        addu(V0, AT, T9),
        branch(4, T8, 0, 0x18, EXIT),
        0,
        lw(T9, V0, TABLE),
        jr(T9),
        0,
    ];
    assert_eq!(targets(&non_likely, 0x24), Some(vec![0x50, 0x60]));

    let likely = [
        sltiu(T8, A0, 3),
        branch(21, V0, V1, 0x04, EXIT), // bnel: fallthrough annuls its slot
        addiu(T3, 0, 2),
        sllv(T9, A0, T3),
        lui(AT),
        addu(V0, AT, T9),
        branch(4, T8, 0, 0x18, EXIT),
        0,
        lw(T9, V0, TABLE),
        jr(T9),
        0,
    ];
    assert_eq!(targets(&likely, 0x24), None);
}

#[test]
fn loops_recheck_the_index_and_reject_changed_values() {
    let code = [
        sltiu(T8, A0, 3),
        branch(4, T8, 0, 0x04, EXIT),
        0,
        branch(5, V1, 0, 0x0c, 0x00), // loop re-enters and rechecks
        0,
        sll(T9, A0),
        lui(AT),
        addu(V0, AT, T9),
        branch(4, T8, 0, 0x20, EXIT),
        0,
        lw(T9, V0, TABLE),
        jr(T9),
        0,
    ];
    assert_eq!(targets(&code, 0x2c), Some(vec![0x50, 0x60]));

    let stale = [
        sltiu(T8, A0, 3),
        branch(4, T8, 0, 0x04, EXIT),
        0,
        branch(5, V1, 0, 0x0c, 0x14),
        addiu(A0, A0, 1), // compared value no longer matches the shifted index
        sll(T9, A0),
        lui(AT),
        addu(V0, AT, T9),
        branch(4, T8, 0, 0x20, EXIT),
        0,
        lw(T9, V0, TABLE),
        jr(T9),
        0,
    ];
    assert_eq!(targets(&stale, 0x2c), None);
}

#[test]
fn a_guard_after_the_pointer_must_check_the_same_index_value() {
    let code = [
        sll(T9, A0),
        lui(AT),
        addu(V0, AT, T9),
        addiu(A0, 0, 0), // bounds a new value, not the pointer's index
        sltiu(T8, A0, 3),
        branch(4, T8, 0, 0x14, EXIT),
        0,
        lw(T9, V0, TABLE),
        jr(T9),
        0,
    ];
    assert_eq!(targets(&code, 0x20), None);
}

#[test]
fn shift_constant_dependencies_cannot_skip_the_current_table_base_definition() {
    let code = [
        lui(AT),     // old value happens to point at the supplied snapshot
        0x3c01_0001, // the actual base is 0x10000, not 0x80000000
        addiu(T3, AT, 0x8001),
        addiu(T3, T3, 0x8001), // 0x10000 - 32767 - 32767 == 2
        sltiu(T8, A0, 3),
        sllv(T9, A0, T3),
        addu(V0, AT, T9),
        branch(4, T8, 0, 0x1c, EXIT),
        0,
        lw(T9, V0, TABLE),
        jr(T9),
        0,
    ];
    assert_eq!(targets(&code, 0x28), None);
}

#[test]
fn the_guard_delay_slot_cannot_change_the_index_before_scaling() {
    let code = [
        sltiu(T8, A0, 3),
        branch(4, T8, 0, 0x04, EXIT),
        addiu(A0, A0, 1),
        sll(T9, A0),
        lui(AT),
        addu(V0, AT, T9),
        lw(T9, V0, TABLE),
        jr(T9),
        0,
    ];
    assert_eq!(targets(&code, 0x1c), None);
}

#[test]
fn verification_recomputes_source_generation_and_dispatch_bytes() {
    let (image, map) = analyzed(&precomputed_address());
    let site = map
        .indirect_sites
        .iter()
        .find(|candidate| candidate.site.pc.0 == 0x8000001c)
        .unwrap();
    assert!(plaid_core::tables::verify(&map, &image, site));

    let mut changed_image = image.clone();
    changed_image.words[0] = sltiu(T8, V1, 3);
    assert!(!plaid_core::tables::verify(&map, &changed_image, site));

    let mut changed_generation = image;
    changed_generation.base.generation += 1;
    assert!(!plaid_core::tables::verify(&map, &changed_generation, site));
}
