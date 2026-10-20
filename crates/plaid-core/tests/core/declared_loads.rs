use plaid_core::{
    EvidenceKind, GuestAddr,
    declared_loads::{DeclaredLoad, LoadEncoding, LoadImage, compose},
    pipeline::discover_image,
    program::{Evidence, GuestRange, RomIdentity, RomOffset},
    solver::{ClosureStatus, Scope, solve},
};

fn bytes(words: &[u32]) -> Vec<u8> {
    words.iter().flat_map(|w| w.to_be_bytes()).collect()
}

/// Discover the composite of `rom` (base: its first `base_words` words at
/// 0x80000000) with one raw load, and record the declaration in the map.
fn solve_with_load(
    rom: &[u8],
    base_words: u32,
    at: u32,
    source: u64,
    size: u32,
    scope: Scope,
) -> plaid_core::solver::SolveReport {
    let spec = LoadImage {
        base_offset: RomOffset(0),
        base: GuestRange {
            start: GuestAddr(0x8000_0000),
            size: base_words * 4,
        },
        loads: vec![DeclaredLoad {
            destination: GuestRange {
                start: GuestAddr(at),
                size,
            },
            source: RomOffset(source),
            encoding: LoadEncoding::Raw,
            evidence: ["loads:test".into()].into(),
            relocatable: false,
            linked: None,
        }],
    };
    let (_, composite) = compose(rom, &spec).unwrap();
    let identity = RomIdentity {
        sha256: "c".repeat(64),
        size: 64,
    };
    let mut map = discover_image(identity, &composite, &[GuestAddr(0x8000_0000)], 100)
        .unwrap()
        .map;
    map.evidence.insert(
        "loads:test".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "plaid-load-declaration/v0".into(),
            revision: "0".into(),
            detail: "test declaration".into(),
        },
    );
    map.load_images.insert(composite.base.image.clone(), spec);
    solve(&map, &[composite], scope).unwrap()
}

#[test]
fn declared_load_closes_only_under_the_guarded_scope() {
    // base: j 0x80000010; nop; (two stale words); load at 0x80000010: b .; nop
    let rom = bytes(&[0x0800_0004, 0, 0xdead_beef, 0xdead_beef, 0x1000_ffff, 0]);
    let guarded = solve_with_load(
        &rom,
        4,
        0x8000_0010,
        16,
        8,
        Scope::DeclaredStaticImagesGuardedRam,
    );
    assert_eq!(
        guarded.status,
        ClosureStatus::Closed,
        "{:?}",
        guarded.blockers
    );
    assert!(
        guarded
            .assumptions
            .iter()
            .any(|a| a.contains("1 declared load(s)"))
    );
    let plain = solve_with_load(&rom, 4, 0x8000_0010, 16, 8, Scope::DeclaredStaticImages);
    assert!(
        plain.blockers.iter().any(
            |b| b.kind == "dynamic_effect_outside_scope" && b.detail.contains("declared loads")
        )
    );
}

#[test]
fn block_that_straddles_a_load_boundary_is_blocked() {
    // nop; nop; nop; b .; nop with a load replacing words 1..3 by nops
    let rom = bytes(&[0, 0, 0, 0x1000_ffff, 0, 0, 0]);
    let report = solve_with_load(
        &rom,
        5,
        0x8000_0004,
        20,
        8,
        Scope::DeclaredStaticImagesGuardedRam,
    );
    assert_ne!(report.status, ClosureStatus::Closed);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "block_straddles_declared_load")
    );
}
