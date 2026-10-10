use plaid_core::{EvidenceKind, GuestAddr, program::*};

fn refs(id: &str) -> EvidenceRefs {
    [id.to_string()].into()
}

fn base_map() -> ProgramMap {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 0x4000,
    });
    map.evidence.insert(
        "trace:dma".into(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: "synthetic".into(),
            revision: "load-region-binding-v0".into(),
            detail: "one successful PI copy".into(),
        },
    );
    map.dma_observations.insert(ObservedDma {
        rom_offset: RomOffset(0x100),
        physical_destination: PhysicalAddr(0x1000),
        size: 0x20,
        evidence: refs("trace:dma"),
    });
    map.regions.insert(Region {
        image: "img".into(),
        generation: 7,
        range: GuestRange {
            start: GuestAddr(0x8000_1000),
            size: 0x20,
        },
        rom_offset: Some(RomOffset(0x100)),
        physical_start: Some(PhysicalAddr(0x1000)),
        overlay: None,
        evidence: refs("trace:dma"),
    });
    map
}

fn load(destination: u32, rom_offset: u64) -> LoadMapping {
    LoadMapping {
        rom_offset: RomOffset(rom_offset),
        destination: GuestRange {
            start: GuestAddr(destination),
            size: 0x20,
        },
        image: "img".into(),
        generation: 7,
        copy_event: Some("trace:dma".into()),
        evidence: refs("trace:dma"),
    }
}

#[test]
fn matching_copy_backed_load_and_region_validate() {
    let mut map = base_map();
    map.loads.insert(load(0x8000_1000, 0x100));
    map.validate().expect("matching importer-shaped mapping must validate");
}

#[test]
fn copy_event_cannot_authenticate_an_unrelated_guest_destination() {
    let mut map = base_map();
    map.loads.insert(load(0x8000_2000, 0x100));

    assert!(
        map.validate().is_err(),
        "one real DMA/physical witness must not authenticate a LoadMapping at an unrelated guest range"
    );
}

#[test]
fn copy_event_cannot_authenticate_a_region_with_different_rom_source() {
    let mut map = base_map();
    let region = map.regions.pop_first().expect("fixture region");
    map.regions.insert(Region {
        rom_offset: Some(RomOffset(0x200)),
        ..region
    });
    map.loads.insert(load(0x8000_1000, 0x100));

    assert!(
        map.validate().is_err(),
        "the Region carrying the physical mapping must agree with the LoadMapping ROM source"
    );
}
