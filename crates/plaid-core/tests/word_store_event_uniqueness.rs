use plaid_core::{EvidenceKind, GuestAddr, program::*};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn trace_evidence(detail: &str) -> Evidence {
    Evidence {
        kind: EvidenceKind::Trace,
        producer: "synthetic-store-sensor".into(),
        revision: "test".into(),
        detail: detail.into(),
    }
}

fn store(
    site: u32,
    destination: u32,
    value: u32,
    generation: u64,
    evidence: &[&str],
) -> ObservedWordStore {
    ObservedWordStore {
        site: GuestAddr(site),
        destination: GuestAddr(destination),
        value,
        generation,
        evidence: evidence.iter().map(|s| (*s).to_string()).collect(),
    }
}

fn base_map() -> ProgramMap {
    let mut map = ProgramMap::new(rom());
    map.evidence.insert(
        "trace:session:7".into(),
        trace_evidence("CpuWordStoreObserved seq=7"),
    );
    map.evidence.insert(
        "trace:session:8".into(),
        trace_evidence("CpuWordStoreObserved seq=8"),
    );
    map.evidence.insert(
        "shared-static".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "fixture".into(),
            revision: "test".into(),
            detail: "shared non-event provenance".into(),
        },
    );
    map
}

#[test]
fn one_trace_store_event_cannot_describe_two_different_operations() {
    let cases = [
        (
            "site",
            store(0x8000_0000, 0x8000_1000, 0x1122_3344, 3, &["trace:session:7"]),
            store(0x8000_0004, 0x8000_1000, 0x1122_3344, 3, &["trace:session:7"]),
        ),
        (
            "destination",
            store(0x8000_0000, 0x8000_1000, 0x1122_3344, 3, &["trace:session:7"]),
            store(0x8000_0000, 0x8000_1004, 0x1122_3344, 3, &["trace:session:7"]),
        ),
        (
            "value",
            store(0x8000_0000, 0x8000_1000, 0x1122_3344, 3, &["trace:session:7"]),
            store(0x8000_0000, 0x8000_1000, 0x5566_7788, 3, &["trace:session:7"]),
        ),
        (
            "generation",
            store(0x8000_0000, 0x8000_1000, 0x1122_3344, 3, &["trace:session:7"]),
            store(0x8000_0000, 0x8000_1000, 0x1122_3344, 4, &["trace:session:7"]),
        ),
    ];

    for (axis, first, forged) in cases {
        let mut map = base_map();
        map.word_store_observations.insert(first);
        map.word_store_observations.insert(forged);
        assert!(
            map.validate().is_err(),
            "same trace event was accepted with conflicting {axis}"
        );
    }
}

#[test]
fn distinct_trace_events_may_describe_distinct_stores() {
    let mut map = base_map();
    map.word_store_observations.insert(store(
        0x8000_0000,
        0x8000_1000,
        0x1122_3344,
        3,
        &["trace:session:7"],
    ));
    map.word_store_observations.insert(store(
        0x8000_0004,
        0x8000_1004,
        0x5566_7788,
        3,
        &["trace:session:8"],
    ));
    map.validate().unwrap();
}

#[test]
fn equivalent_store_facts_may_union_additional_provenance() {
    let mut map = base_map();
    map.word_store_observations.insert(store(
        0x8000_0000,
        0x8000_1000,
        0x1122_3344,
        3,
        &["trace:session:7"],
    ));
    map.word_store_observations.insert(store(
        0x8000_0000,
        0x8000_1000,
        0x1122_3344,
        3,
        &["trace:session:7", "shared-static"],
    ));
    map.validate().unwrap();
}

#[test]
fn shared_non_trace_evidence_does_not_create_event_identity() {
    let mut map = base_map();
    map.word_store_observations.insert(store(
        0x8000_0000,
        0x8000_1000,
        0x1122_3344,
        3,
        &["shared-static"],
    ));
    map.word_store_observations.insert(store(
        0x8000_0004,
        0x8000_1004,
        0x5566_7788,
        3,
        &["shared-static"],
    ));
    map.validate().unwrap();
}
