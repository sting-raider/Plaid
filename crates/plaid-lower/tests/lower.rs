use plaid_core::{GuestAddr, discovery::CodeImage, pipeline::discover_image, program::*};
use plaid_lower::lower_c;

const BASE: u32 = 0x8000_0000;
const HALT: [u32; 2] = [0x1000_ffff, 0]; // b . ; nop

fn lower(words: &[u32], exit: u32) -> Result<String, String> {
    let image = CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "lower".into(),
            generation: 0,
        },
        words: words.to_vec(),
        rom_offset: None,
        physical_start: None,
    };
    let rom = RomIdentity {
        sha256: "b".repeat(64),
        size: 4096,
    };
    let d = discover_image(rom, &image, &[GuestAddr(BASE)], 100)?;
    lower_c(&d.map, &[image], GuestAddr(BASE), &[GuestAddr(exit)])
}

#[test]
fn closed_program_lowers_deterministically_with_guarded_stores() {
    // lui t0,0x8000; sw t1,0x100(t0); j 0x80000010; nop; b .; nop
    let words = [[0x3c08_8000, 0xad09_0100, 0x0800_0004, 0].as_slice(), &HALT].concat();
    let c = lower(&words, 0x8000_0010).unwrap();
    assert_eq!(c, lower(&words, 0x8000_0010).unwrap());
    assert!(c.contains("plaid_store(s, s->r[8] + (u64)(s64)256, 4, s->r[9]"));
    assert!(c.contains("goto L_80000010;"));
    assert!(c.contains("L_80000010: s->pc = 0x80000010u; return 0;"));
    // Executable bytes are registered for the runtime store guard.
    assert!(c.contains("plaid_code[] = {{0, 16}, {16, 24}}"));
}

#[test]
fn computed_jump_dispatches_only_over_its_proven_targets() {
    // lui t0,0x8000; ori t0,t0,0x10; jr t0; nop; b .; nop
    let words = [[0x3c08_8000, 0x3508_0010, 0x0100_0008, 0].as_slice(), &HALT].concat();
    let c = lower(&words, 0x8000_0010).unwrap();
    assert!(c.contains("switch (t) { case 0xffffffff80000010ull: goto L_80000010; }"));
    assert!(c.contains("return plaid_fault(s, 0x80000008u, 3);"));
}

#[test]
fn open_programs_are_rejected() {
    // jr t0 with an unknown target.
    let err = lower(&[0x0100_0008, 0], 0x8000_0010).unwrap_err();
    assert!(err.contains("not CLOSED"), "{err}");
}

#[test]
fn instructions_outside_the_lowered_subset_are_rejected() {
    // daddiu t0,t0,1 is admitted by the scope but not lowered; never emulated.
    let words = [[0x6508_0001, 0x0800_0004, 0, 0].as_slice(), &HALT].concat();
    let err = lower(&words, 0x8000_0010).unwrap_err();
    assert!(err.contains("outside the lowered subset"), "{err}");
}

#[test]
fn unlisted_entries_are_rejected() {
    let words = [[0x0800_0004, 0, 0, 0].as_slice(), &HALT].concat();
    let image = CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "lower".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
    };
    let rom = RomIdentity {
        sha256: "b".repeat(64),
        size: 4096,
    };
    let d = discover_image(rom, &image, &[GuestAddr(BASE)], 100).unwrap();
    let err = lower_c(
        &d.map,
        &[image],
        GuestAddr(BASE + 4),
        &[GuestAddr(0x8000_0010)],
    )
    .unwrap_err();
    assert!(err.contains("not a map entry"), "{err}");
}
