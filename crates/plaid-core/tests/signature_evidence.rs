use plaid_core::{
    GuestAddr,
    program::CodeAddress,
    signature_evidence::{N64SYM_REVISION, inspect_n64sym_candidate},
};

#[test]
fn n64sym_match_is_source_bound_candidate_metadata_only() {
    let source = b"alpha 0x000C 0x076D7C20 0x92AA615F\n";
    let bytes = [
        0x24, 0x02, 0x00, 0x01, 0x03, 0xe0, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00,
    ];
    let candidate = inspect_n64sym_candidate(
        source,
        "41985e586bb1c59014fc879303705572b8107e73eca7ad290516bcf53066826e",
        N64SYM_REVISION,
        0,
        CodeAddress {
            pc: GuestAddr(0x8000_1000),
            image: "fixture".into(),
            generation: 7,
        },
        &bytes,
    )
    .unwrap();

    assert_eq!(candidate.reported_name(), "alpha");
    assert!(candidate.candidate_only());
    assert_eq!(candidate.same_key_entries(), 1);
}
