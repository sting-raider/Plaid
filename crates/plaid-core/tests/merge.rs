use plaid_core::{
    EvidenceKind, GuestAddr, discovery::*, merge::*, program::*, rom::CanonicalRom, trace::*,
};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

#[test]
fn observed_dma_and_captured_words_establish_verified_executable_source() {
    let mut bytes = vec![0; 4096];
    bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    bytes[64..72].copy_from_slice(&[8, 0, 0, 0, 0, 0, 0, 0]);
    let rom = CanonicalRom::from_bytes(&bytes).unwrap();
    let mut t = trace(vec![0x08000000, 0]);
    t.header.rom = rom.identity.clone();
    for e in &mut t.events {
        e.seq += 1;
    }
    t.events.insert(
        0,
        EventRecord {
            seq: 0,
            data: TraceEvent::RomDmaObserved {
                rom_offset: RomOffset(64),
                physical_destination: PhysicalAddr(0),
                size: 8,
            },
        },
    );
    let m = import_trace_with_rom(&t, &[], &rom, 100).unwrap();
    assert_eq!(m.loads.len(), 1);
    assert_eq!(m.dma_observations.len(), 1);
    assert_eq!(m.loads.first().unwrap().rom_offset, RomOffset(64));
    assert!(
        !m.unresolved
            .iter()
            .any(|u| u.kind == "unknown_executable_source")
    );
    t.events[3].data = TraceEvent::UnitCompiled {
        unit: 0,
        start: GuestAddr(0x80000000),
        words: vec![0x03e00008, 0],
    };
    let m = import_trace_with_rom(&t, &[], &rom, 100).unwrap();
    assert!(m.loads.is_empty());
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "executable_load_bytes_mismatch")
    );
}

#[test]
fn repeated_compilation_is_not_a_new_dma_reload() {
    let mut bytes = vec![0; 4096];
    bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    bytes[64..72].copy_from_slice(&[8, 0, 0, 0, 0, 0, 0, 0]);
    let rom = CanonicalRom::from_bytes(&bytes).unwrap();
    let dma = TraceEvent::RomDmaObserved {
        rom_offset: RomOffset(64),
        physical_destination: PhysicalAddr(0),
        size: 8,
    };
    let mut t = trace(vec![0x08000000, 0]);
    t.header.rom = rom.identity.clone();
    let mut second = t.events.clone();
    for event in &mut second {
        match &mut event.data {
            TraceEvent::CompileBegin { unit, .. }
            | TraceEvent::EntryInstalled { unit, .. }
            | TraceEvent::UnitCompiled { unit, .. } => *unit = 1,
            _ => unreachable!(),
        }
    }
    t.events.insert(
        0,
        EventRecord {
            seq: 0,
            data: dma.clone(),
        },
    );
    t.events.push(EventRecord {
        seq: 0,
        data: TraceEvent::Invalidate { range: None },
    });
    t.events.extend(second);
    for (seq, event) in t.events.iter_mut().enumerate() {
        event.seq = seq as u64;
    }
    let recompiled = import_trace_with_rom(&t, &[], &rom, 100).unwrap();
    assert_eq!(recompiled.loads.len(), 2);
    assert_eq!(
        recompiled
            .loads
            .iter()
            .map(|l| l.copy_event.clone())
            .collect::<std::collections::BTreeSet<_>>()
            .len(),
        1
    );
    assert!(
        !recompiled
            .executable_writes
            .iter()
            .any(|w| w.kind == WriteKind::OverlayReload)
    );
    // A distinct sensed copy followed by a matching snapshot can establish reload.
    t.events.insert(5, EventRecord { seq: 0, data: dma });
    for (seq, event) in t.events.iter_mut().enumerate() {
        event.seq = seq as u64;
    }
    let reloaded = import_trace_with_rom(&t, &[], &rom, 100).unwrap();
    assert!(
        reloaded
            .executable_writes
            .iter()
            .any(|w| w.kind == WriteKind::OverlayReload)
    );
    assert_eq!(
        reloaded,
        ProgramMap::from_json(&reloaded.to_json().unwrap()).unwrap()
    );
    let mut misplaced = reloaded.clone();
    misplaced.dma_observations = misplaced
        .dma_observations
        .iter()
        .cloned()
        .map(|mut d| {
            d.physical_destination = PhysicalAddr(32);
            d
        })
        .collect();
    assert!(misplaced.validate().is_err());
    let mut legacy: serde_json::Value = serde_json::from_str(&reloaded.to_json().unwrap()).unwrap();
    for load in legacy["loads"].as_array_mut().unwrap() {
        load.as_object_mut().unwrap().remove("copy_event");
    }
    let legacy = ProgramMap::from_json(&legacy.to_string()).unwrap();
    assert!(legacy.loads.iter().all(|l| l.copy_event.is_none()));
    // Deleting or changing the explicit event's provenance is rejected.
    let mut invalid = reloaded;
    let mut load = invalid.loads.pop_first().unwrap();
    load.evidence.remove(load.copy_event.as_ref().unwrap());
    invalid.loads.insert(load);
    assert!(invalid.validate().is_err());
}

