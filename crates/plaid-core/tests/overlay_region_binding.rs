use plaid_core::{EvidenceKind, GuestAddr, program::*};

fn base_map() -> ProgramMap {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 0x200,
    });
    map.evidence.insert(
        "overlay-evidence".into(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: "synthetic-overlay".into(),
            revision: "test".into(),
            detail: "synthetic overlay candidate".into(),
        },
    );
    map.overlays.insert(
        "ovl".into(),
        Overlay {
            image: "image-a".into(),
            rom_offset: RomOffset(0x40),
            size: 0x20,
            load_address: GuestAddr(0x8000_1000),
            candidate: true,
            evidence: ["overlay-evidence".into()].into(),
        },
    );
    map
}

fn matching_region(generation: u64) -> Region {
    Region {
        image: "image-a".into(),
        generation,
        range: GuestRange {
            start: GuestAddr(0x8000_1000),
            size: 0x20,
        },
        rom_offset: Some(RomOffset(0x40)),
        physical_start: Some(PhysicalAddr(0x1000)),
        overlay: Some("ovl".into()),
        evidence: ["overlay-evidence".into()].into(),
    }
}

#[test]
fn exact_overlay_descriptor_binding_is_valid_across_generations() {
    let mut map = base_map();
    map.regions.insert(matching_region(1));
    map.regions.insert(matching_region(2));
    map.validate().unwrap();
}

#[test]
fn region_cannot_borrow_same_image_overlay_with_different_rom_source() {
    let mut map = base_map();
    let mut region = matching_region(1);
    region.rom_offset = Some(RomOffset(0x80));
    map.regions.insert(region);
    assert!(map.validate().is_err());
}

#[test]
fn region_cannot_borrow_same_image_overlay_with_different_load_address() {
    let mut map = base_map();
    let mut region = matching_region(1);
    region.range.start = GuestAddr(0x8000_2000);
    map.regions.insert(region);
    assert!(map.validate().is_err());
}

#[test]
fn region_cannot_borrow_same_image_overlay_with_different_extent() {
    let mut map = base_map();
    let mut region = matching_region(1);
    region.range.size = 0x10;
    map.regions.insert(region);
    assert!(map.validate().is_err());
}

#[test]
fn mismatched_overlay_image_remains_rejected() {
    let mut map = base_map();
    let mut region = matching_region(1);
    region.image = "image-b".into();
    map.regions.insert(region);
    assert!(map.validate().is_err());
}
