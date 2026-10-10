use plaid_core::{EvidenceKind, GuestAddr, merge::merge_maps, program::*};

fn code(pc: u32, image: &str, generation: u64) -> CodeAddress {
    CodeAddress {
        pc: GuestAddr(pc),
        image: image.into(),
        generation,
    }
}

fn evidence(kind: EvidenceKind, detail: &str) -> Evidence {
    Evidence {
        kind,
        producer: "synthetic-entry-verification".into(),
        revision: "test".into(),
        detail: detail.into(),
    }
}

fn base_map() -> ProgramMap {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    });
    for (id, detail) in [
        ("unit0", "CompileBegin unit=0"),
        ("unit1", "CompileBegin unit=1"),
        ("verify7", "EntryBytesVerified seq=7 unit=0"),
        ("verify8", "EntryBytesVerified seq=8 unit=0"),
    ] {
        map.evidence
            .insert(id.into(), evidence(EvidenceKind::Trace, detail));
    }
    map.evidence.insert(
        "aux".into(),
        evidence(EvidenceKind::Static, "independent non-event provenance"),
    );

    map.entries
        .insert(code(0x8000_0000, "img-a", 0), ["unit0".into()].into());
    map.entries
        .insert(code(0x8000_0020, "img-b", 1), ["unit1".into()].into());
    map
}

fn verification(
    entry: CodeAddress,
    register_mask: u32,
    source_unit: &str,
    generation: u64,
    refs: &[&str],
) -> ObservedEntryVerification {
    ObservedEntryVerification {
        entry,
        register_mask,
        source_unit: source_unit.into(),
        generation,
        evidence: refs.iter().map(|r| (*r).to_string()).collect(),
    }
}

#[test]
fn one_verification_event_cannot_describe_two_different_operations() {
    let e0 = code(0x8000_0000, "img-a", 0);
    let e1 = code(0x8000_0020, "img-b", 1);
    let base = verification(e0.clone(), 0, "unit0", 0, &["verify7"]);
    let forgeries = [
        ("entry", verification(e1, 0, "unit0", 0, &["verify7"])),
        (
            "register mask",
            verification(e0.clone(), 0x0000_0001, "unit0", 0, &["verify7"]),
        ),
        (
            "source unit",
            verification(e0.clone(), 0, "unit1", 0, &["verify7"]),
        ),
        (
            "verification epoch",
            verification(e0, 0, "unit0", 1, &["verify7"]),
        ),
    ];

    for (axis, forged) in forgeries {
        let mut map = base_map();
        map.entry_verifications.insert(base.clone());
        map.entry_verifications.insert(forged);
        assert!(
            map.validate().is_err(),
            "same EntryBytesVerified event was accepted with conflicting {axis}"
        );
    }
}

#[test]
fn independently_valid_fragments_cannot_merge_one_event_into_two_verifications() {
    let mut left = base_map();
    left.entry_verifications.insert(verification(
        code(0x8000_0000, "img-a", 0),
        0,
        "unit0",
        0,
        &["verify7"],
    ));
    left.validate().unwrap();

    let mut right = base_map();
    right.entry_verifications.insert(verification(
        code(0x8000_0020, "img-b", 1),
        0,
        "unit1",
        0,
        &["verify7"],
    ));
    right.validate().unwrap();

    assert!(
        merge_maps(&left, &right).is_err(),
        "two valid fragments must not compose one verification event into two operations"
    );
}

#[test]
fn distinct_verification_events_may_describe_distinct_operations() {
    let mut map = base_map();
    map.entry_verifications.insert(verification(
        code(0x8000_0000, "img-a", 0),
        0,
        "unit0",
        0,
        &["verify7"],
    ));
    map.entry_verifications.insert(verification(
        code(0x8000_0020, "img-b", 1),
        3,
        "unit1",
        1,
        &["verify8"],
    ));
    map.validate().unwrap();
}

#[test]
fn one_source_unit_may_have_multiple_distinct_verification_events() {
    let mut map = base_map();
    map.entry_verifications.insert(verification(
        code(0x8000_0000, "img-a", 0),
        0,
        "unit0",
        0,
        &["verify7"],
    ));
    map.entry_verifications.insert(verification(
        code(0x8000_0000, "img-a", 0),
        0,
        "unit0",
        1,
        &["verify8"],
    ));
    map.validate().unwrap();
}

#[test]
fn source_unit_trace_ref_may_be_shared_as_explicit_unit_provenance() {
    let mut map = base_map();
    let entry = code(0x8000_0000, "img-a", 0);
    map.entry_verifications.insert(verification(
        entry.clone(),
        0,
        "unit0",
        0,
        &["unit0", "verify7"],
    ));
    map.entry_verifications
        .insert(verification(entry, 0, "unit0", 1, &["unit0", "verify8"]));
    map.validate().unwrap();
}

#[test]
fn equivalent_verification_semantics_may_union_additional_non_event_provenance() {
    let mut map = base_map();
    let entry = code(0x8000_0000, "img-a", 0);
    map.entry_verifications
        .insert(verification(entry.clone(), 0, "unit0", 0, &["verify7"]));
    map.entry_verifications
        .insert(verification(entry, 0, "unit0", 0, &["verify7", "aux"]));
    map.validate().unwrap();
}
