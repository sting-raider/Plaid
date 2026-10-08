use plaid_core::{EvidenceKind, GuestAddr, discovery::*, merge::*, program::*, trace::*};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}
fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "boot".into(),
            generation: 0,
        },
        words: vec![0x08000000, 0],
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
    }
}
fn trace(words: Vec<u32>) -> DiscoveryTrace {
    DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: rom(),
            engine: "sensor".into(),
            revision: "pin".into(),
            capabilities: Default::default(),
        },
        events: vec![
            EventRecord {
                seq: 0,
                data: TraceEvent::CompileBegin {
                    unit: 0,
                    start: GuestAddr(0x80000000),
                    physical_start: Some(PhysicalAddr(0)),
                    delay_slot_entry: false,
                },
            },
            EventRecord {
                seq: 1,
                data: TraceEvent::EntryInstalled {
                    unit: 0,
                    pc: GuestAddr(0x80000000),
                    register_mask: 0,
                },
            },
            EventRecord {
                seq: 2,
                data: TraceEvent::UnitCompiled {
                    unit: 0,
                    start: GuestAddr(0x80000000),
                    words,
                },
            },
        ],
    }
}

#[test]
fn static_and_dynamic_facts_merge_with_both_provenances() {
    let i = image();
    let static_map = direct_cfg(rom(), &i, &[i.base.pc], 100).unwrap().map;
    let dynamic = import_trace(&trace(i.words.clone()), &[i], 100).unwrap();
    let merged = merge_maps(&static_map, &dynamic).unwrap();
    assert_eq!(merged.blocks.len(), 1);
    assert!(
        merged
            .blocks
            .first()
            .unwrap()
            .evidence
            .iter()
            .any(|id| merged.evidence[id].kind == EvidenceKind::Trace)
    );
    assert!(
        merged
            .blocks
            .first()
            .unwrap()
            .evidence
            .iter()
            .any(|id| merged.evidence[id].kind == EvidenceKind::Static)
    );
    assert_eq!(
        merged.to_json().unwrap(),
        merge_maps(&dynamic, &static_map)
            .unwrap()
            .to_json()
            .unwrap()
    );
    assert_eq!(merged, merge_maps(&merged, &merged).unwrap());
}

#[test]
fn contradictions_and_rom_or_provenance_identity_conflicts_are_visible() {
    let i = image();
    let a = direct_cfg(rom(), &i, &[i.base.pc], 100).unwrap().map;
    let mut b = a.clone();
    let mut block = b.blocks.pop_first().unwrap();
    block.size = 4;
    b.blocks.insert(block);
    let m = merge_maps(&a, &b).unwrap();
    assert_eq!(m.blocks.len(), 2);
    assert!(m.unresolved.iter().any(|u| u.kind == "conflicting_block"));
    b = a.clone();
    b.rom.sha256 = "b".repeat(64);
    assert!(merge_maps(&a, &b).is_err());
    b = a.clone();
    b.evidence.values_mut().next().unwrap().detail = "different evidence".into();
    assert!(
        merge_maps(&a, &b)
            .unwrap_err()
            .contains("conflicting provenance")
    );
}

#[test]
fn mismatched_bytes_do_not_merge_by_pc_and_lookups_are_not_indirect_proofs() {
    let mut t = trace(vec![0x01000008, 0]);
    t.events.push(EventRecord {
        seq: 3,
        data: TraceEvent::TargetLookup {
            target: GuestAddr(0x80000000),
            delay_slot_entry: false,
        },
    });
    let m = import_trace(&t, &[image()], 100).unwrap();
    assert!(m.regions.iter().all(|r| r.image != "boot"));
    assert!(
        m.indirect_sites
            .iter()
            .all(|s| s.observed.is_empty() && s.closed_proof.is_none())
    );
    assert!(m.unresolved.iter().any(|u| u.kind == "uncorrelated_target"));
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "unknown_executable_source")
    );
}

#[test]
fn invalidation_and_same_pc_recompilation_keep_distinct_generations() {
    let i = image();
    let mut t = trace(i.words.clone());
    t.events.push(EventRecord {
        seq: 3,
        data: TraceEvent::Invalidate { range: None },
    });
    let second = trace(i.words.clone());
    for mut e in second.events {
        e.seq += 4;
        match &mut e.data {
            TraceEvent::CompileBegin { unit, .. }
            | TraceEvent::UnitCompiled { unit, .. }
            | TraceEvent::EntryInstalled { unit, .. } => *unit = 1,
            _ => (),
        };
        t.events.push(e);
    }
    let m = import_trace(&t, &[i], 100).unwrap();
    assert!(m.regions.iter().any(|r| r.generation == 0));
    assert!(m.regions.iter().any(|r| r.generation == 1));
    assert_eq!(m.executable_writes.len(), 1);
}
