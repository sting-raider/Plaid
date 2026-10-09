use plaid_core::{GuestAddr, discovery::*, indirect::*, pipeline::*, program::*};

fn image(branch: u32, delay_slot: u32) -> CodeImage {
    let mut words = vec![0; 67];
    words[..10].copy_from_slice(&[
        0x2c890003, // sltiu $t1, $a0, 3
        branch,
        delay_slot,
        0x3c088000, // lui   $t0, 0x8000
        0x25080100, // addiu $t0, $t0, 0x100
        0x00045080, // sll   $t2, $a0, 2
        0x010a4021, // addu  $t0, $t0, $t2
        0x8d080000, // lw    $t0, 0($t0)
        0x01000008, // jr    $t0
        0,
    ]);
    for offset in [0x40, 0x50, 0x60] {
        words[offset / 4] = 0x08000000 | (offset as u32 / 4);
    }
    words[64..].copy_from_slice(&[0x80000040, 0x80000050, 0x80000040]);
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "guard-delay".into(),
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

fn direct(i: &CodeImage) -> ProgramMap {
    direct_cfg(rom(), i, &[i.base.pc], 1000).unwrap().map
}

fn candidate_pcs(map: &ProgramMap) -> Vec<u32> {
    map.indirect_sites
        .first()
        .unwrap()
        .candidates
        .keys()
        .map(|address| address.pc.0)
        .collect()
}

fn has_guard_delay_blocker(map: &ProgramMap) -> bool {
    map.unresolved.iter().any(|u| {
        u.kind == "unsupported_delay_slot"
            && u.site.as_ref().is_some_and(|site| site.pc.0 == 0x80000004)
    })
}

#[test]
fn exceptional_executed_guard_delay_slots_reject_table_candidates() {
    // Plain BEQ selects the fallthrough dispatch when SLTIU produced nonzero.
    // Its delay slot executes regardless of branch direction, so any instruction
    // that can synchronously terminate that path must prevent table recognition.
    const BEQ_T1_ZERO: u32 = 0x11200016;
    let exceptional = [
        ("teq", 0x00000034),
        ("syscall", 0x0000000c),
        ("break", 0x0000000d),
        ("eret", 0x42000018),
    ];

    for (name, slot) in exceptional {
        let i = image(BEQ_T1_ZERO, slot);
        let cfg = direct(&i);
        assert!(has_guard_delay_blocker(&cfg), "{name}: CFG must flag exceptional slot");

        let analyzed = analyze_indirect(&cfg, &i).unwrap();
        assert!(
            candidate_pcs(&analyzed).is_empty(),
            "{name}: unreachable dispatch must not gain pointer-table candidates"
        );
        eprintln!("EXECUTED_REJECT name={name} slot={slot:08x}");
    }
}

#[test]
fn ordinary_nontrapping_guard_delay_slot_remains_recognizable() {
    const BEQ_T1_ZERO: u32 = 0x11200016;
    // addu $t2, $t2, $zero: valid, non-control, non-trapping, does not modify index $a0.
    let i = image(BEQ_T1_ZERO, 0x01405021);
    let cfg = direct(&i);
    assert!(!has_guard_delay_blocker(&cfg));
    let analyzed = analyze_indirect(&cfg, &i).unwrap();
    assert_eq!(candidate_pcs(&analyzed), [0x80000040, 0x80000050]);
}

#[test]
fn branch_likely_annulled_fallthrough_may_ignore_exceptional_physical_slot() {
    // BEQL $t1,$zero selects the same fallthrough dispatch when the guard succeeds,
    // but the delay slot is annulled on this not-taken path. The selected edge therefore
    // carries DelaySlot::None even though the other branch path's slot is exceptional.
    const BEQL_T1_ZERO: u32 = 0x51200016;
    let i = image(BEQL_T1_ZERO, 0x00000034); // teq $zero,$zero
    let cfg = direct(&i);
    let selected = cfg
        .direct_edges
        .iter()
        .find(|e| e.site.pc.0 == 0x80000004 && e.kind == EdgeKind::Fallthrough)
        .unwrap();
    assert_eq!(selected.delay_slot, DelaySlot::None);

    let analyzed = analyze_indirect(&cfg, &i).unwrap();
    assert_eq!(candidate_pcs(&analyzed), [0x80000040, 0x80000050]);
    eprintln!("ANNULLED_ACCEPT slot=00000034 candidates=2");
}
