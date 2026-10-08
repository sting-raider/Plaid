use plaid_core::{
    fetch::{
        FORMAT, PHYSICAL_FORMAT, REVISION, SOURCE_FORMAT, SOURCE_POLICY, import_fetch,
        verify_fetch_capture,
    },
    merge::merge_maps,
    program::*,
    rom::{CanonicalRom, sha256},
    solver::{ClosureStatus, Scope, solve},
};
use std::io::Cursor;

fn rom() -> CanonicalRom {
    let mut bytes = vec![0; 4096];
    bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    bytes[64..68].copy_from_slice(&0x08000000u32.to_be_bytes());
    CanonicalRom::from_bytes(&bytes).unwrap()
}
fn raw(events: &[(u64, u32, bool)]) -> String {
    let mut out = format!(
        "{{\"record\":\"header\",\"format\":\"{FORMAT}\",\"revision\":\"{REVISION}\",\"rom_sha256\":\"{}\",\"budget\":10,\"initial_state\":\"declared_post_ipl2_sp_entry\"}}\n",
        rom().identity.sha256
    );
    for (seq, (pc, word, slot)) in events.iter().enumerate() {
        out += &format!(
            "{{\"record\":\"fetch\",\"seq\":{seq},\"pc\":{pc},\"word\":{word},\"delay_slot\":{slot}}}\n"
        );
    }
    out += &format!(
        "{{\"record\":\"end\",\"fetch_count\":{},\"reason\":\"instruction_call_budget\"}}\n",
        events.len()
    );
    out
}
fn import(input: &str) -> Result<ProgramMap, String> {
    import_fetch(Cursor::new(input.as_bytes()), &rom())
}

fn physical_raw(events: &[(u32, bool)]) -> String {
    let input = raw(&vec![(0x4000, 0, false); events.len()]);
    input
        .lines()
        .enumerate()
        .map(|(index, line)| {
            let mut event: serde_json::Value = serde_json::from_str(line).unwrap();
            if index == 0 {
                event["format"] = PHYSICAL_FORMAT.into();
                event["mapped_cartridge_size"] = 4096.into();
            } else if index <= events.len() {
                event["physical"] = events[index - 1].0.into();
                event["cached"] = events[index - 1].1.into();
            }
            event.to_string() + "\n"
        })
        .collect()
}

fn source_raw(sources: &[FetchSource]) -> String {
    physical_raw(&vec![(0x10000044, false); sources.len()])
        .lines()
        .enumerate()
        .map(|(index, line)| {
            let mut event: serde_json::Value = serde_json::from_str(line).unwrap();
            if index == 0 {
                event["format"] = SOURCE_FORMAT.into();
                event["source_policy"] = SOURCE_POLICY.into();
            } else if index <= sources.len() {
                event["source"] = serde_json::to_value(sources[index - 1]).unwrap();
            }
            event.to_string() + "\n"
        })
        .collect()
}

#[test]
fn source_witnesses_keep_unknowns_and_canonical_bytes_without_image_identity() {
    let known = FetchSource::CartridgeRom {
        offset: RomOffset(68),
    };
    let input = source_raw(&[known, FetchSource::Unknown {}, known]);
    let map = import(&input).unwrap();
    assert_eq!(map.fetch_observations.len(), 2);
    let witness = map
        .fetch_observations
        .iter()
        .find(|f| f.source == Some(known))
        .unwrap();
    assert_eq!(
        (witness.first_seq, witness.last_seq, witness.occurrences),
        (0, 2, 2)
    );
    assert_eq!(
        map.fetch_captures
            .values()
            .next()
            .unwrap()
            .source_policy
            .as_deref(),
        Some(SOURCE_POLICY)
    );
    assert!(map.regions.is_empty() && map.loads.is_empty() && map.entries.is_empty());
    verify_fetch_capture(&map, Cursor::new(input.as_bytes()), &rom()).unwrap();
    assert_eq!(map, ProgramMap::from_json(&map.to_json().unwrap()).unwrap());
    let old = import(&physical_raw(&[(0x10000044, false)])).unwrap();
    assert!(!old.to_json().unwrap().contains("source_policy"));
    assert!(!old.to_json().unwrap().contains("\"source\""));
    let merged = merge_maps(&map, &old).unwrap();
    assert_eq!(merged.fetch_observations.len(), 3);
    assert_eq!(merged, merge_maps(&old, &map).unwrap());
    assert_eq!(merged, merge_maps(&merged, &map).unwrap());
    let all_known = import(&source_raw(&[known])).unwrap();
    let report = solve(&all_known, &[], Scope::WholeRom).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(!report.native_complete);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "fetch_execution_identity_unknown")
    );
    let mut changed = all_known;
    let mut fact = changed.fetch_observations.pop_first().unwrap();
    fact.source = Some(FetchSource::Unknown {});
    changed.fetch_observations.insert(fact);
    changed.validate().unwrap();
    assert!(verify_fetch_capture(&changed, Cursor::new(source_raw(&[known])), &rom()).is_err());
}

