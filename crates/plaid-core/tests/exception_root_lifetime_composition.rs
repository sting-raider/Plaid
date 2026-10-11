use plaid_core::{
    exception_root_generation::{
        ExceptionRootGenerationReport, FORMAT, LINE_FORMAT, LINE_POLICY, POLICY, RootWordOrigin,
        inspect_exception_root_generation_history, verify_exception_root_generation_report,
    },
    reset_cache_lifetime::PROFILE,
    rom::sha256,
};
use serde_json::{Value, json};

fn write(ordinal: u64, physical: u32, word: u32) -> Value {
    json!({"kind":"backing_write","ordinal":ordinal,"physical":physical,"word":word})
}
fn fill(ordinal: u64, physical_line: u32, word: u32) -> Value {
    json!({"kind":"fill_line","ordinal":ordinal,"physical_line":physical_line,"words":[word,0,0,0,0,0,0,0]})
}
fn root(ordinal: u64, word: u32) -> Value {
    json!({"kind":"root_fetch","ordinal":ordinal,"physical":0x180,"word":word,
        "input":{"class":"general","bev":false,"exl":false,"kernel_mode":"bits32"}})
}
fn transition(ordinal: u64, kind: &str, resident: bool, backing: bool) -> Value {
    json!({"kind":"lifecycle","ordinal":ordinal,"transition":kind,
        "resident_reinitialized":resident,"backing_reinitialized":backing})
}
fn source(events: Vec<Value>) -> Vec<u8> {
    serde_json::to_vec(
        &json!({"format":LINE_FORMAT,"policy":LINE_POLICY,"profile":PROFILE,"events":events}),
    )
    .unwrap()
}
fn inspect(events: Vec<Value>) -> ExceptionRootGenerationReport {
    let bytes = source(events);
    let report = inspect_exception_root_generation_history(&bytes, &sha256(&bytes)).unwrap();
    verify_exception_root_generation_report(&report, &bytes, &sha256(&bytes)).unwrap();
    assert!(
        !report.reachability_certified
            && !report.mutation_coverage_certified
            && !report.executable_lifetime_certified
            && !report.native_complete
    );
    report
}

#[test]
fn equal_value_conflicting_line_ends_residency_and_later_fill_uses_current_writer() {
    let report = inspect(vec![
        write(1, 0x180, 7),
        fill(2, 0x180, 7),
        write(3, 0x180, 7),
        write(4, 0x4180, 7),
        fill(5, 0x4180, 7),
        root(6, 7),
        fill(7, 0x180, 7),
        root(8, 7),
    ]);
    assert_eq!(report.witnesses[0].origin, RootWordOrigin::Unknown);
    assert_eq!(
        report.witnesses[0].current_backing.unwrap().write_ordinal,
        3
    );
    assert_eq!(
        report.witnesses[1].origin,
        RootWordOrigin::Resident {
            fill_ordinal: 7,
            backing_write_ordinal: 3
        }
    );
}

#[test]
fn nonconflicting_fill_preserves_root_and_index_invalidation_ends_the_whole_slot() {
    let report = inspect(vec![
        write(1, 0x180, 7),
        fill(2, 0x180, 7),
        write(3, 0x2180, 7),
        fill(4, 0x2180, 7),
        root(5, 7),
        json!({"kind":"index_invalidate","ordinal":6,"physical_line":0x4180}),
        root(7, 7),
    ]);
    assert_eq!(
        report.witnesses[0].origin,
        RootWordOrigin::Resident {
            fill_ordinal: 2,
            backing_write_ordinal: 1
        }
    );
    assert_eq!(report.witnesses[1].origin, RootWordOrigin::Unknown);
}

#[test]
fn nmi_reset_and_full_power_compose_distinct_resident_and_backing_lifetimes() {
    let report = inspect(vec![
        write(1, 0x180, 1),
        fill(2, 0x180, 1),
        write(3, 0x180, 2),
        transition(4, "nmi", false, false),
        root(5, 1),
        transition(6, "system_reset", true, false),
        root(7, 2),
        fill(8, 0x180, 2),
        root(9, 2),
        transition(10, "full_power", true, true),
        root(11, 2),
        fill(12, 0x180, 2),
        root(13, 2),
        write(14, 0x180, 2),
        root(15, 2),
        fill(16, 0x180, 2),
        root(17, 2),
    ]);
    assert_eq!(
        report.witnesses[0].origin,
        RootWordOrigin::Resident {
            fill_ordinal: 2,
            backing_write_ordinal: 1
        }
    );
    assert_eq!(
        report.witnesses[0].current_backing.unwrap().write_ordinal,
        3
    );
    assert_eq!(report.witnesses[1].origin, RootWordOrigin::Unknown);
    assert_eq!(
        report.witnesses[1].current_backing.unwrap().write_ordinal,
        3
    );
    assert_eq!(
        report.witnesses[2].origin,
        RootWordOrigin::Resident {
            fill_ordinal: 8,
            backing_write_ordinal: 3
        }
    );
    assert!(report.witnesses[3].current_backing.is_none());
    for witness in &report.witnesses[3..6] {
        assert_eq!(witness.origin, RootWordOrigin::Unknown);
    }
    assert_eq!(
        report.witnesses[6].origin,
        RootWordOrigin::Resident {
            fill_ordinal: 16,
            backing_write_ordinal: 14
        }
    );
}