#[test]
fn actual_word_store_evidence_survives_and_only_known_code_overlap_is_executable() {
    let known = image();
    let mut t = trace(known.words.clone());
    for destination in [GuestAddr(0x80000000), GuestAddr(0x80000100)] {
        t.events.push(EventRecord {
            seq: t.events.len() as u64,
            data: TraceEvent::CpuWordStoreObserved {
                site: GuestAddr(0x80000000),
                destination,
                value: 0x12345678,
            },
        });
    }
    let map = import_trace(&t, &[known], 100).unwrap();
    assert_eq!(map.word_store_observations.len(), 2);
    assert_eq!(map.executable_writes.len(), 1);
    let write = map.executable_writes.first().unwrap();
    assert_eq!(write.kind, WriteKind::Unknown);
    assert_eq!(write.range.as_ref().unwrap().start, GuestAddr(0x80000000));
    assert_eq!(write.range.as_ref().unwrap().size, 4);
    assert_eq!(map, merge_maps(&map, &map).unwrap());
    assert_eq!(map, ProgramMap::from_json(&map.to_json().unwrap()).unwrap());
}

#[test]
fn unproved_evidence_merges_into_a_static_certificate_without_duplicate_sites() {
    let mut i = image();
    i.words = vec![0x3c088000, 0x35080000, 0x01000008, 0];
    let a = direct_cfg(rom(), &i, &[i.base.pc], 100).unwrap().map;
    let b = plaid_core::indirect::analyze_indirect(&a, &i).unwrap();
    let m = merge_maps(&a, &b).unwrap();
    assert_eq!(m.indirect_sites.len(), 1);
    assert!(plaid_core::indirect::verify_constant(
        &m,
        &i,
        m.indirect_sites.first().unwrap()
    ));
    assert_eq!(m, merge_maps(&b, &a).unwrap());
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

#[test]
fn indirect_observation_precedes_target_compilation_and_survives_raw() {
    let mut known = image();
    known.words = vec![0x01000008, 0, 0, 0, 0, 0, 0, 0, 0x08000008, 0];
    let mut t = trace(known.words[..2].to_vec());
    for data in [
        TraceEvent::IndirectTargetObserved {
            site: GuestAddr(0x80000000),
            target: GuestAddr(0x80000020),
            delay_slot_pc: Some(GuestAddr(0x80000004)),
            source_unit: None,
        },
        TraceEvent::CompileBegin {
            unit: 1,
            start: GuestAddr(0x80000020),
            physical_start: Some(PhysicalAddr(32)),
            delay_slot_entry: false,
        },
        TraceEvent::EntryInstalled {
            unit: 1,
            pc: GuestAddr(0x80000020),
            register_mask: 0,
        },
        TraceEvent::UnitCompiled {
            unit: 1,
            start: GuestAddr(0x80000020),
            words: known.words[8..].to_vec(),
        },
    ] {
        t.events.push(EventRecord {
            seq: t.events.len() as u64,
            data,
        });
    }
    let m = import_trace(&t, std::slice::from_ref(&known), 100).unwrap();
    assert_eq!(m.indirect_observations.len(), 1);
    let site = m.indirect_sites.first().unwrap();
    assert_eq!(site.observed.len(), 1);
    assert_eq!(
        site.observed.first_key_value().unwrap().0,
        &known.address(GuestAddr(0x80000020))
    );
    assert!(site.closed_proof.is_none());
    assert!(
        !m.unresolved
            .iter()
            .any(|u| u.kind == "uncorrelated_indirect_observation")
    );
    assert_eq!(m, ProgramMap::from_json(&m.to_json().unwrap()).unwrap());
    assert_eq!(m, merge_maps(&m, &m).unwrap());

    // A future generation cannot explain an earlier runtime transfer.
    t.events.insert(
        4,
        EventRecord {
            seq: 0,
            data: TraceEvent::Invalidate { range: None },
        },
    );
    for (seq, event) in t.events.iter_mut().enumerate() {
        event.seq = seq as u64;
    }
    let m = import_trace(&t, &[known], 100).unwrap();
    assert_eq!(m.indirect_observations.len(), 1);
    assert!(m.indirect_sites.iter().all(|s| s.observed.is_empty()));
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "uncorrelated_indirect_observation")
    );
}

