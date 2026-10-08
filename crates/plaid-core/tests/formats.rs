use plaid_core::{EvidenceKind, GuestAddr, program::*, trace::*};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}
fn addr(pc: u32) -> CodeAddress {
    CodeAddress {
        pc: GuestAddr(pc),
        image: "boot".into(),
        generation: 0,
    }
}
fn evidence() -> Evidence {
    Evidence {
        kind: EvidenceKind::Static,
        producer: "synthetic".into(),
        revision: "v0".into(),
        detail: "test source".into(),
    }
}
fn map() -> ProgramMap {
    let mut p = ProgramMap::new(rom());
    p.evidence.insert("e1".into(), evidence());
    p.entries.insert(addr(0x80000000), ["e1".into()].into());
    p.blocks.insert(BasicBlock {
        start: addr(0x80000000),
        size: 8,
        delay_slot_entry: false,
        evidence: ["e1".into()].into(),
    });
    p.indirect_sites.insert(IndirectSite {
        site: addr(0x80000004),
        link_register: None,
        delay_slot: DelaySlot::Always,
        candidates: [(addr(0x80000020), ["e1".into()].into())].into(),
        observed: Default::default(),
        closed_proof: None,
        evidence: ["e1".into()].into(),
    });
    p
}

#[test]
fn map_roundtrip_and_order_are_canonical() {
    let mut a = map();
    a.evidence.insert("e2".into(), evidence());
    a.entries.insert(addr(0x80000020), ["e2".into()].into());
    let mut b = map();
    b.entries.insert(addr(0x80000020), ["e2".into()].into());
    b.evidence.insert("e2".into(), evidence());
    let json = a.to_json().unwrap();
    assert_eq!(json, b.to_json().unwrap());
    assert_eq!(ProgramMap::from_json(&json).unwrap(), a);
}

#[test]
fn map_rejects_bad_version_provenance_ranges_and_unknown_fields() {
    let mut p = map();
    p.schema_version = 1;
    assert!(p.to_json().is_err());
    p = map();
    p.evidence.clear();
    assert!(p.to_json().is_err());
    assert!(
        GuestRange {
            start: GuestAddr(0xfffffffc),
            size: 8
        }
        .validate(true)
        .is_err()
    );
    assert!(
        GuestRange {
            start: GuestAddr(0xfffffffc),
            size: 4
        }
        .validate(true)
        .is_ok()
    );
    let json = map()
        .to_json()
        .unwrap()
        .replacen('{', "{\"future_field\":true,", 1);
    assert!(ProgramMap::from_json(&json).is_err());
}

#[test]
fn execution_identity_preserves_overlay_and_generation() {
    let mut a = addr(0x80000000);
    let b = a.clone();
    a.image = "overlay".into();
    let mut c = b.clone();
    c.generation = 1;
    assert_eq!(
        [a, b, c]
            .into_iter()
            .collect::<std::collections::BTreeSet<_>>()
            .len(),
        3
    );
}

fn trace() -> DiscoveryTrace {
    DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: rom(),
            engine: "synthetic".into(),
            revision: "v0".into(),
            capabilities: ["units".into()].into(),
        },
        events: vec![
            EventRecord {
                seq: 0,
                data: TraceEvent::CompileBegin {
                    unit: 7,
                    start: GuestAddr(0x80000000),
                    physical_start: None,
                    delay_slot_entry: true,
                },
            },
            EventRecord {
                seq: 1,
                data: TraceEvent::EntryInstalled {
                    unit: 7,
                    pc: GuestAddr(0x80000000),
                    register_mask: 0,
                },
            },
            EventRecord {
                seq: 2,
                data: TraceEvent::UnitCompiled {
                    unit: 7,
                    start: GuestAddr(0x80000000),
                    words: vec![0, 0],
                },
            },
            EventRecord {
                seq: 3,
                data: TraceEvent::Invalidate { range: None },
            },
        ],
    }
}

#[test]
fn trace_roundtrip_and_sequence_validation() {
    let t = trace();
    let json = t.to_ndjson().unwrap();
    assert_eq!(DiscoveryTrace::from_ndjson(&json).unwrap(), t);
    let mut invalid = t.clone();
    invalid.events[2].seq = 4;
    assert!(invalid.validate().is_err());
    invalid = t.clone();
    invalid.events.pop();
    invalid.events.pop();
    assert!(invalid.validate().is_err());
    invalid = t;
    invalid.events[1].data = TraceEvent::EntryInstalled {
        unit: 7,
        pc: GuestAddr(0x80000040),
        register_mask: 0,
    };
    assert!(invalid.validate().is_err());
}

#[test]
fn trace_rejects_truncation_extra_unknown_and_reordered_records() {
    let json = trace().to_ndjson().unwrap();
    assert!(
        DiscoveryTrace::from_ndjson(&json.lines().take(4).collect::<Vec<_>>().join("\n")).is_err()
    );
    assert!(DiscoveryTrace::from_ndjson(&(json.clone() + "{}\n")).is_err());
    assert!(
        DiscoveryTrace::from_ndjson(&json.replace(
            "\"register_mask\":0",
            "\"register_mask\":0,\"host_pointer\":123"
        ))
        .is_err()
    );
    assert!(
        DiscoveryTrace::from_ndjson(&json.replace("\"schema_version\":0", "\"schema_version\":9"))
            .is_err()
    );
}

#[test]
fn duplicate_provenance_keys_and_structured_keys_are_rejected() {
    let p = map();
    let mut json = serde_json::to_value(&p).unwrap();
    let e = serde_json::to_string(&evidence()).unwrap();
    json["evidence"] = serde_json::json!({});
    let text = serde_json::to_string(&json).unwrap().replace(
        "\"evidence\":{}",
        &format!("\"evidence\":{{\"e1\":{e},\"e1\":{e}}}"),
    );
    assert!(
        ProgramMap::from_json(&text)
            .unwrap_err()
            .contains("duplicate")
    );
    let mut json = serde_json::to_value(&p).unwrap();
    let duplicate = json["entries"][0].clone();
    json["entries"].as_array_mut().unwrap().push(duplicate);
    assert!(
        ProgramMap::from_json(&json.to_string())
            .unwrap_err()
            .contains("duplicate")
    );
}

#[test]
fn raw_dma_range_must_fit_rom_and_physical_space() {
    let mut t = trace();
    t.events.push(EventRecord {
        seq: 4,
        data: TraceEvent::RomDmaObserved {
            rom_offset: RomOffset(4092),
            physical_destination: PhysicalAddr(0),
            size: 8,
        },
    });
    assert!(t.validate().is_err());
    t.events[4].data = TraceEvent::RomDmaObserved {
        rom_offset: RomOffset(64),
        physical_destination: PhysicalAddr(0xffffffff),
        size: 8,
    };
    assert!(t.validate().is_err());
    t.events[4].data = TraceEvent::RomDmaObserved {
        rom_offset: RomOffset(64),
        physical_destination: PhysicalAddr(0),
        size: 0,
    };
    assert!(t.validate().is_err());
}
