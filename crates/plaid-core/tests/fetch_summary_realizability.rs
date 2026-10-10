use plaid_core::{
    EvidenceKind,
    fetch::{FORMAT, INITIAL_STATE, REVISION},
    program::{
        Evidence, EvidenceRefs, FetchCapture, GuestVirtualAddr, ObservedFetch, ProgramMap,
        RomIdentity,
    },
};

const TRACE_SHA: &str = "1111111111111111111111111111111111111111111111111111111111111111";

fn refs(id: &str) -> EvidenceRefs {
    [id.to_string()].into_iter().collect()
}

fn map_with_capture(fetch_count: u64) -> (ProgramMap, String) {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "2222222222222222222222222222222222222222222222222222222222222222".into(),
        size: 4096,
    });
    let capture = format!("fetch:{TRACE_SHA}");
    map.evidence.insert(
        capture.clone(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: FORMAT.into(),
            revision: REVISION.into(),
            detail: "synthetic raw-fetch capture for realizability regression".into(),
        },
    );
    map.fetch_captures.insert(
        capture.clone(),
        FetchCapture {
            trace_sha256: TRACE_SHA.into(),
            revision: REVISION.into(),
            initial_state: INITIAL_STATE.into(),
            instruction_call_budget: 32,
            fetch_count,
            mapped_cartridge_size: None,
            source_policy: None,
            boot_inputs: None,
            cache_policy: None,
        },
    );
    (map, capture)
}

fn summary(
    capture: &str,
    pc: u64,
    word: u32,
    first_seq: u64,
    last_seq: u64,
    occurrences: u64,
) -> ObservedFetch {
    ObservedFetch {
        pc: GuestVirtualAddr(pc),
        word,
        delay_slot: false,
        access: None,
        source: None,
        cache_line: None,
        capture: capture.into(),
        first_seq,
        last_seq,
        occurrences,
        evidence: refs(capture),
    }
}

#[test]
fn rejects_interval_covered_but_globally_impossible_summary_set() {
    let (mut map, capture) = map_with_capture(7);

    // Every sequence position lies in at least one summary interval and the
    // occurrence total is exactly seven. Still, A must occupy 0,1,2 in order
    // to occur three times between first=0 and last=2, while B requires its
    // first occurrence at sequence 1. No concrete seven-event history exists.
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0000, 0x1111_1111, 0, 2, 3));
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0004, 0x2222_2222, 1, 3, 2));
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0008, 0x3333_3333, 4, 6, 2));

    let error = map
        .validate()
        .expect_err("an impossible finite summary set must not validate");
    assert_eq!(error, "fetch summaries are not jointly realizable");
}

#[test]
fn accepts_concrete_interleaved_history_summary_set() {
    let (mut map, capture) = map_with_capture(7);

    // Concrete witness: A, B, B, A, C, C, C.
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0000, 0x1111_1111, 0, 3, 2));
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0004, 0x2222_2222, 1, 2, 2));
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0008, 0x3333_3333, 4, 6, 3));

    map.validate().unwrap();
}

#[test]
fn equal_payload_does_not_repair_endpoint_quota_collision() {
    let (mut map, capture) = map_with_capture(7);

    map.fetch_observations
        .insert(summary(&capture, 0x8000_0000, 0xdead_beef, 0, 2, 3));
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0004, 0xdead_beef, 1, 3, 2));
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0008, 0xdead_beef, 4, 6, 2));

    assert!(map.validate().is_err());
}

#[test]
fn accepts_empty_capture_without_summaries() {
    let (map, _) = map_with_capture(0);
    map.validate().unwrap();
}
