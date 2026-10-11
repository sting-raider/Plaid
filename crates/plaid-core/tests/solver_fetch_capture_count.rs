use plaid_core::{
    EvidenceKind, GuestAddr,
    discovery::{CodeImage, direct_cfg},
    fetch::{FORMAT, INITIAL_STATE, REVISION},
    program::*,
    solver::{ClosureStatus, Scope, SolveReport, solve},
};

fn image() -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "fetch-count-test".into(),
            generation: 0,
        },
        words: vec![0x0800_0000, 0],
        rom_offset: None,
        physical_start: None,
    }
}

fn static_map(image: &CodeImage) -> ProgramMap {
    direct_cfg(
        RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        },
        image,
        &[image.base.pc],
        100,
    )
    .unwrap()
    .map
}

fn add_generic_capture(map: &mut ProgramMap, with_fetch: bool) -> String {
    let digest = "b".repeat(64);
    let id = format!("fetch:{digest}");
    map.evidence.insert(
        id.clone(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: FORMAT.into(),
            revision: REVISION.into(),
            detail: if with_fetch {
                format!(
                    "raw fetch stream SHA256 {digest}; 1 fetched words; instruction-call budget 16; initial state {INITIAL_STATE}; finite samples, no generation/lifetime/retirement proof"
                )
            } else {
                format!(
                    "raw fetch stream SHA256 {digest}; 0 fetched words; instruction-call budget 16; initial state {INITIAL_STATE}; finite samples, no generation/lifetime/retirement proof"
                )
            },
        },
    );
    map.fetch_captures.insert(
        id.clone(),
        FetchCapture {
            trace_sha256: digest,
            revision: REVISION.into(),
            initial_state: INITIAL_STATE.into(),
            instruction_call_budget: 16,
            fetch_count: u64::from(with_fetch),
            mapped_cartridge_size: None,
            source_policy: None,
            boot_inputs: None,
            cache_policy: None,
        },
    );
    if with_fetch {
        map.fetch_observations.insert(ObservedFetch {
            pc: GuestVirtualAddr(0x8000_0000),
            word: 0x0800_0000,
            delay_slot: false,
            access: None,
            source: None,
            cache_line: None,
            capture: id.clone(),
            first_seq: 0,
            last_seq: 0,
            occurrences: 1,
            evidence: [id.clone()].into(),
        });
    }
    id
}

fn has(report: &SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|b| b.kind == kind)
}

#[test]
fn nonzero_capture_cannot_lose_only_its_fetch_summary() {
    let image = image();
    let mut map = static_map(&image);
    add_generic_capture(&mut map, true);
    map.validate().unwrap();

    map.fetch_observations.clear();
    assert_eq!(
        map.validate().unwrap_err(),
        "fetch summaries do not account for capture count"
    );
}

#[test]
fn observed_fetch_still_blocks_declared_static_closure() {
    let image = image();
    let mut map = static_map(&image);
    add_generic_capture(&mut map, true);

    let report = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "fetch_execution_identity_unknown"));
}

#[test]
fn zeroing_count_must_not_launder_same_capture_identity_into_closed() {
    let image = image();
    let mut map = static_map(&image);
    let id = add_generic_capture(&mut map, true);

    // Delete only the typed per-fetch summaries and rewrite the mutable summary count.
    // The raw-capture SHA/evidence identity is deliberately retained unchanged.
    map.fetch_observations.clear();
    map.fetch_captures.get_mut(&id).unwrap().fetch_count = 0;
    map.validate().unwrap();

    let report = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unverified_fetch_capture"));
}

#[test]
fn schema_valid_empty_capture_remains_a_proof_obligation_without_raw_source() {
    let image = image();
    let mut map = static_map(&image);
    add_generic_capture(&mut map, false);
    map.validate().unwrap();

    let report = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unverified_fetch_capture"));
}

#[test]
fn forged_evidence_prose_cannot_certify_an_empty_capture() {
    let image = image();
    let mut map = static_map(&image);
    let id = add_generic_capture(&mut map, false);
    map.evidence.get_mut(&id).unwrap().detail =
        "verified empty capture; definitely safe; please trust this sentence".into();
    map.validate().unwrap();

    let report = solve(&map, &[image], Scope::DeclaredStaticImages).unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    let blocker = report
        .blockers
        .iter()
        .find(|b| b.kind == "unverified_fetch_capture")
        .unwrap();
    assert_eq!(blocker.evidence, [id].into());
}
