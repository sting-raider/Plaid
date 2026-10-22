//! RSP lowering contracts (ADR-0167..0169); semantics are checked against
//! ares by spike097, and real tasks by spike098.
use plaid_lower::rsp::lower_rsp;

fn text(words: &[u32]) -> Vec<u8> {
    words.iter().flat_map(|w| w.to_be_bytes()).collect()
}
fn c(words: &[u32], imem: u32) -> String {
    let lowered = lower_rsp(&text(words), imem, "u").unwrap();
    assert!(lowered.stubs.is_empty(), "{:?}", lowered.stubs);
    lowered.c
}

const BREAK: u32 = 13;
const JR_T0: u32 = 8 << 21 | 8;

#[test]
fn generated_text_uses_the_runtime_state_header() {
    let c = c(&[BREAK], 0);
    assert!(c.starts_with("#include \"rsp_state.h\"\n"));
    assert!(!c.contains("typedef struct plaid_rsp {"));
}

#[test]
fn register_jumps_dispatch_only_over_the_text() {
    let c = c(&[JR_T0, 0, BREAK], 0x80);
    for pc in [0x80, 0x84, 0x88] {
        assert!(
            c.contains(&format!("case 0x{pc:03x}: goto L_{pc:03x};")),
            "{pc:x}"
        );
    }
    assert_eq!(c.matches(": goto L_").count(), 3);
    // anything else leaves the text for the host to choose another
    assert!(c.contains("default: return plaid_rsp_leave(r, pc);"));
    assert!(c.contains("if (t & 3) return plaid_rsp_fault(r, 0x080u, 3);"));
    assert!(c.contains("  return plaid_rsp_leave(r, 0x08cu);\n}"));
}

#[test]
fn every_word_runs_only_while_imem_holds_it() {
    let c = c(&[JR_T0, 0, BREAK], 0x80);
    // checked against IMEM on entry and after any DMA into IMEM
    assert!(c.contains("{\n  plaid_rsp_verify(r, plaid_rsp_bytes_u, 0x080u, 0xcu);\ndispatch:"));
    assert!(c.contains("PLAID_RSP_LIVE2(0x080u)"));
    assert!(c.contains("PLAID_RSP_LIVE(0x088u)"));
    assert!(c.contains("static const u8 plaid_rsp_bytes_u[12] = {\n  1,0,0,8,"));
    assert!(c.contains(
        "const plaid_rsp_text plaid_rsp_text_u = {0x080u, 0xcu, plaid_rsp_bytes_u, plaid_rsp_u, \"u\"};"
    ));
    let mtc0 = 16 << 26 | 4 << 21 | 8 << 16 | 2 << 11; // mtc0 $t0, SP_RD_LEN
    let c = self::c(&[mtc0], 0);
    assert!(c.contains(
        "if (r->imem_written) { r->imem_written = 0; plaid_rsp_verify(r, plaid_rsp_bytes_u, 0x000u, 0x4u); }"
    ));
}

#[test]
fn direct_targets_outside_the_text_leave_it() {
    // j 0x800 from a text at 0x080..0x08c
    let c = c(&[2 << 26 | 0x800 >> 2, 0, BREAK], 0x80);
    assert!(c.contains("{  return plaid_rsp_leave(r, 0x800u); }"));
}

#[test]
fn vector_instructions_lower_to_the_ported_unit() {
    // vxor $v1, $v1, $v1[0]: the first vector op in a real audio microcode
    assert!(c(&[0x4a01_086c], 0x80).contains("plaid_vu(r, 0x2c, 1, 1, 1, 0);"));
    // lqv $v2[0], 0x10($a0) and sqv $v2[8], -0x10($a0)
    let c2 = c(&[0xc882_2001, 0xe882_247f], 0);
    assert!(c2.contains("plaid_lwc2(r, 4, 2, 4, 1, 0);"));
    assert!(c2.contains("plaid_swc2(r, 4, 2, 4, -1, 8);"));
    // vrcph $v3[1], $v4[2] reads e from bits 21..24 and de from vs
    assert!(c(&[0x4b44_08f2], 0).contains("plaid_vdivh(r, 3, 1, 4, 10);"));
}

#[test]
fn words_that_cannot_be_lowered_become_fault_stubs() {
    for w in [
        24,          // MULT has no RSP meaning
        0x4a01_0852, // VSUT: ares runs it as VZERO
        0x4a01_0856, // VADDB
        0x4820_0800, // COP2 rs 1 (DMFC2)
        0xc801_5000, // LWV is not on the N64 RSP
        0xc801_6000, // LWC2 opcode 12
        0xe801_6000, // SWC2 opcode 12
    ] {
        let lowered = lower_rsp(&text(&[w]), 0, "u").unwrap();
        assert_eq!(
            lowered.stubs,
            [format!("000: unsupported RSP instruction {w:08x}")]
        );
        assert!(
            lowered
                .c
                .contains("L_000:\n  return plaid_rsp_fault(r, 0x000u, 6);")
        );
    }
    let lowered = lower_rsp(&text(&[JR_T0, JR_T0, 0]), 0, "u").unwrap();
    assert_eq!(lowered.stubs, ["000: transfer in a delay slot"]);
    // a final transfer leaves for a text that also holds its delay slot (ADR-0246)
    let lowered = lower_rsp(&text(&[0, JR_T0]), 0, "u").unwrap();
    assert!(lowered.stubs.is_empty());
    assert!(lowered.c.contains(
        "L_004:
  return plaid_rsp_leave(r, 0x004u);"
    ));
    // a transfer whose delay slot cannot be lowered is a stub itself
    let lowered = lower_rsp(&text(&[JR_T0, 24]), 0, "u").unwrap();
    assert_eq!(lowered.stubs.len(), 2);
    assert!(
        lowered
            .c
            .contains("L_000:\n  return plaid_rsp_fault(r, 0x000u, 6);")
    );
}

#[test]
fn text_and_name_are_validated() {
    assert!(lower_rsp(&[0; 6], 0, "u").is_err());
    assert!(lower_rsp(&[0; 8], 0xffc, "u").is_err());
    assert!(lower_rsp(&[0; 4], 2, "u").is_err());
    assert!(lower_rsp(&[], 0, "u").is_err());
    assert!(lower_rsp(&[0; 4], 0, "a-b").is_err());
    assert!(lower_rsp(&[0; 4], 0, "").is_err());
}
