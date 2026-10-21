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
        holes: Vec::new(),
        slots: Vec::new(),
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
    assert!(c.contains("L_80000010: s->pc = 0x80000010u; return 2;"));
    // Executable bytes are registered for the runtime store guard.
    assert!(c.contains("plaid_code[] = {{0, 16, -1}, {16, 24, -1}}"));
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
fn a_residual_jump_also_dispatches_over_its_own_candidates() {
    // The same jump with its proof removed: only --residual-dispatch lowers
    // it, and its known candidate stays a label (ADR-0223).
    use plaid_lower::lower_c_with_preload;
    let words = [[0x3c08_8000, 0x3508_0010, 0x0100_0008, 0].as_slice(), &HALT].concat();
    let (mut map, image) = map_of(&words);
    let mut site = map.indirect_sites.pop_first().unwrap();
    assert!(site.closed_proof.take().is_some());
    map.indirect_sites.insert(site);
    let images = std::slice::from_ref(&image);
    let exits = [GuestAddr(0x8000_0010)];
    assert!(lower_c(&map, images, GuestAddr(BASE), &exits).is_err());
    let c = lower_c_with_preload(&map, images, &image, GuestAddr(BASE), &exits, true).unwrap();
    assert!(
        c.contains("case 0xffffffff80000010ull: goto L_80000010;"),
        "{c}"
    );
    assert!(c.contains("return plaid_fault(s, 0x80000008u, 3);"));
}

#[test]
fn open_programs_are_rejected() {
    // jr t0 with an unknown target.
    let err = lower(&[0x0100_0008, 0], 0x8000_0010).unwrap_err();
    assert!(err.contains("not CLOSED"), "{err}");
}

#[test]
fn instructions_outside_the_model_are_rejected() {
    // TLBWR needs a modeled Random timeline; never emulated.
    let words = [[0x4200_0006, 0, 0, 0].as_slice(), &HALT].concat();
    let err = lower(&words, 0x8000_0010).unwrap_err();
    assert!(err.contains("not CLOSED"), "{err}");
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
        holes: Vec::new(),
        slots: Vec::new(),
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

fn map_of(words: &[u32]) -> (ProgramMap, CodeImage) {
    let image = CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "lower".into(),
            generation: 0,
        },
        words: words.to_vec(),
        rom_offset: None,
        physical_start: None,
        holes: Vec::new(),
        slots: Vec::new(),
    };
    let rom = RomIdentity {
        sha256: "b".repeat(64),
        size: 4096,
    };
    (
        discover_image(rom, &image, &[GuestAddr(BASE)], 100)
            .unwrap()
            .map,
        image,
    )
}

// 0: jal 0x10; nop; j 0x20; nop; 0x10: addiu v0,v0,1; jr ra; nop; nop; 0x20: b .; nop
const CALL: [u32; 10] = [
    0x0c00_0004,
    0,
    0x0800_0008,
    0,
    0x2442_0001,
    0x03e0_0008,
    0,
    0,
    0x1000_ffff,
    0,
];

#[test]
fn returns_close_only_under_the_checked_call_return_assumption() {
    use plaid_core::solver::{ClosureStatus, Scope, solve};
    let (map, image) = map_of(&CALL);
    let site = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == 0x8000_0014)
        .unwrap();
    assert_eq!(
        site.candidates.keys().map(|c| c.pc.0).collect::<Vec<_>>(),
        [0x8000_0008]
    );
    for scope in [Scope::WholeRom, Scope::DeclaredStaticImages] {
        let r = solve(&map, std::slice::from_ref(&image), scope).unwrap();
        assert!(
            r.blockers
                .iter()
                .any(|b| b.kind == "unresolved_indirect_site")
        );
    }
    let r = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert_eq!(r.status, ClosureStatus::Closed);
    assert!(r.assumptions.iter().any(|a| a.contains("jr $ra returns")));
    // An edited target set no longer matches the recomputed certificate.
    let mut edited = map.clone();
    let mut s = edited.indirect_sites.pop_first().unwrap();
    assert_eq!(s.site.pc.0, 0x8000_0014);
    let refs = s.candidates.values().next().unwrap().clone();
    s.candidates
        .insert(edited.entries.keys().next().unwrap().clone(), refs);
    edited.indirect_sites.insert(s);
    let r = solve(&edited, &[image], Scope::DeclaredStaticImagesGuardedRam).unwrap();
    assert_eq!(r.status, ClosureStatus::Open);
}

#[test]
fn calls_lower_to_c_functions_with_checked_returns() {
    let (map, image) = map_of(&CALL);
    let c = lower_c(&map, &[image], GuestAddr(BASE), &[GuestAddr(0x8000_0020)]).unwrap();
    assert!(c.contains("static int F_80000010(plaid_state *s, u64 ret);"));
    assert!(c.contains(
        "{ int r = F_80000010(s, 0xffffffff80000008ull); if (r) return r; } goto L_80000008;"
    ));
    assert!(c.contains("if (t != ret) return plaid_fault(s, 0x80000014u, 5); return 0;"));
}

