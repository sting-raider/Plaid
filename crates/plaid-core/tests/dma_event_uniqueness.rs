use plaid_core::{EvidenceKind, GuestAddr, program::*};

fn base_map() -> ProgramMap {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 256,
    });
    map.evidence.insert(
        "copy0".into(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: "synthetic-dma".into(),
            revision: "0".into(),
            detail: "one completed synthetic DMA event".into(),
        },
    );
    map
}

fn add_copy(
    map: &mut ProgramMap,
    image: &str,
    generation: u64,
    guest: u32,
    rom: u64,
    physical: u32,
    size: u32,
    event: &str,
) {
    let evidence: EvidenceRefs = [event.to_string()].into();
    map.dma_observations.insert(ObservedDma {
        rom_offset: RomOffset(rom),
        physical_destination: PhysicalAddr(physical),
        size,
        evidence: evidence.clone(),
    });
    map.regions.insert(Region {
        image: image.into(),
        generation,
        range: GuestRange {
            start: GuestAddr(guest),
            size,
        },
        rom_offset: Some(RomOffset(rom)),
        physical_start: Some(PhysicalAddr(physical)),
        overlay: None,
        evidence: evidence.clone(),
    });
    map.loads.insert(LoadMapping {
        rom_offset: RomOffset(rom),
        destination: GuestRange {
            start: GuestAddr(guest),
            size,
        },
        image: image.into(),
        generation,
        copy_event: Some(event.into()),
        evidence,
    });
}

#[test]
fn one_copy_event_cannot_name_two_distinct_dma_transactions() {
    let mut map = base_map();
    add_copy(&mut map, "img-a", 0, 0x8000_0000, 64, 0, 8, "copy0");
    add_copy(&mut map, "img-b", 1, 0x8000_0020, 80, 32, 8, "copy0");

    assert!(
        map.validate().is_err(),
        "one source-bound copy event must not certify two incompatible DMA transactions"
    );
}

#[test]
fn distinct_copy_events_may_name_distinct_dma_transactions() {
    let mut map = base_map();
    map.evidence.insert(
        "copy1".into(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: "synthetic-dma".into(),
            revision: "0".into(),
            detail: "a different completed synthetic DMA event".into(),
        },
    );
    add_copy(&mut map, "img-a", 0, 0x8000_0000, 64, 0, 8, "copy0");
    add_copy(&mut map, "img-b", 1, 0x8000_0020, 80, 32, 8, "copy1");

    map.validate().unwrap();
}

#[test]
fn equivalent_dma_semantics_can_share_a_copy_event_with_more_provenance() {
    let mut map = base_map();
    map.evidence.insert(
        "aux".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "synthetic-check".into(),
            revision: "0".into(),
            detail: "independent corroboration of the same transaction".into(),
        },
    );
    add_copy(&mut map, "img-a", 0, 0x8000_0000, 64, 0, 8, "copy0");
    map.dma_observations.insert(ObservedDma {
        rom_offset: RomOffset(64),
        physical_destination: PhysicalAddr(0),
        size: 8,
        evidence: ["aux".into(), "copy0".into()].into(),
    });

    map.validate().unwrap();
}
