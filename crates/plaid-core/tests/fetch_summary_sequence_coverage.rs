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
            detail: "synthetic raw-fetch capture for sequence-coverage regression".into(),
        },
    );
    map.fetch_captures.insert(
        capture.clone(),
        FetchCapture {
            trace_sha256: TRACE_SHA.into(),
            revision: REVISION.into(),
            initial_state: INITIAL_STATE.into(),
            instruction_call_budget: 16,
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
fn rejects_missing_capture_sequence_even_when_occurrence_totals_match() {
    let (mut map, capture) = map_with_capture(6);

    // These summaries claim six occurrences, but every claimed occurrence is
    // constrained to sequence IDs 0..=4. Sequence 5 has no possible owner.
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0000, 0x1111_1111, 0, 4, 4));
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0004, 0x2222_2222, 1, 3, 2));

    let error = map
        .validate()
        .expect_err("an uncovered capture sequence must invalidate the summary set");
    assert_eq!(error, "fetch summaries leave unaccounted sequence position");
}

#[test]
fn accepts_interleaved_summaries_when_interval_union_covers_capture() {
    let (mut map, capture) = map_with_capture(6);

    // A, B, C, C, B, A is one concrete history satisfying these summaries.
    // Occurrences need not be contiguous, so interval overlap itself is valid.
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0000, 0x1111_1111, 0, 5, 2));
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0004, 0x2222_2222, 1, 4, 2));
    map.fetch_observations
        .insert(summary(&capture, 0x8000_0008, 0x3333_3333, 2, 3, 2));

    map.validate().unwrap();
}

#[test]
fn accepts_empty_capture_without_summaries() {
    let (map, _) = map_with_capture(0);
    map.validate().unwrap();
}