#[test]
fn a_host_entry_return_is_a_checked_return_to_the_host() {
    // 0: jr ra; nop  -- returns to the host's $ra (ADR-0146).
    let (map, image) = map_of(&[0x03e0_0008, 0]);
    let c = lower_c(&map, &[image], GuestAddr(BASE), &[]).unwrap();
    assert!(c.contains("if (t != ret) return plaid_fault(s, 0x80000000u, 5); return 0;"));
    assert!(c.contains("int r = F_80000000(s, host);"));
    assert!(c.contains("if (r == 0) { s->pc = (u32)host; return 0; }"));
}

#[test]
fn trapping_adds_check_overflow_and_likely_slots_run_only_when_taken() {
    // addi t1,t0,1; beql zero,zero,0x10; addiu t2,t2,1; nop; b .; nop
    let words = [[0x2109_0001, 0x5000_0002, 0x254a_0001, 0].as_slice(), &HALT].concat();
    let c = lower(&words, 0x8000_0010).unwrap();
    assert!(c.contains("return plaid_fault(s, 0x80000000u, 6);"));
    assert!(c.contains("{ int t = s->r[0] == s->r[0]; if (t) { s->r[10] = "));
}

fn runtime_map(words: &[u32], runtime: u32, callbacks: Vec<u8>) -> (ProgramMap, CodeImage) {
    use plaid_core::{EvidenceKind, pipeline::discover_image_with_runtime};
    let image = CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "lower".into(),
            generation: 0,
        },
        words: words.to_vec(),
        rom_offset: None,
        physical_start: None,
        holes: Vec::new(),
        slots: Vec::new(),
    };
    let rom = RomIdentity {
        sha256: "b".repeat(64),
        size: 4096,
    };
    let evidence = Evidence {
        kind: EvidenceKind::Signature,
        producer: "test".into(),
        revision: "0".into(),
        detail: "declared".into(),
    };
    let decl = [(GuestAddr(runtime), "sum".to_string(), callbacks)];
    assert!(
        discover_image_with_runtime(rom.clone(), &image, &[GuestAddr(BASE)], &decl, None, 100)
            .is_err()
    );
    let d = discover_image_with_runtime(
        rom,
        &image,
        &[GuestAddr(BASE)],
        &decl,
        Some(("runtime:test".into(), evidence)),
        100,
    )
    .unwrap();
    (d.map, image)
}

#[test]
fn runtime_functions_are_called_not_decoded_and_close_only_under_the_guarded_scope() {
    use plaid_core::solver::{ClosureStatus, Scope, solve};
    // 0: jal 0x10; nop; j 0x20; nop; 0x10: sync; jr ra; nop; nop; 0x20: b .; nop
    let mut words = CALL;
    words[4] = 0x0000_000f;
    let (map, image) = runtime_map(&words, 0x8000_0010, Vec::new());
    assert!(!map.blocks.iter().any(|b| b.start.pc.0 == 0x8000_0010));
    let r = solve(&map, std::slice::from_ref(&image), Scope::WholeRom).unwrap();
    assert!(
        r.blockers
            .iter()
            .any(|b| b.kind == "runtime_boundary_outside_scope")
    );
    let r = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert_eq!(r.status, ClosureStatus::Closed);
    assert!(
        r.assumptions
            .iter()
            .any(|a| a.contains("(sum) are host-provided"))
    );
    let c = lower_c(&map, &[image], GuestAddr(BASE), &[GuestAddr(0x8000_0020)]).unwrap();
    assert!(c.contains("int plaid_rt_sum(plaid_state *s);"));
    assert!(c.contains(
        "{ s->cp0_known = 0; int r = plaid_rt_sum(s); if (r) return r; } goto L_80000008;"
    ));
    assert!(!c.contains("F_80000010"));
}

#[test]
fn a_runtime_function_reached_by_a_branch_stays_open() {
    use plaid_core::solver::{ClosureStatus, Scope, solve};
    // beq zero,zero,0x10; nop; nop; nop; 0x10: b .; nop -- branches decode their target.
    let words = [[0x1000_0003, 0, 0, 0].as_slice(), &HALT].concat();
    let (map, image) = runtime_map(&words, 0x8000_0010, Vec::new());
    let r = solve(&map, &[image], Scope::DeclaredStaticImagesGuardedRam).unwrap();
    assert_eq!(r.status, ClosureStatus::Open);
    assert!(
        r.blockers
            .iter()
            .any(|b| b.kind == "runtime_function_decoded")
    );
}

// 0: lui a0,0x8000; jal 0x20; ori a0,a0,0x18 (delay slot); j 0x28; nop; nop
// 0x18: cb: jr ra; nop; 0x20: runtime spawn (sync; jr ra); 0x28: b .; nop
const SPAWN: [u32; 12] = [
    0x3c04_8000,
    0x0c00_0008,
    0x3484_0018,
    0x0800_000a,
    0,
    0,
    0x03e0_0008,
    0,
    0x0000_000f,
    0x03e0_0008,
    0x1000_ffff,
    0,
];

