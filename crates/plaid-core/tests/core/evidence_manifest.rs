use plaid_core::{
    GuestAddr,
    evidence_manifest::{DiscoveryTraceManifest, DiscoveryTraceManifestSet},
    merge::import_trace,
    program::RomIdentity,
    trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
};
use std::collections::BTreeSet;

fn trace(revision: &str, destination_bias: u32) -> DiscoveryTrace {
    DiscoveryTrace {
        header: TraceHeader {
            schema_version: 0,
            rom: RomIdentity {
                sha256: "a".repeat(64),
                size: 4096,
            },
            engine: "manifest-test".into(),
            revision: revision.into(),
            capabilities: BTreeSet::new(),
        },
        events: vec![
            EventRecord {
                seq: 0,
                data: TraceEvent::CpuWordStoreObserved {
                    site: GuestAddr(0x8000_0000),
                    destination: GuestAddr(0x8000_0100 + destination_bias),
                    value: 0x1122_3344,
                },
            },
            EventRecord {
                seq: 1,
                data: TraceEvent::CpuWordStoreObserved {
                    site: GuestAddr(0x8000_0000),
                    destination: GuestAddr(0x8000_0104 + destination_bias),
                    value: 0x1122_3344,
                },
            },
        ],
    }
}

#[test]
fn manifest_uses_the_same_canonical_session_identity_as_import() {
    let trace = trace("r1", 0);
    let manifest = DiscoveryTraceManifest::from_trace(&trace).unwrap();
    let map = import_trace(&trace, &[], 64).unwrap();
    let prefix = format!("trace:{}:", manifest.source_sha256);

    assert_eq!(manifest.event_count, 2);
    assert!(map.evidence.keys().all(|id| id.starts_with(&prefix)));
    manifest.verify_trace(&trace).unwrap();
}

#[test]
fn external_manifest_rejects_same_count_semantic_substitution() {
    let original = trace("r1", 0);
    let expected = DiscoveryTraceManifest::from_trace(&original).unwrap();
    let mut edited = original.clone();
    let TraceEvent::CpuWordStoreObserved { destination, .. } = &mut edited.events[1].data else {
        unreachable!();
    };
    *destination = GuestAddr(0x8000_0204);

    edited.validate().unwrap();
    assert!(expected.verify_trace(&edited).is_err());
}

#[test]
fn external_manifest_rejects_equal_value_fresh_event_identity() {
    let original = trace("r1", 0);
    let expected = DiscoveryTraceManifest::from_trace(&original).unwrap();
    let mut edited = original.clone();
    edited.events.push(EventRecord {
        seq: 2,
        data: TraceEvent::CpuWordStoreObserved {
            site: GuestAddr(0x8000_0000),
            destination: GuestAddr(0x8000_0108),
            value: 0x1122_3344,
        },
    });

    edited.validate().unwrap();
    assert!(expected.verify_trace(&edited).is_err());
}

#[test]
fn exact_manifest_set_detects_whole_session_deletion() {
    let first = trace("r1", 0);
    let second = trace("r2", 0x100);
    let expected =
        DiscoveryTraceManifestSet::from_traces(&[first.clone(), second.clone()]).unwrap();

    expected
        .verify_traces(&[second.clone(), first.clone()])
        .unwrap();
    assert!(expected.verify_traces(&[first]).is_err());
    assert!(expected.verify_traces(&[second]).is_err());
}

#[test]
fn independent_manifest_sets_merge_by_source_identity_not_order() {
    let first = DiscoveryTraceManifestSet::from_traces(&[trace("r1", 0)]).unwrap();
    let second = DiscoveryTraceManifestSet::from_traces(&[trace("r2", 0x100)]).unwrap();

    let left = first.merge(&second).unwrap();
    let right = second.merge(&first).unwrap();
    assert_eq!(left, right);
    assert_eq!(left.sessions.len(), 2);
    assert_eq!(
        serde_json::to_string(&left).unwrap(),
        serde_json::to_string(&right).unwrap()
    );
}

#[test]
fn same_source_identity_with_conflicting_manifest_is_rejected() {
    let original = DiscoveryTraceManifestSet::from_traces(&[trace("r1", 0)]).unwrap();
    let mut conflicting = original.clone();
    conflicting.sessions.values_mut().next().unwrap().engine = "forged-producer".into();
    conflicting.validate().unwrap();

    assert!(original.merge(&conflicting).is_err());
}

#[test]
fn expected_manifest_plus_complete_source_recheck_catches_primitive_deletion() {
    let trace = trace("r1", 0);
    let expected = DiscoveryTraceManifestSet::from_traces(std::slice::from_ref(&trace)).unwrap();
    let mut map = import_trace(&trace, &[], 64).unwrap();

    expected
        .verify_primitive_projections(&map, std::slice::from_ref(&trace))
        .unwrap();
    map.word_store_observations.clear();
    map.validate().unwrap();
    assert!(
        expected
            .verify_primitive_projections(&map, std::slice::from_ref(&trace))
            .is_err()
    );
}

#[test]
fn an_unexpected_map_session_cannot_hide_beside_expected_sources() {
    let expected_trace = trace("expected", 0);
    let unexpected_trace = trace("unexpected", 0x100);
    let expected =
        DiscoveryTraceManifestSet::from_traces(std::slice::from_ref(&expected_trace)).unwrap();
    let expected_map = import_trace(&expected_trace, &[], 64).unwrap();
    let unexpected_map = import_trace(&unexpected_trace, &[], 64).unwrap();
    let merged = plaid_core::merge::merge_maps(&expected_map, &unexpected_map).unwrap();
    assert!(
        expected
            .verify_primitive_projections(&merged, std::slice::from_ref(&expected_trace))
            .is_err()
    );
    let second =
        DiscoveryTraceManifestSet::from_traces(std::slice::from_ref(&unexpected_trace)).unwrap();
    expected
        .merge(&second)
        .unwrap()
        .verify_primitive_projections(&merged, &[unexpected_trace, expected_trace])
        .unwrap();
}

#[test]
fn repeated_session_keys_cannot_erase_an_earlier_manifest_conflict() {
    let original = DiscoveryTraceManifest::from_trace(&trace("r1", 0)).unwrap();
    let mut conflict = original.clone();
    conflict.engine = "conflicting producer".into();
    let wire = format!(
        "{{\"format\":\"{}\",\"sessions\":{{\"{}\":{},\"{}\":{}}}}}",
        plaid_core::evidence_manifest::DISCOVERY_TRACE_MANIFEST_SET_FORMAT,
        original.source_sha256,
        serde_json::to_string(&conflict).unwrap(),
        original.source_sha256,
        serde_json::to_string(&original).unwrap(),
    );
    assert!(serde_json::from_str::<DiscoveryTraceManifestSet>(&wire).is_err());
}
