//! Gaps between disjoint declared loads are holes, not code (ADR-0150).
use plaid_core::{
    EvidenceKind, GuestAddr,
    declared_loads::{DeclaredLoad, LoadEncoding, LoadImage, compose},
    pipeline::discover_image,
    program::{Evidence, EvidenceRefs, GuestRange, RomIdentity, RomOffset},
    solver::{Scope, solve},
};

fn words(w: &[u32]) -> Vec<u8> {
    w.iter().flat_map(|x| x.to_be_bytes()).collect()
}

/// Base window at 0x80000000 jumps to `target`; a load places `b .; nop` at
/// 0x80000040, leaving 0x80000010..0x80000040 as a hole.
fn measure(target: u32) -> (usize, bool) {
    let mut rom = words(&[0x0800_0000 | (target >> 2 & 0x03ff_ffff), 0, 0, 0]);
    rom.extend(words(&[0x1000_ffff, 0]));
    let spec = LoadImage {
        base_offset: RomOffset(0),
        base: GuestRange {
            start: GuestAddr(0x8000_0000),
            size: 16,
        },
        loads: vec![DeclaredLoad {
            destination: GuestRange {
                start: GuestAddr(0x8000_0040),
                size: 8,
            },
            source: RomOffset(16),
            encoding: LoadEncoding::Raw,
            evidence: EvidenceRefs::from(["load".to_string()]),
            relocatable: false,
        }],
    };
    let (_, composite) = compose(&rom, &spec).unwrap();
    assert_eq!(composite.holes.len(), 1);
    let rom_id = RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    };
    let mut map = discover_image(rom_id, &composite, &[GuestAddr(0x8000_0000)], 100)
        .unwrap()
        .map;
    map.evidence.insert(
        "load".into(),
        Evidence {
            kind: EvidenceKind::Signature,
            producer: "test".into(),
            revision: "0".into(),
            detail: "declared load".into(),
        },
    );
    map.load_images.insert(composite.base.image.clone(), spec);
    let unmapped = map
        .unresolved
        .iter()
        .filter(|u| u.kind == "unmapped_target")
        .count();
    let report = solve(
        &map,
        std::slice::from_ref(&composite),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    let blocked = report
        .blockers
        .iter()
        .any(|b| b.kind == "unmapped_target" || b.kind == "unresolved_direct_target");
    (unmapped, blocked)
}

#[test]
fn a_jump_into_a_hole_is_unmapped_and_stays_open() {
    assert_eq!(measure(0x8000_0020), (1, true));
    // the same jump into the declared load decodes it
    assert_eq!(measure(0x8000_0040), (0, false));
}