#[test]
fn explicit_executing_unit_identifies_stale_source_but_not_stale_target() {
    let mut t = trace(vec![0x01000008, 0]);
    for data in [
        TraceEvent::Invalidate { range: None },
        TraceEvent::IndirectTargetObserved {
            site: GuestAddr(0x80000000),
            target: GuestAddr(0x80000020),
            delay_slot_pc: Some(GuestAddr(0x80000004)),
            source_unit: Some(0),
        },
        TraceEvent::CompileBegin {
            unit: 1,
            start: GuestAddr(0x80000020),
            physical_start: Some(PhysicalAddr(32)),
            delay_slot_entry: false,
        },
        TraceEvent::UnitCompiled {
            unit: 1,
            start: GuestAddr(0x80000020),
            words: vec![0x03e00008, 0],
        },
        TraceEvent::IndirectTargetObserved {
            site: GuestAddr(0x80000020),
            target: GuestAddr(0x80000000),
            delay_slot_pc: Some(GuestAddr(0x80000024)),
            source_unit: Some(1),
        },
    ] {
        t.events.push(EventRecord {
            seq: t.events.len() as u64,
            data,
        });
    }
    let m = import_trace(&t, &[], 100).unwrap();
    let source = m
        .indirect_sites
        .iter()
        .find(|s| s.site.pc == GuestAddr(0x80000000))
        .unwrap();
    assert_eq!(source.site.generation, 0);
    assert_eq!(source.observed.len(), 1);
    assert_eq!(source.observed.first_key_value().unwrap().0.generation, 1);
    let returning = m
        .indirect_sites
        .iter()
        .find(|s| s.site.pc == GuestAddr(0x80000020))
        .unwrap();
    assert!(returning.observed.is_empty());
    assert!(
        m.unresolved
            .iter()
            .any(|u| u.kind == "uncorrelated_indirect_observation"
                && u.site.as_ref() == Some(&returning.site))
    );
    assert!(m.indirect_sites.iter().all(|s| s.closed_proof.is_none()));
    assert!(
        m.indirect_observations
            .iter()
            .all(|o| o.generation == 1 && o.source_unit.is_some())
    );
    assert_eq!(m, ProgramMap::from_json(&m.to_json().unwrap()).unwrap());
    assert_eq!(m, merge_maps(&m, &m).unwrap());
    let mut missing_provenance = m.clone();
    let unit = m
        .indirect_observations
        .first()
        .unwrap()
        .source_unit
        .as_ref()
        .unwrap();
    missing_provenance.evidence.remove(unit);
    assert!(missing_provenance.validate().is_err());

    // Without actual executing-unit context, the same PC cannot pick a stale source.
    if let TraceEvent::IndirectTargetObserved { source_unit, .. } = &mut t.events[4].data {
        *source_unit = None;
    }
    let legacy = import_trace(&t, &[], 100).unwrap();
    assert!(legacy.indirect_sites.iter().all(|s| s.observed.is_empty()));
    let old_json = legacy
        .to_json()
        .unwrap()
        .replace("\"source_unit\": null,", "");
    assert_eq!(legacy, ProgramMap::from_json(&old_json).unwrap());
}

#[test]
fn indirect_unit_context_must_already_be_completed_and_contain_site() {
    let mut t = trace(vec![0x01000008, 0]);
    let observed = |source_unit, site| EventRecord {
        seq: 3,
        data: TraceEvent::IndirectTargetObserved {
            site: GuestAddr(site),
            target: GuestAddr(0x80000020),
            delay_slot_pc: Some(GuestAddr(site + 4)),
            source_unit,
        },
    };
    t.events.push(observed(Some(0), 0x80000000));
    assert!(t.validate().is_ok());
    t.events[3] = observed(Some(1), 0x80000000);
    assert!(
        t.validate()
            .unwrap_err()
            .contains("unknown indirect source unit")
    );
    t.events[3] = observed(Some(0), 0x80000008);
    assert!(t.validate().unwrap_err().contains("outside source unit"));
    t.events.remove(2); // Unit exists but has not completed when the sensor runs.
    t.events[2] = observed(Some(0), 0x80000000);
    t.events[2].seq = 2;
    assert!(t.validate().unwrap_err().contains("not completed"));
}

