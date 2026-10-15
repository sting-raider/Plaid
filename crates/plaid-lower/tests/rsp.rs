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
    assert_eq!(c.matches("case 0x").count(), 3);
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
fn vector_and_unknown_instructions_are_refused() {
    let vector = 0x4a01_086c; // vxor, the first vector op in a real audio microcode
    assert_eq!(
        lower_rsp(&text(&[0, vector]), 0x80, "u").unwrap_err(),
        "084: unsupported RSP instruction 4a01086c"
    );
    // MULT has no RSP meaning
    assert!(lower_rsp(&text(&[24]), 0, "u").is_err());
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
