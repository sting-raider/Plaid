use plaid_core::{
    EvidenceKind, GuestAddr,
    discovery::CodeImage,
    merge::{import_trace, merge_maps},
    program::{CodeAddress, Evidence, PhysicalAddr, ProgramMap, RomIdentity, RomOffset},
    trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
    trace_projection::verify_discovery_trace_projection_with_entries,
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "boot".into(),
            generation: 0,
        },
        words: vec![0x0800_0000, 0, 0x0800_0002, 0],
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
    }
}

fn trace(entries: &[u32]) -> DiscoveryTrace {
    let mut events = vec![EventRecord {
        seq: 0,
        data: TraceEvent::CompileBegin {
            unit: 7,
            start: GuestAddr(0x8000_0000),
            physical_start: Some(PhysicalAddr(0)),
            delay_slot_entry: false,
        },
    }];
    for pc in entries {
        events.push(EventRecord {
            seq: events.len() as u64,
            data: TraceEvent::EntryInstalled {
                unit: 7,
                pc: GuestAddr(*pc),
                register_mask: 0,
            },
        });
    }
    events.push(EventRecord {
        seq: events.len() as u64,
        data: TraceEvent::UnitCompiled {
            unit: 7,
            start: GuestAddr(0x8000_0000),
            words: image().words,
        },
    });
    DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: rom(),
            engine: "synthetic-entry-install".into(),
            revision: "test".into(),
            capabilities: Default::default(),
        },
        events,
    }
}

fn imported(source: &DiscoveryTrace) -> ProgramMap {
    import_trace(source, &[image()], 100).unwrap()
}

fn verify(source: &DiscoveryTrace, map: &ProgramMap) -> Result<(), String> {
    verify_discovery_trace_projection_with_entries(source, &[image()], map, 100)
}

fn trace_id_with(map: &ProgramMap, needle: &str) -> String {
    map.evidence
        .iter()
        .find(|(_, e)| e.kind == EvidenceKind::Trace && e.detail.contains(needle))
        .map(|(id, _)| id.clone())
        .unwrap()
}

fn address(pc: u32, image: &str, generation: u64) -> CodeAddress {
    CodeAddress {
        pc: GuestAddr(pc),
        image: image.into(),
        generation,
    }
}

#[test]
fn install_event_cannot_fork_entry_identity() {
    let source = trace(&[0x8000_0000]);
    let base = imported(&source);
    let install = trace_id_with(&base, "EntryInstalled");
    verify(&source, &base).unwrap();

    for forged_entry in [
        address(0x8000_0008, "boot", 0),
        address(0x8000_0000, "decoy", 0),
        address(0x8000_0000, "boot", 1),
    ] {
        let mut forged = base.clone();
        forged
            .entries
            .insert(forged_entry, [install.clone()].into());
        forged.validate().unwrap();
        assert!(verify(&source, &forged).is_err());
    }
}

#[test]
fn merge_cannot_launder_install_event() {
    let source = trace(&[0x8000_0000]);
    let left = imported(&source);
    let install = trace_id_with(&left, "EntryInstalled");

    let mut right = left.clone();
    right.entries.clear();
    right
        .entries
        .insert(address(0x8000_0008, "boot", 0), [install].into());
    right.validate().unwrap();

    let merged = merge_maps(&left, &right).unwrap();
    assert!(verify(&source, &merged).is_err());
}

#[test]
fn distinct_install_events_and_shared_compile_context_remain_valid() {
    let source = trace(&[0x8000_0000, 0x8000_0008]);
    let map = imported(&source);
    let compile_begin = trace_id_with(&map, "CompileBegin");
    assert!(map.entries[&address(0x8000_0000, "boot", 0)].contains(&compile_begin));
    assert!(map.entries[&address(0x8000_0008, "boot", 0)].contains(&compile_begin));
    verify(&source, &map).unwrap();
}

#[test]
fn tampered_install_event_metadata_is_rejected() {
    let source = trace(&[0x8000_0000]);
    let mut map = imported(&source);
    let install = trace_id_with(&map, "EntryInstalled");
    map.evidence
        .get_mut(&install)
        .unwrap()
        .detail
        .push_str("; forged detail");
    map.validate().unwrap();
    assert!(verify(&source, &map).is_err());
}

#[test]
fn equivalent_entry_may_accumulate_non_event_provenance() {
    let source = trace(&[0x8000_0000]);
    let mut map = imported(&source);
    map.evidence.insert(
        "aux".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "synthetic".into(),
            revision: "test".into(),
            detail: "independent supporting provenance".into(),
        },
    );
    map.entries
        .get_mut(&address(0x8000_0000, "boot", 0))
        .unwrap()
        .insert("aux".into());
    map.validate().unwrap();
    verify(&source, &map).unwrap();
}
