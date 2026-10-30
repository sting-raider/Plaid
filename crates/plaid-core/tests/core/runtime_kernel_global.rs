use plaid_core::{
    GuestAddr,
    merge::merge_maps,
    program::{CodeAddress, ProgramMap, RomIdentity, SdkGlobalBinding},
};

#[test]
fn kernel_globals_require_matching_source_abi_extent_and_ram() {
    for (name, binding) in [
        (
            "osSetEventMesg",
            SdkGlobalBinding::EventStateTable(GuestAddr(0x80003000)),
        ),
        (
            "osCreateMesgQueue",
            SdkGlobalBinding::ThreadTail(GuestAddr(0xa0003000)),
        ),
        (
            "osStartThread",
            SdkGlobalBinding::RunQueue(GuestAddr(0x80003000)),
        ),
        (
            "osYieldThread",
            SdkGlobalBinding::RunQueue(GuestAddr(0xa0003000)),
        ),
    ] {
        let mut map = ProgramMap::new(RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        });
        let entry = CodeAddress {
            pc: GuestAddr(0x80000400),
            image: "synthetic".into(),
            generation: 0,
        };
        map.evidence.insert("source".into(), serde_json::from_value(serde_json::json!({"kind":"static","producer":"synthetic","revision":"1","detail":"SDK source"})).unwrap());
        map.runtime_functions.insert(
            entry.clone(),
            serde_json::from_value(
                serde_json::json!({"name":name,"source_size":8,"evidence":["source"]}),
            )
            .unwrap(),
        );
        map.runtime_kernel_global.insert(entry.clone(), binding);
        map.validate().unwrap();
        let (size, at): (u32, fn(GuestAddr) -> SdkGlobalBinding) = match binding {
            SdkGlobalBinding::EventStateTable(_) => (120, SdkGlobalBinding::EventStateTable),
            SdkGlobalBinding::ThreadTail(_) => (8, SdkGlobalBinding::ThreadTail),
            SdkGlobalBinding::RunQueue(_) => (4, SdkGlobalBinding::RunQueue),
        };
        for base in [0x80000000, 0xa0000000] {
            let mut edge = map.clone();
            edge.runtime_kernel_global
                .insert(entry.clone(), at(GuestAddr(base + 0x800000 - size)));
            edge.validate().unwrap();
            edge.runtime_kernel_global
                .insert(entry.clone(), at(GuestAddr(base + 0x800000 - size + 4)));
            assert!(edge.validate().is_err());
        }
        assert_eq!(ProgramMap::from_json(&map.to_json().unwrap()).unwrap(), map);
        assert_eq!(merge_maps(&map, &map).unwrap(), map);
        let mut bad = map.clone();
        bad.runtime_functions.get_mut(&entry).unwrap().source_size = None;
        assert!(bad.validate().is_err());
        bad = map.clone();
        bad.runtime_functions.get_mut(&entry).unwrap().name = "osGetCount".into();
        assert!(bad.validate().is_err());
        for address in [0x80003001, 0x3000, 0x80800000, 0xa0800000] {
            bad = map.clone();
            bad.runtime_kernel_global.insert(
                entry.clone(),
                match binding {
                    SdkGlobalBinding::EventStateTable(_) => {
                        SdkGlobalBinding::EventStateTable(GuestAddr(address))
                    }
                    SdkGlobalBinding::ThreadTail(_) => {
                        SdkGlobalBinding::ThreadTail(GuestAddr(address))
                    }
                    SdkGlobalBinding::RunQueue(_) => SdkGlobalBinding::RunQueue(GuestAddr(address)),
                },
            );
            assert!(bad.validate().is_err());
        }
        bad = map.clone();
        bad.runtime_kernel_global.insert(
            entry.clone(),
            match binding {
                SdkGlobalBinding::EventStateTable(_) => {
                    SdkGlobalBinding::EventStateTable(GuestAddr(0x80003004))
                }
                SdkGlobalBinding::ThreadTail(_) => {
                    SdkGlobalBinding::ThreadTail(GuestAddr(0xa0003004))
                }
                SdkGlobalBinding::RunQueue(_) => SdkGlobalBinding::RunQueue(GuestAddr(0x80003004)),
            },
        );
        assert!(merge_maps(&map, &bad).is_err());
        map.runtime_kernel_global.clear();
        assert!(
            serde_json::to_value(map)
                .unwrap()
                .get("runtime_kernel_global")
                .is_none()
        );
    }
}
