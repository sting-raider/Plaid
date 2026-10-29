use plaid_core::{GuestAddr, merge::merge_maps, program::*};

fn binding() -> (ProgramMap, CodeAddress) {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    });
    let entry = CodeAddress {
        pc: GuestAddr(0x80000400),
        image: "synthetic".into(),
        generation: 0,
    };
    map.evidence.insert(
        "source".into(),
        Evidence {
            kind: plaid_core::EvidenceKind::Static,
            producer: "synthetic".into(),
            revision: "1".into(),
            detail: "synthetic SDK declaration".into(),
        },
    );
    map.runtime_functions.insert(
        entry.clone(),
        serde_json::from_value(
            serde_json::json!({"name":"osStartThread","source_size":8,"evidence":["source"]}),
        )
        .unwrap(),
    );
    map.runtime_running_thread
        .insert(entry.clone(), GuestAddr(0x80004000));
    (map, entry)
}

#[test]
fn runtime_running_thread_roundtrip_merge_and_binding_refusals() {
    let (map, entry) = binding();
    map.validate().unwrap();
    assert_eq!(
        serde_json::from_value::<ProgramMap>(serde_json::to_value(&map).unwrap()).unwrap(),
        map
    );
    assert_eq!(merge_maps(&map, &map).unwrap(), map);
    for address in [0x80004001, 0x00804000, 0x80800000, 0xa0800000] {
        let mut bad = map.clone();
        bad.runtime_running_thread
            .insert(entry.clone(), GuestAddr(address));
        assert!(bad.validate().is_err());
    }
    let mut conflict = map.clone();
    conflict
        .runtime_running_thread
        .insert(entry.clone(), GuestAddr(0x80004004));
    assert!(merge_maps(&map, &conflict).is_err());
    let mut missing = map.clone();
    missing.runtime_functions.clear();
    assert!(missing.validate().is_err());
    let mut extent = map.clone();
    extent
        .runtime_functions
        .get_mut(&entry)
        .unwrap()
        .source_size = None;
    assert!(extent.validate().is_err());
    let mut wrong = map.clone();
    wrong.runtime_functions.get_mut(&entry).unwrap().name = "osGetCount".into();
    assert!(wrong.validate().is_err());
    let mut legacy = map;
    legacy.runtime_running_thread.clear();
    assert!(
        serde_json::to_value(legacy)
            .unwrap()
            .get("runtime_running_thread")
            .is_none()
    );
}
