use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, direct_cfg},
    merge::{import_trace, merge_maps},
    program::{CodeAddress, RomIdentity},
    solver::{ClosureStatus, Scope, solve},
    trace::{DiscoveryTrace, EventRecord, TraceEvent, TraceHeader},
};

#[test]
fn deleting_only_dispatch_diagnostics_preserves_the_raw_obligation() {
    let rom = RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    };
    let image = CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "dispatch-retention".into(),
            generation: 0,
        },
        words: vec![0x0800_0000, 0],
        rom_offset: None,
        physical_start: None,
        holes: Vec::new(),
        slots: Vec::new(),
    };
    let static_map = direct_cfg(rom.clone(), &image, &[image.base.pc], 100)
        .unwrap()
        .map;
    for data in [
        TraceEvent::TargetLookup {
            target: image.base.pc,
            delay_slot_entry: false,
        },
        TraceEvent::RuntimeLink {
            target: image.base.pc,
        },
    ] {
        let trace = DiscoveryTrace {
            header: TraceHeader {
                schema_version: 0,
                rom: rom.clone(),
                engine: "dispatch-retention".into(),
                revision: "test".into(),
                capabilities: Default::default(),
            },
            events: vec![EventRecord { seq: 0, data }],
        };
        let raw = import_trace(&trace, &[], 100).unwrap();
        let mut map = merge_maps(&static_map, &raw).unwrap();
        map.unresolved.retain(|u| u.kind != "uncorrelated_target");
        map.validate().unwrap();
        assert_eq!(
            solve(
                &map,
                std::slice::from_ref(&image),
                Scope::DeclaredStaticImages
            )
            .unwrap()
            .status,
            ClosureStatus::Open
        );
    }
}
