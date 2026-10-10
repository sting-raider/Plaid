use plaid_core::{
    EvidenceKind, GuestAddr,
    discovery::CodeImage,
    entry_install::verify_entry_install_projection,
    merge::{import_trace, merge_maps},
    program::{CodeAddress, Evidence, PhysicalAddr, ProgramMap, RomIdentity, RomOffset},
    trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
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
        // Two independent self-jump roots, each with its own delay slot.
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
    let known = image();
    import_trace(source, &[known], 100).unwrap()
}

fn verify(source: &DiscoveryTrace, map: &ProgramMap) -> Result<(), String> {
    let known = image();
    verify_entry_install_projection(source, &[known], map, 100)
}

fn trace_id_with(map: &ProgramMap, needle: &str) -> String {
    map.evidence
        .iter()
        .find(|(_, e)| e.kind == EvidenceKind::Trace && e.detail.contains(needle))
        .map(|(id, _)| id.clone())
        .unwrap_or_else(|| panic!("missing trace evidence containing {needle:?}"))
}

fn address(pc: u32, image: &str, generation: u64) -> CodeAddress {
    CodeAddress {
        pc: GuestAddr(pc),
        image: image.into(),
        generation,
    }
}

#[test]
fn source_bound_verifier_rejects_one_install_event_on_two_entry_identities() {
    let source = trace(&[0x8000_0000]);
    let original = address(0x8000_0000, "boot", 0);
    let base = imported(&source);
    let install = trace_id_with(&base, "EntryInstalled");
    assert!(base.entries[&original].contains(&install));
    verify(&source, &base).unwrap();

    let forgeries = [
        ("different PC", address(0x8000_0008, "boot", 0)),
        ("different image", address(0x8000_0000, "decoy", 0)),
        ("different generation", address(0x8000_0000, "boot", 1)),
    ];
    for (axis, forged_entry) in forgeries {
        let mut forged = base.clone();
        forged
            .entries
            .insert(forged_entry, [install.clone()].into());
        assert!(
            forged.validate().is_ok(),
            "control changed: ProgramMap alone unexpectedly rejected {axis}"
        );
        assert!(
            verify(&source, &forged).is_err(),
            "source recheck accepted one EntryInstalled event for an incompatible {axis}"
        );
    }
}

#[test]
fn source_bound_verifier_rejects_cross_map_install_event_laundering() {
    let source = trace(&[0x8000_0000]);
    let left = imported(&source);
    let install = trace_id_with(&left, "EntryInstalled");

    let mut right = left.clone();
    right.entries.clear();
    right
        .entries
        .insert(address(0x8000_0008, "boot", 0), [install.clone()].into());
    right.validate().unwrap();

    let merged = merge_maps(&left, &right).unwrap();
    merged.validate().unwrap();
    assert!(
        verify(&source, &merged).is_err(),
        "source recheck accepted one EntryInstalled event composed into two roots"
    );
}

#[test]
fn distinct_install_events_may_install_distinct_entries() {
    let source = trace(&[0x8000_0000, 0x8000_0008]);
    let map = imported(&source);
    map.validate().unwrap();
    verify(&source, &map).unwrap();
    assert!(map.entries.contains_key(&address(0x8000_0000, "boot", 0)));
    assert!(map.entries.contains_key(&address(0x8000_0008, "boot", 0)));
}

#[test]
fn compile_trace_provenance_is_legitimately_shared_across_entries() {
    let source = trace(&[0x8000_0000, 0x8000_0008]);
    let map = imported(&source);
    let compile_begin = trace_id_with(&map, "CompileBegin");
    let first = &map.entries[&address(0x8000_0000, "boot", 0)];
    let second = &map.entries[&address(0x8000_0008, "boot", 0)];
    assert!(first.contains(&compile_begin));
    assert!(second.contains(&compile_begin));
    verify(&source, &map).unwrap();
}

#[test]
fn source_bound_verifier_rejects_tampered_event_metadata() {
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