#[test]
fn source_claims_reject_forged_bytes_access_capacity_and_version_fields() {
    let input = source_raw(&[FetchSource::CartridgeRom {
        offset: RomOffset(68),
    }]);
    for bad in [
        input.replace(SOURCE_FORMAT, PHYSICAL_FORMAT),
        input.replace(SOURCE_POLICY, "physical_range_guess"),
        input.replace(&format!(",\"source_policy\":\"{SOURCE_POLICY}\""), ""),
        input.replace("\"source\":{\"kind\":\"cartridge_rom\",\"offset\":68},", ""),
        input.replace("\"offset\":68", "\"offset\":69"),
        input.replace("\"offset\":68", "\"offset\":4096"),
        input.replace("\"offset\":68", "\"offset\":18446744073709551615"),
        input.replace("\"physical\":268435524", "\"physical\":268435528"),
        input.replace("\"cached\":false", "\"cached\":true"),
        input.replace("\"word\":0", "\"word\":1"),
        input.replace("cartridge_rom", "unrecognized"),
        input.replace("{\"kind\":\"cartridge_rom\",\"offset\":68}", "null"),
    ] {
        assert_ne!(bad, input, "mutation did not change input");
        assert!(import(&bad).is_err(), "accepted {bad}");
    }
    let unknown = source_raw(&[FetchSource::Unknown {}]);
    assert!(
        import(&unknown.replace(
            "{\"kind\":\"unknown\"}",
            "{\"kind\":\"unknown\",\"offset\":68}"
        ))
        .is_err()
    );
    let old = physical_raw(&[(0x10000044, false)]);
    assert!(
        import(&old.replace("\"seq\":0", "\"seq\":0,\"source\":{\"kind\":\"unknown\"}")).is_err()
    );
    let map = import(&input).unwrap();
    for source in [
        None,
        Some(FetchSource::CartridgeRom {
            offset: RomOffset(u64::MAX),
        }),
    ] {
        let mut invalid = map.clone();
        let mut fact = invalid.fetch_observations.pop_first().unwrap();
        fact.source = source;
        invalid.fetch_observations.insert(fact);
        assert!(invalid.validate().is_err());
    }
}

#[test]
fn physical_fetches_preserve_remappings_and_cache_variants_without_source_claims() {
    let input = physical_raw(&[
        (0x2000, false),
        (0x3000, false),
        (0x2000, true),
        (0x2000, false),
    ]);
    let map = import(&input).unwrap();
    assert_eq!(map.fetch_observations.len(), 3);
    assert_eq!(
        map.fetch_captures
            .values()
            .next()
            .unwrap()
            .mapped_cartridge_size,
        Some(4096)
    );
    let repeated = map
        .fetch_observations
        .iter()
        .find(|f| {
            f.access
                == Some(FetchAccess {
                    physical: PhysicalAddr(0x2000),
                    cached: false,
                })
        })
        .unwrap();
    assert_eq!(
        (repeated.first_seq, repeated.last_seq, repeated.occurrences),
        (0, 3, 2)
    );
    assert!(map.regions.is_empty() && map.loads.is_empty() && map.entries.is_empty());
    verify_fetch_capture(&map, Cursor::new(input.as_bytes()), &rom()).unwrap();
    assert_eq!(map, ProgramMap::from_json(&map.to_json().unwrap()).unwrap());
    let legacy = import(&raw(&[(0x4000, 0, false)])).unwrap();
    let old_json = legacy.to_json().unwrap();
    assert!(!old_json.contains("mapped_cartridge_size") && !old_json.contains("\"access\""));
    let merged = merge_maps(&map, &legacy).unwrap();
    assert_eq!(merged.fetch_observations.len(), 4);
    assert_eq!(merged, merge_maps(&legacy, &map).unwrap());
    assert_eq!(merged, merge_maps(&merged, &map).unwrap());
    verify_fetch_capture(&merged, Cursor::new(input.as_bytes()), &rom()).unwrap();
    let mut altered = map.clone();
    let mut fact = altered.fetch_observations.pop_first().unwrap();
    fact.access.as_mut().unwrap().physical = PhysicalAddr(0x4000);
    altered.fetch_observations.insert(fact);
    altered.validate().unwrap();
    assert!(verify_fetch_capture(&altered, Cursor::new(input.as_bytes()), &rom()).is_err());
    let report = solve(&map, &[], Scope::WholeRom).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(!report.native_complete);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "fetch_execution_identity_unknown")
    );
}

