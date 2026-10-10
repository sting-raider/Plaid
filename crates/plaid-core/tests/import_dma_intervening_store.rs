use plaid_core::{
    GuestAddr,
    discovery::CodeImage,
    merge::import_trace_with_rom,
    program::{GuestRange, PhysicalAddr, RomOffset},
    rom::CanonicalRom,
    trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
};

fn rom_and_words() -> (CanonicalRom, Vec<u32>) {
    let mut bytes = vec![0; 4096];
    bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    let words: Vec<u32> = vec![0x0800_0000, 0];
    bytes[64..68].copy_from_slice(&words[0].to_be_bytes());
    bytes[68..72].copy_from_slice(&words[1].to_be_bytes());
    (CanonicalRom::from_bytes(&bytes).unwrap(), words)
}

fn known_image(rom: &CanonicalRom) -> CodeImage {
    let mut image = CodeImage::from_rom(
        rom,
        RomOffset(64),
        GuestRange {
            start: GuestAddr(0x8000_0000),
            size: 8,
        },
    )
    .unwrap();
    image.physical_start = Some(PhysicalAddr(0));
    image
}

fn trace_with_prefix(rom: &CanonicalRom, words: &[u32], mut prefix: Vec<TraceEvent>) -> DiscoveryTrace {
    prefix.extend([
        TraceEvent::CompileBegin {
            unit: 0,
            start: GuestAddr(0x8000_0000),
            physical_start: Some(PhysicalAddr(0)),
            delay_slot_entry: false,
        },
        TraceEvent::EntryInstalled {
            unit: 0,
            pc: GuestAddr(0x8000_0000),
            register_mask: 0,
        },
        TraceEvent::UnitCompiled {
            unit: 0,
            start: GuestAddr(0x8000_0000),
            words: words.to_vec(),
        },
    ]);
    DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: rom.identity.clone(),
            engine: "sensor".into(),
            revision: "pin".into(),
            capabilities: Default::default(),
        },
        events: prefix
            .into_iter()
            .enumerate()
            .map(|(seq, data)| EventRecord {
                seq: seq as u64,
                data,
            })
            .collect(),
    }
}

fn dma() -> TraceEvent {
    TraceEvent::RomDmaObserved {
        rom_offset: RomOffset(64),
        physical_destination: PhysicalAddr(0),
        size: 8,
    }
}

fn store(destination: u32, value: u32) -> TraceEvent {
    TraceEvent::CpuWordStoreObserved {
        site: GuestAddr(0x8000_0100),
        destination: GuestAddr(destination),
        value,
    }
}

#[test]
fn overlapping_same_value_store_after_dma_must_revoke_dma_byte_origin() {
    let (rom, words) = rom_and_words();
    let trace = trace_with_prefix(
        &rom,
        &words,
        vec![dma(), store(0x8000_0000, words[0])],
    );
    let map = import_trace_with_rom(&trace, &[], &rom, 100).unwrap();

    assert_eq!(map.word_store_observations.len(), 1);
    assert!(
        map.loads.is_empty(),
        "a later successful store supersedes the DMA writer even when the word value is unchanged: {:?}",
        map.loads
    );
    assert!(
        map.unresolved
            .iter()
            .any(|u| u.kind == "unknown_executable_source"),
        "the first compilation should remain source-unknown after the DMA provenance is superseded"
    );
}

#[test]
fn same_value_store_cannot_fall_back_to_equal_known_image() {
    let (rom, words) = rom_and_words();
    let known = known_image(&rom);
    let trace = trace_with_prefix(
        &rom,
        &words,
        vec![dma(), store(0x8000_0000, words[0])],
    );
    let map = import_trace_with_rom(&trace, &[known], &rom, 100).unwrap();

    assert!(map.loads.is_empty());
    assert!(
        map.unresolved
            .iter()
            .any(|u| u.kind == "unknown_executable_source"),
        "equal bytes in a supplied image cannot replace superseded writer provenance"
    );
}

#[test]
fn invalidation_does_not_make_a_superseded_dma_writer_current_again() {
    let (rom, words) = rom_and_words();
    let trace = trace_with_prefix(
        &rom,
        &words,
        vec![
            dma(),
            store(0x8000_0000, words[0]),
            TraceEvent::Invalidate { range: None },
        ],
    );
    let map = import_trace_with_rom(&trace, &[], &rom, 100).unwrap();

    assert!(map.loads.is_empty());
    assert!(
        map.unresolved
            .iter()
            .any(|u| u.kind == "unknown_executable_source")
    );
}

#[test]
fn overlapping_store_before_dma_is_superseded_by_later_copy() {
    let (rom, words) = rom_and_words();
    let trace = trace_with_prefix(
        &rom,
        &words,
        vec![store(0x8000_0000, words[0]), dma()],
    );
    let map = import_trace_with_rom(&trace, &[], &rom, 100).unwrap();
    assert_eq!(map.loads.len(), 1);
    assert!(
        !map.unresolved
            .iter()
            .any(|u| u.kind == "unknown_executable_source")
    );
}

#[test]
fn later_dma_after_store_and_invalidation_restores_copy_provenance() {
    let (rom, words) = rom_and_words();
    let trace = trace_with_prefix(
        &rom,
        &words,
        vec![
            store(0x8000_0000, words[0]),
            TraceEvent::Invalidate { range: None },
            dma(),
        ],
    );
    let map = import_trace_with_rom(&trace, &[], &rom, 100).unwrap();
    assert_eq!(map.loads.len(), 1);
    assert!(
        !map.unresolved
            .iter()
            .any(|u| u.kind == "unknown_executable_source")
    );
}

#[test]
fn non_overlapping_store_after_dma_does_not_revoke_copy() {
    let (rom, words) = rom_and_words();
    let trace = trace_with_prefix(
        &rom,
        &words,
        vec![dma(), store(0x8000_0100, words[0])],
    );
    let map = import_trace_with_rom(&trace, &[], &rom, 100).unwrap();
    assert_eq!(map.loads.len(), 1);
    assert!(
        !map.unresolved
            .iter()
            .any(|u| u.kind == "unknown_executable_source")
    );
}

#[test]
fn changed_value_snapshot_already_fails_closed() {
    let (rom, _words) = rom_and_words();
    let changed: Vec<u32> = vec![0x2402_0001, 0];
    let trace = trace_with_prefix(
        &rom,
        &changed,
        vec![dma(), store(0x8000_0000, changed[0])],
    );
    let map = import_trace_with_rom(&trace, &[], &rom, 100).unwrap();
    assert!(map.loads.is_empty());
    assert!(
        map.unresolved
            .iter()
            .any(|u| u.kind == "executable_load_bytes_mismatch")
    );
}
