use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    program::{CodeAddress, GuestRange, RomOffset},
    rom::{CanonicalRom, sha256},
    solver::{ClosureStatus, Scope, solve},
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

fn image_bytes(image: &CodeImage) -> Vec<u8> {
    image.words.iter().flat_map(|word| word.to_be_bytes()).collect()
}

fn claimed_rom_bytes<'a>(rom: &'a CanonicalRom, image: &CodeImage) -> Option<&'a [u8]> {
    let offset = usize::try_from(image.rom_offset?.0).ok()?;
    rom.bytes().get(offset..offset.checked_add(image_bytes(image).len())?)
}

fn map_for(rom: &CanonicalRom, image: &CodeImage) -> plaid_core::program::ProgramMap {
    direct_cfg(rom.identity.clone(), image, &[GuestAddr(0x8000_0000)], 32)
        .unwrap()
        .map
}

#[test]
fn declared_static_closed_does_not_authenticate_claimed_rom_offset() {
    let rom = canonical_rom([0, 0], None);
    let image = supplied_image([0x0800_0000, 0], Some(RomOffset(64)));
    let map = map_for(&rom, &image);
    map.validate().unwrap();

    // The supplied image authenticates its own content and agrees with the Region's
    // metadata, but those bytes are not present at the claimed canonical ROM offset.
    assert_ne!(claimed_rom_bytes(&rom, &image).unwrap(), image_bytes(&image));
    assert_eq!(map.regions.first().unwrap().rom_offset, image.rom_offset);

    let report = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!report.native_complete);
    assert!(!report.assumptions.is_empty());
}

#[test]
fn equal_payload_decoy_elsewhere_does_not_validate_claimed_location() {
    let rom = canonical_rom([0, 0], Some([0x0800_0000, 0]));
    let image = supplied_image([0x0800_0000, 0], Some(RomOffset(64)));
    let map = map_for(&rom, &image);
    let bytes = image_bytes(&image);

    assert_ne!(claimed_rom_bytes(&rom, &image).unwrap(), bytes);
    assert_eq!(&rom.bytes()[72..80], bytes);

    // CLOSED remains valid only for the declared immutable-image scope. The equal
    // decoy at another ROM offset is deliberately not treated as source provenance.
    let report = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!report.native_complete);
}

#[test]
fn canonical_from_rom_control_is_byte_consistent_with_claimed_location() {
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

    assert_eq!(claimed_rom_bytes(&rom, &image).unwrap(), image_bytes(&image));
    let report = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!report.native_complete);
}

#[test]
fn image_without_rom_source_metadata_also_closes_relative_scope() {
    let rom = canonical_rom([0, 0], None);
    let image = supplied_image([0x0800_0000, 0], None);
    let map = map_for(&rom, &image);

    assert!(claimed_rom_bytes(&rom, &image).is_none());
    let report = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Closed);
    assert!(!report.native_complete);
}
