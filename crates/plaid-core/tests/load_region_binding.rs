use plaid_core::{GuestAddr, loads::*, program::*, rom::CanonicalRom};

fn rom() -> CanonicalRom {
    let mut bytes = vec![0; 128];
    bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    bytes[64..72].copy_from_slice(&[0x08, 0, 0, 0, 0, 0, 0, 0]);
    bytes[80..88].copy_from_slice(&[0x03, 0xe0, 0, 8, 0, 0, 0, 0]);
    CanonicalRom::from_bytes(&bytes).unwrap()
}

fn observation(rom: &CanonicalRom, physical_start: Option<PhysicalAddr>) -> LoadObservation {
    LoadObservation {
        rom_offset: RomOffset(64),
        destination: GuestRange {
            start: GuestAddr(0x8000_0000),
            size: 8,
        },
        physical_start,
        generation: 7,
        snapshot: rom.bytes()[64..72].to_vec(),
        producer: "load-region-binding-regression".into(),
        revision: "0".into(),
        event: 1,
        copy_event: None,
    }
}

fn legacy_load_map() -> ProgramMap {
    let r = rom();
    record_load(
        &ProgramMap::new(r.identity.clone()),
        &r,
        &observation(&r, Some(PhysicalAddr(0x1000))),
    )
    .unwrap()
}

#[test]
fn orphan_legacy_load_mapping_is_rejected() {
    let mut forged = legacy_load_map();
    assert_eq!(forged.loads.len(), 1);
    assert_eq!(forged.regions.len(), 1);
    forged.regions.clear();
    assert!(
        forged.validate().is_err(),
        "a retained load cannot survive deletion of the exact Region emitted with it"
    );
}

#[test]
fn legacy_load_cannot_borrow_region_with_wrong_rom_source() {
    let mut forged = legacy_load_map();
    let mut region = forged.regions.first().unwrap().clone();
    forged.regions.clear();
    region.rom_offset = Some(RomOffset(80));
    forged.regions.insert(region);
    assert!(
        forged.validate().is_err(),
        "same image/generation is insufficient when canonical ROM source differs"
    );
}

#[test]
fn legacy_load_cannot_borrow_region_with_wrong_guest_span() {
    let mut forged = legacy_load_map();
    let mut region = forged.regions.first().unwrap().clone();
    forged.regions.clear();
    region.range.start = GuestAddr(0x8000_0010);
    forged.regions.insert(region);
    assert!(
        forged.validate().is_err(),
        "same image/generation is insufficient when guest span differs"
    );
}

#[test]
fn exact_legacy_load_region_without_physical_mapping_remains_valid() {
    let r = rom();
    let map = record_load(
        &ProgramMap::new(r.identity.clone()),
        &r,
        &observation(&r, None),
    )
    .unwrap();
    assert_eq!(map.loads.len(), 1);
    assert_eq!(map.regions.len(), 1);
    assert!(map.validate().is_ok());
}