#[test]
fn physical_wire_and_map_metadata_are_versioned_and_fail_closed() {
    let input = physical_raw(&[(0x2000, false)]);
    for bad in [
        input.replace(PHYSICAL_FORMAT, FORMAT),
        input.replace("\"physical\":8192,", ""),
        input.replace("\"cached\":false,", ""),
        input.replace("\"physical\":8192", "\"physical\":8193"),
        input.replace("\"physical\":8192", "\"physical\":4294967296"),
        input.replace("\"cached\":false", "\"cached\":0"),
        input.replace("\"physical\":8192", "\"physical\":null"),
        input.replace("\"mapped_cartridge_size\":4096,", ""),
        input.replace(
            "\"mapped_cartridge_size\":4096",
            "\"mapped_cartridge_size\":4088",
        ),
        input.replace(
            "\"mapped_cartridge_size\":4096",
            "\"mapped_cartridge_size\":null",
        ),
    ] {
        assert!(import(&bad).is_err(), "accepted {bad}");
    }
    let legacy = raw(&[(0x4000, 0, false)]);
    for field in [
        "\"physical\":null,",
        "\"physical\":8192,",
        "\"cached\":false,",
    ] {
        assert!(import(&legacy.replace("\"seq\":0,", &format!("\"seq\":0,{field}"))).is_err());
    }
    let map = import(&input).unwrap();
    for access in [
        None,
        Some(FetchAccess {
            physical: PhysicalAddr(1),
            cached: false,
        }),
    ] {
        let mut invalid = map.clone();
        let mut fact = invalid.fetch_observations.pop_first().unwrap();
        fact.access = access;
        invalid.fetch_observations.insert(fact);
        assert!(invalid.validate().is_err());
    }
    let mut invalid = map;
    invalid
        .fetch_captures
        .values_mut()
        .next()
        .unwrap()
        .mapped_cartridge_size = Some(4088);
    assert!(invalid.validate().is_err());
}

#[test]
fn raw_fetches_keep_wide_pcs_word_variants_slots_and_digest_provenance() {
    let pc = 0x9000_0000_0000_1000;
    let input = raw(&[
        (pc, 0, false),
        (pc, 0, true),
        (pc, 1, false),
        (pc, 0, false),
    ]);
    let map = import(&input).unwrap();
    assert_eq!(map.fetch_observations.len(), 3);
    let id = format!("fetch:{}", sha256(input.as_bytes()));
    let capture = &map.fetch_captures[&id];
    assert_eq!(capture.fetch_count, 4);
    assert_eq!(capture.trace_sha256, sha256(input.as_bytes()));
    let repeated = map
        .fetch_observations
        .iter()
        .find(|f| f.word == 0 && !f.delay_slot)
        .unwrap();
    assert_eq!(repeated.pc, GuestVirtualAddr(pc));
    assert_eq!(
        (repeated.first_seq, repeated.last_seq, repeated.occurrences),
        (0, 3, 2)
    );
    assert!(repeated.evidence.contains(&id));
    assert!(map.regions.is_empty() && map.blocks.is_empty() && map.loads.is_empty());
    assert!(map.indirect_sites.is_empty() && map.entries.is_empty());
    assert_eq!(map, ProgramMap::from_json(&map.to_json().unwrap()).unwrap());
    verify_fetch_capture(&map, Cursor::new(input.as_bytes()), &rom()).unwrap();
    assert_eq!(
        map.to_json().unwrap(),
        merge_maps(&map, &map).unwrap().to_json().unwrap()
    );
}

