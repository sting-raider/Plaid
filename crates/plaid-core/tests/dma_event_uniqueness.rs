use plaid_core::{EvidenceKind, GuestAddr, program::*};

#[derive(Clone, Copy)]
struct CopyFact {
    image: &'static str,
    generation: u64,
    guest: u32,
    rom: u64,
    physical: u32,
    size: u32,
}

fn base_map() -> ProgramMap {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 256,
    });
    add_trace(&mut map, "copy0", "one completed synthetic DMA event");
    map
}

fn add_trace(map: &mut ProgramMap, event: &str, detail: &str) {
    map.evidence.insert(
        event.into(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: "synthetic-dma".into(),
            revision: "0".into(),
            detail: detail.into(),
        },
    );
}

fn add_copy(map: &mut ProgramMap, fact: CopyFact, event: &str) {
    let evidence: EvidenceRefs = [event.to_string()].into();
    map.dma_observations.insert(ObservedDma {
        rom_offset: RomOffset(fact.rom),
        physical_destination: PhysicalAddr(fact.physical),
        size: fact.size,
        evidence: evidence.clone(),
    });
    add_load_only(map, fact, event);
}

fn add_load_only(map: &mut ProgramMap, fact: CopyFact, event: &str) {
    let evidence: EvidenceRefs = [event.to_string()].into();
    map.regions.insert(Region {
        image: fact.image.into(),
        generation: fact.generation,
        range: GuestRange {
            start: GuestAddr(fact.guest),
            size: fact.size,
        },
        rom_offset: Some(RomOffset(fact.rom)),
        physical_start: Some(PhysicalAddr(fact.physical)),
        overlay: None,
        evidence: evidence.clone(),
    });
    map.loads.insert(LoadMapping {
        rom_offset: RomOffset(fact.rom),
        destination: GuestRange {
            start: GuestAddr(fact.guest),
            size: fact.size,
        },
        image: fact.image.into(),
        generation: fact.generation,
        copy_event: Some(event.into()),
        evidence,
    });
}

const A: CopyFact = CopyFact {
    image: "img-a",
    generation: 0,
    guest: 0x8000_0000,
    rom: 64,
    physical: 0,
    size: 8,
};

#[test]
fn one_copy_event_cannot_name_two_distinct_dma_transactions() {
    let mut map = base_map();
    add_copy(&mut map, A, "copy0");
    add_copy(
        &mut map,
        CopyFact {
            image: "img-b",
            generation: 1,
            guest: 0x8000_0020,
            rom: 80,
            physical: 32,
            size: 8,
        },
        "copy0",
    );

    assert!(
        map.validate().is_err(),
        "one source-bound copy event must not certify two incompatible DMA transactions"
    );
}

#[test]
fn each_dma_identity_component_is_causally_bound() {
    for forged in [
        CopyFact {
            image: "phys-conflict",
            generation: 1,
            guest: 0x8000_0020,
            physical: 32,
            ..A
        },
        CopyFact {
            image: "rom-conflict",
            generation: 1,
            guest: 0x8000_0020,
            rom: 80,
            ..A
        },
        CopyFact {
            image: "size-conflict",
            generation: 1,
            guest: 0x8000_0020,
            size: 12,
            ..A
        },
    ] {
        let mut map = base_map();
        add_copy(&mut map, A, "copy0");
        add_copy(&mut map, forged, "copy0");
        assert!(map.validate().is_err());
    }
}

#[test]
fn distinct_copy_events_may_name_distinct_dma_transactions() {
    let mut map = base_map();
    add_trace(
        &mut map,
        "copy1",
        "a different completed synthetic DMA event",
    );
    add_copy(&mut map, A, "copy0");
    add_copy(
        &mut map,
        CopyFact {
            image: "img-b",
            generation: 1,
            guest: 0x8000_0020,
            rom: 80,
            physical: 32,
            size: 8,
        },
        "copy1",
    );

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
    add_copy(&mut map, A, "copy0");
    map.dma_observations.insert(ObservedDma {
        rom_offset: RomOffset(A.rom),
        physical_destination: PhysicalAddr(A.physical),
        size: A.size,
        evidence: ["aux".into(), "copy0".into()].into(),
    });

    map.validate().unwrap();
}

#[test]
fn one_large_dma_event_may_cover_multiple_executable_subranges() {
    let mut map = base_map();
    map.dma_observations.insert(ObservedDma {
        rom_offset: RomOffset(64),
        physical_destination: PhysicalAddr(0),
        size: 16,
        evidence: ["copy0".into()].into(),
    });
    add_load_only(&mut map, A, "copy0");
    add_load_only(
        &mut map,
        CopyFact {
            image: "img-b",
            generation: 0,
            guest: 0x8000_0008,
            rom: 72,
            physical: 8,
            size: 8,
        },
        "copy0",
    );

    map.validate().unwrap();
}