#[test]
fn verified_old_entry_explains_only_pending_targets_before_invalidation() {
    let words = vec![0x01000008, 0];
    let mut t = trace(words.clone());
    let transfer = TraceEvent::IndirectTargetObserved {
        site: GuestAddr(0x80000000),
        target: GuestAddr(0x80000000),
        delay_slot_pc: Some(GuestAddr(0x80000004)),
        source_unit: Some(0),
    };
    let verification = TraceEvent::EntryBytesVerified {
        unit: 0,
        pc: GuestAddr(0x80000000),
        register_mask: 0,
        words: words.clone(),
    };
    for data in [
        TraceEvent::Invalidate { range: None },
        transfer.clone(),
        verification.clone(),
    ] {
        t.events.push(EventRecord {
            seq: t.events.len() as u64,
            data,
        });
    }
    let m = import_trace(&t, &[], 100).unwrap();
    let site = m.indirect_sites.first().unwrap();
    assert_eq!(site.observed.len(), 1);
    assert_eq!(site.observed.first_key_value().unwrap().0, &site.site);
    assert!(site.closed_proof.is_none());
    let checked = m.entry_verifications.first().unwrap();
    assert_eq!(checked.generation, 1);
    assert_eq!(checked.entry.generation, 0);
    assert!(
        checked
            .evidence
            .is_subset(site.observed.first_key_value().unwrap().1)
    );
    assert_eq!(m, ProgramMap::from_json(&m.to_json().unwrap()).unwrap());
    assert_eq!(m, merge_maps(&m, &m).unwrap());
    let mut bad_map = m.clone();
    bad_map.entries.clear();
    assert!(bad_map.validate().is_err());

    let mut missing = t.clone();
    missing.events.pop();
    assert!(
        import_trace(&missing, &[], 100)
            .unwrap()
            .indirect_sites
            .first()
            .unwrap()
            .observed
            .is_empty()
    );
    // Verification is not an execution event and cannot explain a later transfer.
    let mut before = t.clone();
    before.events[4].data = verification.clone();
    before.events[5].data = transfer.clone();
    let m = import_trace(&before, &[], 100).unwrap();
    assert_eq!(m.entry_verifications.len(), 1);
    assert!(m.indirect_sites.first().unwrap().observed.is_empty());
    let mut interrupted = t.clone();
    interrupted.events.insert(
        5,
        EventRecord {
            seq: 0,
            data: TraceEvent::Invalidate { range: None },
        },
    );
    for (seq, event) in interrupted.events.iter_mut().enumerate() {
        event.seq = seq as u64;
    }
    assert!(
        import_trace(&interrupted, &[], 100)
            .unwrap()
            .indirect_sites
            .first()
            .unwrap()
            .observed
            .is_empty()
    );

    // A competing current-epoch compilation at the same PC remains ambiguous.
    let mut ambiguous = t.clone();
    for data in [
        TraceEvent::CompileBegin {
            unit: 1,
            start: GuestAddr(0x80000000),
            physical_start: Some(PhysicalAddr(0)),
            delay_slot_entry: false,
        },
        TraceEvent::UnitCompiled {
            unit: 1,
            start: GuestAddr(0x80000000),
            words,
        },
    ] {
        ambiguous.events.push(EventRecord {
            seq: ambiguous.events.len() as u64,
            data,
        });
    }
    assert!(
        import_trace(&ambiguous, &[], 100)
            .unwrap()
            .indirect_sites
            .iter()
            .all(|s| s.observed.is_empty())
    );
}

#[test]
fn verified_entry_requires_exact_completed_words_and_installed_mask() {
    let mut t = trace(vec![0x01000008, 0]);
    let verified = |unit, pc, register_mask, words| TraceEvent::EntryBytesVerified {
        unit,
        pc: GuestAddr(pc),
        register_mask,
        words,
    };
    t.events.push(EventRecord {
        seq: 3,
        data: verified(0, 0x80000000, 0, vec![0x01000008, 0]),
    });
    assert_eq!(
        t,
        DiscoveryTrace::from_ndjson(&t.to_ndjson().unwrap()).unwrap()
    );
    for data in [
        verified(0, 0x80000000, 0, vec![0x01000008]),
        verified(0, 0x80000000, 0, vec![0x03e00008, 0]),
        verified(0, 0x80000004, 0, vec![0x01000008, 0]),
        verified(0, 0x80000000, 1, vec![0x01000008, 0]),
        verified(1, 0x80000000, 0, vec![0x01000008, 0]),
    ] {
        t.events[3].data = data;
        assert!(t.validate().is_err());
    }
    t.events.remove(2);
    t.events[2] = EventRecord {
        seq: 2,
        data: verified(0, 0x80000000, 0, vec![0x01000008, 0]),
    };
    assert!(t.validate().is_err());
}