#[test]
fn fetch_summary_verifier_detects_changed_bytes_counts_and_missing_facts() {
    let input = raw(&[
        (0xffff_ffff_b000_1000, 0, false),
        (0xffff_ffff_b000_1004, 1, true),
    ]);
    let map = import(&input).unwrap();
    let mut changed = map.clone();
    let mut fact = changed.fetch_observations.pop_first().unwrap();
    fact.word ^= 1;
    changed.fetch_observations.insert(fact);
    changed.validate().unwrap();
    assert!(verify_fetch_capture(&changed, Cursor::new(input.as_bytes()), &rom()).is_err());
    let mut missing = map.clone();
    missing.fetch_observations.pop_first();
    assert!(missing.validate().is_err());
    assert!(
        verify_fetch_capture(
            &map,
            Cursor::new(input.replace("\"word\":1", "\"word\":2")),
            &rom()
        )
        .is_err()
    );
    let mut invalid = map.clone();
    let mut fact = invalid.fetch_observations.pop_first().unwrap();
    fact.last_seq = 2;
    invalid.fetch_observations.insert(fact);
    assert!(invalid.validate().is_err());
}

#[test]
fn malformed_or_incomplete_fetch_streams_fail_closed() {
    let input = raw(&[(0xffff_ffff_8000_0000, 0, false)]);
    for bad in [
        input.lines().take(2).collect::<Vec<_>>().join("\n"),
        input.clone() + "{}\n",
        input.replace("\"seq\":0", "\"seq\":1"),
        input.replace("\"fetch_count\":1", "\"fetch_count\":0"),
        input.replace("\"word\":0", "\"word\":4294967296"),
        input.replace("18446744071562067968", "18446744071562067969"),
        input.replace(
            "\"delay_slot\":false",
            "\"delay_slot\":false,\"unexpected\":1",
        ),
        input.replace("\"seq\":0", "\"seq\":0,\"seq\":0"),
        input.replace("\"budget\":10", "\"budget\":0"),
        input.replace("instruction_call_budget", "guest_complete"),
        input.replace(REVISION, &"b".repeat(40)),
        input.replace(&rom().identity.sha256, &"a".repeat(64)),
    ] {
        assert!(import(&bad).is_err(), "accepted {bad}");
    }
    assert!(import(&" ".repeat(1024 * 1024 + 1)).is_err());
    assert!(import(&raw(&[])).is_ok());
}

#[test]
fn distinct_captures_merge_without_summing_or_collapsing_observations() {
    let a = import(&raw(&[(0xffff_ffff_8000_0000, 0, false)])).unwrap();
    let b = import(&raw(&[(0xffff_ffff_8000_0000, 1, false)])).unwrap();
    let merged = merge_maps(&a, &b).unwrap();
    assert_eq!(merged.fetch_captures.len(), 2);
    assert_eq!(merged.fetch_observations.len(), 2);
    assert_eq!(merged, merge_maps(&b, &a).unwrap());
    assert_eq!(merged, merge_maps(&merged, &a).unwrap());
    let source = rom();
    let image = plaid_core::discovery::CodeImage::from_rom(
        &source,
        RomOffset(64),
        GuestRange {
            start: plaid_core::GuestAddr(0x80000000),
            size: 8,
        },
    )
    .unwrap();
    let static_map =
        plaid_core::discovery::direct_cfg(source.identity, &image, &[image.base.pc], 20)
            .unwrap()
            .map;
    assert_eq!(
        solve(
            &static_map,
            std::slice::from_ref(&image),
            Scope::DeclaredStaticImages
        )
        .unwrap()
        .status,
        ClosureStatus::Closed
    );
    let mut no_diagnostic = merge_maps(&static_map, &merged).unwrap();
    no_diagnostic.unresolved.clear();
    let report = solve(&no_diagnostic, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "fetch_execution_identity_unknown")
    );
    assert!(!report.native_complete);
}

#[test]
fn summary_endpoints_and_legacy_defaults_are_structurally_checked() {
    let map = import(&raw(&[
        (0xffff_ffff_8000_0000, 0, false),
        (0xffff_ffff_8000_0004, 1, false),
    ]))
    .unwrap();
    let mut conflicting = map.clone();
    let mut fact = conflicting.fetch_observations.pop_last().unwrap();
    fact.first_seq = 0;
    fact.last_seq = 0;
    conflicting.fetch_observations.insert(fact);
    assert!(conflicting.validate().is_err());
    let mut impossible = map.clone();
    let mut fact = impossible.fetch_observations.pop_first().unwrap();
    fact.last_seq = 1;
    impossible.fetch_observations.insert(fact);
    assert!(impossible.validate().is_err());
    let empty = ProgramMap::new(rom().identity);
    let mut legacy: serde_json::Value = serde_json::from_str(&empty.to_json().unwrap()).unwrap();
    legacy.as_object_mut().unwrap().remove("fetch_captures");
    legacy.as_object_mut().unwrap().remove("fetch_observations");
    assert_eq!(empty, ProgramMap::from_json(&legacy.to_string()).unwrap());
}
