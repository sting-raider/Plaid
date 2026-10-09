use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    program::{CodeAddress, GuestRange, RomOffset},
    rom::{CanonicalRom, sha256},
    solver::{ClosureStatus, Scope, solve, solve_with_rom},
};

fn canonical_rom(code: [u32; 2], decoy: Option<[u32; 2]>) -> CanonicalRom {
    let mut bytes = vec![0u8; if decoy.is_some() { 80 } else { 72 }];
    bytes[..4].copy_from_slice(&0x8037_1240u32.to_be_bytes());
    bytes[64..68].copy_from_slice(&code[0].to_be_bytes());
    bytes[68..72].copy_from_slice(&code[1].to_be_bytes());
    if let Some(decoy) = decoy {
        bytes[72..76].copy_from_slice(&decoy[0].to_be_bytes());
        bytes[76..80].copy_from_slice(&decoy[1].to_be_bytes());
    }
    CanonicalRom::from_bytes(&bytes).unwrap()
}

fn supplied_image(words: [u32; 2], rom_offset: Option<RomOffset>) -> CodeImage {
    let bytes: Vec<_> = words.into_iter().flat_map(u32::to_be_bytes).collect();
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: sha256(&bytes),
            generation: 0,
        },
        words: words.to_vec(),
        rom_offset,
        physical_start: None,
    }
}

fn map_for(rom: &CanonicalRom, image: &CodeImage) -> plaid_core::program::ProgramMap {
    direct_cfg(rom.identity.clone(), image, &[GuestAddr(0x8000_0000)], 32)
        .unwrap()
        .map
}

#[test]
fn explicit_rom_source_without_canonical_byte_witness_cannot_close() {
    // The canonical ROM says the source bytes are two NOPs. The supplied image
    // instead contains an immutable self-loop, but authenticates *its own* bytes
    // and claims the exact same ROM offset as the Region derived below.
    let rom = canonical_rom([0, 0], None);
    let image = supplied_image([0x0800_0000, 0], Some(RomOffset(64)));
    assert_ne!(&rom.bytes()[64..72], &[0x08, 0, 0, 0, 0, 0, 0, 0]);

    let map = map_for(&rom, &image);
    map.validate().unwrap();

    let report = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "canonical_rom_source_unverified")
    );
}

#[test]
fn mismatching_canonical_rom_witness_stays_open() {
    let rom = canonical_rom([0, 0], None);
    let image = supplied_image([0x0800_0000, 0], Some(RomOffset(64)));
    let map = map_for(&rom, &image);

    let report = solve_with_rom(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
        &rom,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "canonical_rom_source_mismatch")
    );
}

#[test]
fn equal_payload_at_another_rom_offset_does_not_reconcile_provenance() {
    let rom = canonical_rom([0, 0], Some([0x0800_0000, 0]));
    let image = supplied_image([0x0800_0000, 0], Some(RomOffset(64)));
    assert_eq!(&rom.bytes()[72..80], &[0x08, 0, 0, 0, 0, 0, 0, 0]);
    let map = map_for(&rom, &image);

    let report = solve_with_rom(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
        &rom,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "canonical_rom_source_mismatch")
    );
}

#[test]
fn matching_canonical_rom_witness_can_discharge_explicit_source() {
    let rom = canonical_rom([0x0800_0000, 0], None);
    let image = CodeImage::from_rom(
        &rom,
        RomOffset(64),
        GuestRange {
            start: GuestAddr(0x8000_0000),
            size: 8,
        },
    )
    .unwrap();
    let map = map_for(&rom, &image);

    let report = solve_with_rom(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
        &rom,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!report.blockers.iter().any(|b| {
        matches!(
            b.kind.as_str(),
            "canonical_rom_source_unverified" | "canonical_rom_source_mismatch"
        )
    }));
}

#[test]
fn image_without_claimed_rom_source_keeps_declared_static_semantics() {
    let rom = canonical_rom([0, 0], None);
    let image = supplied_image([0x0800_0000, 0], None);
    let map = map_for(&rom, &image);

    let report = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
}
