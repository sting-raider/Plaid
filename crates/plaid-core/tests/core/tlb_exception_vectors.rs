use plaid_core::{
    EvidenceKind, GuestAddr,
    merge::merge_maps,
    program::{BasicBlock, CodeAddress, Evidence, ProgramMap, RomIdentity},
};

fn vector_map(pc: u32) -> (ProgramMap, CodeAddress) {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    });
    let address = CodeAddress {
        pc: GuestAddr(pc),
        image: "synthetic-vector".into(),
        generation: 0,
    };
    map.evidence.insert(
        "source".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "synthetic".into(),
            revision: "1".into(),
            detail: "original synthetic instruction source".into(),
        },
    );
    map.entries
        .insert(address.clone(), ["source".into()].into());
    map.blocks.insert(BasicBlock {
        start: address.clone(),
        size: 4,
        delay_slot_entry: false,
        evidence: ["source".into()].into(),
    });
    map.tlb_exception_vectors.insert(address.clone());
    (map, address)
}

#[test]
fn tlb_vectors_roundtrip_and_merge_with_source_identity() {
    let (left, _) = vector_map(0x80000000);
    let (right, _) = vector_map(0x80000180);
    left.validate().unwrap();
    right.validate().unwrap();
    let merged = merge_maps(&left, &right).unwrap();
    assert_eq!(merged.tlb_exception_vectors.len(), 2);
    let json = serde_json::to_string(&merged).unwrap();
    assert_eq!(serde_json::from_str::<ProgramMap>(&json).unwrap(), merged);
    let mut legacy = merged;
    legacy.tlb_exception_vectors.clear();
    let json = serde_json::to_value(&legacy).unwrap();
    assert!(json.get("tlb_exception_vectors").is_none());
    assert!(
        serde_json::from_value::<ProgramMap>(json)
            .unwrap()
            .tlb_exception_vectors
            .is_empty()
    );
}

#[test]
fn tlb_vectors_require_unique_real_guest_entries() {
    let (map, address) = vector_map(0x80000000);
    let mut missing = map.clone();
    missing.entries.remove(&address);
    assert!(missing.validate().is_err());
    let mut generation = map.clone();
    generation.tlb_exception_vectors.clear();
    generation.tlb_exception_vectors.insert(CodeAddress {
        generation: 1,
        ..address.clone()
    });
    assert!(generation.validate().is_err());
    let mut host = map.clone();
    host.runtime_functions.insert(
        address.clone(),
        serde_json::from_value(serde_json::json!({
            "name": "host", "evidence": ["source"]
        }))
        .unwrap(),
    );
    assert!(host.validate().is_err());
    let mut duplicate = map;
    let alternate = CodeAddress {
        image: "another-source".into(),
        ..address
    };
    duplicate
        .entries
        .insert(alternate.clone(), ["source".into()].into());
    duplicate.blocks.insert(BasicBlock {
        start: alternate.clone(),
        size: 4,
        delay_slot_entry: false,
        evidence: ["source".into()].into(),
    });
    duplicate.tlb_exception_vectors.insert(alternate);
    assert!(duplicate.validate().is_err());
    assert!(vector_map(0x80000400).0.validate().is_err());
}
