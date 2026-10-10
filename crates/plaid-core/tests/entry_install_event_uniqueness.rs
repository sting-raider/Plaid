use plaid_core::{
    EvidenceKind, GuestAddr,
    discovery::CodeImage,
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

fn imported(entries: &[u32]) -> ProgramMap {
    let known = image();
    import_trace(&trace(entries), &[known], 100).unwrap()
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
fn one_entry_install_event_cannot_authenticate_two_entry_identities() {
    let original = address(0x8000_0000, "boot", 0);
    let base = imported(&[original.pc.0]);
    let install = trace_id_with(&base, "EntryInstalled");
    assert!(base.entries[&original].contains(&install));

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
            forged.validate().is_err(),
            "one concrete EntryInstalled event was accepted for an incompatible {axis}"
        );
    }
}

#[test]
fn independently_valid_fragments_cannot_merge_one_install_event_into_two_roots() {
    let original = address(0x8000_0000, "boot", 0);
    let left = imported(&[original.pc.0]);
    let install = trace_id_with(&left, "EntryInstalled");

    let mut right = left.clone();
    right.entries.clear();
    right.entries.insert(
        address(0x8000_0008, "boot", 0),
        [install.clone()].into(),
    );
    right.validate().unwrap();

    assert!(
        merge_maps(&left, &right).is_err(),
        "independently valid fragments reused one EntryInstalled event as two roots"
    );
}

#[test]
fn distinct_install_events_may_install_distinct_entries() {
    let map = imported(&[0x8000_0000, 0x8000_0008]);
    map.validate().unwrap();
    assert!(map.entries.contains_key(&address(0x8000_0000, "boot", 0)));
    assert!(map.entries.contains_key(&address(0x8000_0008, "boot", 0)));
}

#[test]
fn compile_trace_provenance_is_legitimately_shared_across_entries() {
    let map = imported(&[0x8000_0000, 0x8000_0008]);
    let compile_begin = trace_id_with(&map, "CompileBegin");
    let first = &map.entries[&address(0x8000_0000, "boot", 0)];
    let second = &map.entries[&address(0x8000_0008, "boot", 0)];
    assert!(first.contains(&compile_begin));
    assert!(second.contains(&compile_begin));
}

#[test]
fn equivalent_entry_may_accumulate_non_event_provenance() {
    let mut map = imported(&[0x8000_0000]);
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
}
