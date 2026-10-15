//! RSP lowering contracts (ADR-0167); semantics are checked against ares by spike097.
use plaid_lower::rsp::lower_rsp;

fn text(words: &[u32]) -> Vec<u8> {
    words.iter().flat_map(|w| w.to_be_bytes()).collect()
}

const BREAK: u32 = 13;
const JR_T0: u32 = 8 << 21 | 8;

#[test]
fn register_jumps_dispatch_only_over_the_text() {
    let c = lower_rsp(&text(&[JR_T0, 0, BREAK]), 0x80, "u").unwrap();
    for pc in [0x80, 0x84, 0x88] {
        assert!(
            c.contains(&format!("case 0x{pc:03x}: goto L_{pc:03x};")),
            "{pc:x}"
        );
    }
    assert_eq!(c.matches(": goto L_").count(), 3);
    assert!(c.contains("default: return plaid_rsp_fault(r, pc, 3);"));
    assert!(c.contains("if (t & 3) return plaid_rsp_fault(r, 0x080u, 3);"));
    // falling off the end of the text faults too
    assert!(c.contains("return plaid_rsp_fault(r, 0x08cu, 3);\n}"));
}

#[test]
fn direct_targets_outside_the_text_go_through_the_faulting_dispatch() {
    // j 0x800 from a text at 0x080..0x08c
    let c = lower_rsp(&text(&[2 << 26 | 0x800 >> 2, 0, BREAK]), 0x80, "u").unwrap();
    assert!(c.contains("{ pc = 0x800u; goto dispatch; }"));
}

#[test]
fn vector_instructions_lower_to_the_ported_unit() {
    // vxor $v1, $v1, $v1[0]: the first vector op in a real audio microcode
    let c = lower_rsp(&text(&[0x4a01_086c]), 0x80, "u").unwrap();
    assert!(c.contains("plaid_vu(r, 0x2c, 1, 1, 1, 0);"));
    // lqv $v2[0], 0x10($a0) and sqv $v2[8], -0x10($a0)
    let c = lower_rsp(&text(&[0xc882_2001, 0xe882_247f]), 0, "u").unwrap();
    assert!(c.contains("plaid_lwc2(r, 4, 2, 4, 1, 0);"));
    assert!(c.contains("plaid_swc2(r, 4, 2, 4, -1, 8);"));
    // vrcph $v3[1], $v4[2] reads e from bits 21..24 and de from vs
    let c = lower_rsp(&text(&[0x4b44_08f2]), 0, "u").unwrap();
    assert!(c.contains("plaid_vdivh(r, 3, 1, 4, 10);"));
}

#[test]
fn reserved_and_unknown_instructions_are_refused() {
    for w in [
        24,          // MULT has no RSP meaning
        0x4a01_0852, // VSUT: ares runs it as VZERO
        0x4a01_0856, // VADDB
        0x4820_0800, // COP2 rs 1 (DMFC2)
        0xc801_5000, // LWV is not on the N64 RSP
        0xc801_6000, // LWC2 opcode 12
        0xe801_6000, // SWC2 opcode 12
    ] {
        assert_eq!(
            lower_rsp(&text(&[w]), 0, "u").unwrap_err(),
            format!("000: unsupported RSP instruction {w:08x}")
        );
    }
}

#[test]
fn transfers_need_a_plain_delay_slot() {
    assert_eq!(
        lower_rsp(&text(&[JR_T0, JR_T0, 0]), 0, "u").unwrap_err(),
        "000: transfer in a delay slot"
    );
    assert_eq!(
        lower_rsp(&text(&[0, JR_T0]), 0, "u").unwrap_err(),
        "004: transfer without a delay slot in the text"
    );
}

#[test]
fn text_and_name_are_validated() {
    assert!(lower_rsp(&[0; 6], 0, "u").is_err());
    assert!(lower_rsp(&[0; 8], 0xffc, "u").is_err());
    assert!(lower_rsp(&[0; 4], 2, "u").is_err());
    assert!(lower_rsp(&[0; 4], 0, "a-b").is_err());
    assert!(lower_rsp(&[0; 4], 0, "").is_err());
}