#[test]
fn other_lane_writer_cannot_supply_root_ancestry_and_every_captured_lane_is_checked() {
    let report = inspect(vec![
        write(1, 0x184, 0),
        fill(2, 0x180, 7),
        root(3, 7),
        write(4, 0x180, 7),
        root(5, 7),
    ]);
    assert_eq!(report.witnesses[0].origin, RootWordOrigin::Unknown);
    assert_eq!(report.witnesses[1].origin, RootWordOrigin::Unknown);
    let bytes = source(vec![write(1, 0x184, 99), fill(2, 0x180, 7), root(3, 7)]);
    assert!(
        inspect_exception_root_generation_history(&bytes, &sha256(&bytes))
            .unwrap_err()
            .contains("line fill payload")
    );
}

#[test]
fn same_line_refill_replaces_all_lanes_even_when_root_payload_is_equal() {
    let report = inspect(vec![
        write(1, 0x180, 7),
        fill(2, 0x180, 7),
        write(3, 0x180, 7),
        fill(4, 0x180, 7),
        root(5, 7),
    ]);
    assert_eq!(
        report.witnesses[0].origin,
        RootWordOrigin::Resident {
            fill_ordinal: 4,
            backing_write_ordinal: 3
        }
    );
}

#[test]
fn legacy_and_full_line_profiles_cannot_silently_mix_operations() {
    let legacy = json!({"format":FORMAT,"policy":POLICY,"events":[write(1,0x180,7),
        {"kind":"fill","ordinal":2,"physical":0x180,"word":7},root(3,7)]});
    let bytes = serde_json::to_vec(&legacy).unwrap();
    let report = inspect_exception_root_generation_history(&bytes, &sha256(&bytes)).unwrap();
    assert!(report.profile.is_none());
    assert!(
        serde_json::to_value(report)
            .unwrap()
            .get("profile")
            .is_none()
    );
    let mut v0_other_line = legacy.clone();
    v0_other_line["events"][0]["physical"] = json!(0x4180);
    let mut v0_line_fill = legacy.clone();
    v0_line_fill["events"][1] = fill(2, 0x180, 7);
    let mut v1_word_fill = legacy.clone();
    v1_word_fill["format"] = json!(LINE_FORMAT);
    v1_word_fill["policy"] = json!(LINE_POLICY);
    v1_word_fill["profile"] = json!(PROFILE);
    let mut missing_profile = v1_word_fill.clone();
    missing_profile.as_object_mut().unwrap().remove("profile");
    for invalid in [v0_other_line, v0_line_fill, v1_word_fill, missing_profile] {
        let bytes = serde_json::to_vec(&invalid).unwrap();
        assert!(inspect_exception_root_generation_history(&bytes, &sha256(&bytes)).is_err());
    }
}

#[test]
fn unsupported_line_mapping_restore_scope_and_forged_lifecycle_effects_reject() {
    let invalids = vec![
        fill(1, 0x184, 7),
        fill(1, 0x800000, 7),
        write(1, 0x181, 7),
        transition(1, "nmi", true, false),
        transition(1, "system_reset", true, true),
        transition(1, "full_power", true, false),
        transition(1, "restore", true, true),
    ];
    for event in invalids {
        let bytes = source(vec![event]);
        assert!(inspect_exception_root_generation_history(&bytes, &sha256(&bytes)).is_err());
    }
    let mut outside = root(1, 7);
    outside["input"]["bev"] = json!(true);
    let bytes = source(vec![outside]);
    assert!(inspect_exception_root_generation_history(&bytes, &sha256(&bytes)).is_err());
}

#[test]
fn complete_source_and_report_bind_replacement_and_lifetime_effects() {
    let bytes = source(vec![
        write(1, 0x180, 7),
        fill(2, 0x180, 7),
        transition(3, "system_reset", true, false),
        root(4, 7),
    ]);
    let digest = sha256(&bytes);
    let mut report = inspect_exception_root_generation_history(&bytes, &digest).unwrap();
    report.witnesses[0].origin = RootWordOrigin::Resident {
        fill_ordinal: 2,
        backing_write_ordinal: 1,
    };
    assert!(verify_exception_root_generation_report(&report, &bytes, &digest).is_err());
    let edited = source(vec![write(1, 0x180, 7), fill(2, 0x180, 7), root(3, 7)]);
    assert!(inspect_exception_root_generation_history(&edited, &digest).is_err());
    let forged = source(vec![write(1, 0x180, 7), fill(2, 0x180, 7), root(4, 7)]);
    assert!(inspect_exception_root_generation_history(&forged, &sha256(&forged)).is_err());
}
