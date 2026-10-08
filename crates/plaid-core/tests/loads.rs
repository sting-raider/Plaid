use plaid_core::{GuestAddr, loads::*, program::*, rom::CanonicalRom};

fn rom() -> CanonicalRom {
    let mut bytes = vec![0; 128];
    bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    bytes[64..72].copy_from_slice(&[0x08, 0, 0, 0, 0, 0, 0, 0]);
    bytes[80..88].copy_from_slice(&[0x03, 0xe0, 0, 8, 0, 0, 0, 0]);
    CanonicalRom::from_bytes(&bytes).unwrap()
}
fn observation(rom: &CanonicalRom, offset: u64, generation: u64) -> LoadObservation {
    LoadObservation {
        rom_offset: RomOffset(offset),
        destination: GuestRange {
            start: GuestAddr(0x80000000),
            size: 8,
        },
        physical_start: Some(PhysicalAddr(0)),
        generation,
        snapshot: rom.bytes()[offset as usize..offset as usize + 8].to_vec(),
        producer: "synthetic-dma".into(),
        revision: "0".into(),
        event: generation,
    }
}

#[test]
fn exact_copy_and_reload_keep_rom_provenance_and_generation() {
    let r = rom();
    let m = ProgramMap::new(r.identity.clone());
    let m = record_load(&m, &r, &observation(&r, 64, 0)).unwrap();
    let m = record_load(&m, &r, &observation(&r, 64, 1)).unwrap();
    assert_eq!(m.loads.len(), 2);
    assert_eq!(m.regions.len(), 2);
    assert!(
        m.executable_writes
            .iter()
            .any(|w| w.kind == WriteKind::OverlayReload)
    );
    assert!(m.overlays.is_empty());
    assert!(m.unresolved.is_empty());
}

#[test]
fn overlapping_distinct_sources_create_candidates_not_resolved_overlays() {
    let r = rom();
    let m = ProgramMap::new(r.identity.clone());
    let m = record_load(&m, &r, &observation(&r, 64, 0)).unwrap();
    let m = record_load(&m, &r, &observation(&r, 80, 1)).unwrap();
    assert_eq!(m.overlays.len(), 2);
    assert!(m.overlays.values().all(|o| o.candidate));
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "overlay_candidate_lifecycle_unknown")
    );
    assert!(m.executable_writes.is_empty());
}

#[test]
fn changed_snapshot_does_not_get_rom_source_or_relocation_certainty() {
    let r = rom();
    let mut o = observation(&r, 64, 0);
    o.snapshot[0] ^= 1;
    let m = record_load(&ProgramMap::new(r.identity.clone()), &r, &o).unwrap();
    assert!(m.loads.is_empty());
    assert!(m.regions.is_empty());
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "executable_load_bytes_mismatch")
    );
    assert_eq!(
        m.executable_writes.first().unwrap().kind,
        WriteKind::Unknown
    );
}

#[test]
fn malformed_snapshots_and_rom_mismatch_are_errors() {
    let r = rom();
    let mut o = observation(&r, 64, 0);
    o.snapshot.pop();
    assert!(record_load(&ProgramMap::new(r.identity.clone()), &r, &o).is_err());
    let mut m = ProgramMap::new(r.identity.clone());
    m.rom.sha256 = "b".repeat(64);
    assert!(record_load(&m, &r, &observation(&r, 64, 0)).is_err());
}