#[test]
fn proven_callbacks_are_discovered_and_entered_only_through_plaid_enter() {
    use plaid_core::solver::{ClosureStatus, Scope, solve};
    let (map, image) = runtime_map(&SPAWN, 0x8000_0020, vec![4]);
    assert!(map.blocks.iter().any(|b| b.start.pc.0 == 0x8000_0018));
    let r = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert_eq!(r.status, ClosureStatus::Closed, "{:?}", r.blockers);
    let c = lower_c(&map, &[image], GuestAddr(BASE), &[GuestAddr(0x8000_0028)]).unwrap();
    assert!(c.contains("case 0x80000018u: return F_80000018(s, ret);"));
    assert!(c.contains("if (t != ret) return plaid_fault(s, 0x80000018u, 5); return 0;"));
}

#[test]
fn an_unproven_callback_argument_stays_open() {
    use plaid_core::solver::{ClosureStatus, Scope, solve};
    let mut words = SPAWN;
    words[2] = 0x8c84_0100; // lw a0,0x100(a0): the code pointer comes from memory
    let (map, image) = runtime_map(&words, 0x8000_0020, vec![4]);
    let r = solve(&map, &[image], Scope::DeclaredStaticImagesGuardedRam).unwrap();
    assert_eq!(r.status, ClosureStatus::Open);
    assert!(
        r.blockers
            .iter()
            .any(|b| b.kind == "unresolved_runtime_callback")
    );
}

#[test]
fn cop1_moves_lower_with_an_explicit_fr_assumption() {
    use plaid_core::solver::{Scope, solve};
    // lui t0,0x3f80; mtc1 t0,f0; j 0x10; nop; b .; nop
    let words = [[0x3c08_3f80, 0x4488_0000, 0x0800_0004, 0].as_slice(), &HALT].concat();
    let (map, image) = map_of(&words);
    let r = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert!(r.assumptions.iter().any(|a| a.contains("Status.FR = 1")));
    let r = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert!(
        r.blockers
            .iter()
            .any(|b| b.kind == "unsupported_scope_effect")
    );
    let c = lower_c(&map, &[image], GuestAddr(BASE), &[GuestAddr(0x8000_0010)]).unwrap();
    assert!(c.contains("s->f[0] = (s->f[0] & 0xffffffff00000000ull) | (u32)s->r[8];"));
}

#[test]
fn loop_headers_and_only_loop_headers_get_safepoints() {
    // addiu t0,zero,3; loop: addiu t0,t0,-1; bne t0,zero,loop; nop; b .; nop
    let words = [[0x2408_0003, 0x2508_ffff, 0x1500_fffe, 0].as_slice(), &HALT].concat();
    let c = lower(&words, 0x8000_0010).unwrap();
    assert!(c.contains("L_80000004:\n  PLAID_SAFEPOINT(s);"), "{c}");
    assert_eq!(c.matches("  PLAID_SAFEPOINT(s);").count(), 1);
    // without PLAID_SAFEPOINTS the check compiles to nothing
    assert!(c.contains("#define PLAID_SAFEPOINT(s) ((void)0)"));
}

#[test]
fn fr0_maps_odd_transfers_to_upper_words_and_masks_sources() {
    use plaid_core::solver::{Scope, solve};
    // lui at,0x3ff0; mtc1 at,f11; add.s f4,f5,f2; lwc1 f7,0(t0); j 0x18; nop; b .; nop
    let words = [
        [
            0x3c01_3ff0,
            0x4481_5800,
            0x4602_2900,
            0xc507_0000,
            0x0800_0006,
            0,
        ]
        .as_slice(),
        &HALT,
    ]
    .concat();
    let (mut map, image) = map_of(&words);
    map.cop1_fr0 = true;
    let r = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert!(r.assumptions.iter().any(|a| a.contains("Status.FR = 0")));
    let c = lower_c(&map, &[image], GuestAddr(BASE), &[GuestAddr(0x8000_0018)]).unwrap();
    // f11 is the upper word of f10; the odd source f5 reads f4
    assert!(c.contains("s->f[10] = (s->f[10] & 0xffffffffull) | (u64)(u32)s->r[1] << 32;"));
    assert!(c.contains("plaid_arith_s(s, 0, 4, 4, 2,"));
    assert!(c.contains("s->f[6] = (s->f[6] & 0xffffffffull) | (u64)(u32)v << 32;"));
}

#[test]
fn unmodeled_cop0_register_lowers_to_an_explicit_checked_fault() {
    let words = [[0x4084_5800, 0, 0, 0].as_slice(), &HALT].concat();
    let c = lower(&words, 0x8000_0010).unwrap();
    assert!(c.contains("plaid_cp0_write(s, 11, s->r[4],"));
}
