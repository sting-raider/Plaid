use plaid_core::{
    dcache_writeback::{
        DcacheByteOrigin, STORE64_FORMAT, inspect_dcache_resident_read_history,
        inspect_dcache_store64_history, verify_dcache_store64_report,
    },
    rom::sha256,
    store_mutation::{ARES_REVISION, MODEL_SHA256},
};
use serde_json::{Value, json};

fn operation(ordinal: u64, label: &str, sink: &str) -> Value {
    let mut gpr = [0u64; 32];
    gpr[1] = 0xffffffff80002000;
    gpr[2] = 0x1122334455667788;
    json!({"record":"store64","ordinal":ordinal,
        "context":{"pc":0xffffffffa0001000u64,"word":(0x3fu32<<26)|(1<<21)|(2<<16),
            "gpr":gpr,"after_gpr":gpr,"after_pc":0xffffffffa0001004u64,"little":false,"exception":0},
        "receipt":{"reference_revision":ARES_REVISION,"model_sha256":MODEL_SHA256,
            "operation_event":label,"site":0xa0001000u32,"address":0x80002000u32,
            "source_value":gpr[2],"kind":"sd","endian":"big","cached":true,"outcome":"completed",
            "subwrites":[{"sequence":0,"event":sink,"handler_address":0x80002000u32,
                "sink_physical":0x2000,"bytes":8,"value":gpr[2],"layer":"dcache_resident"}]}})
}
fn fixture() -> Vec<Value> {
    let initial: Vec<u8> = (0xa0..0xb0).collect();
    let payload = 0x1122334455667788u64.to_be_bytes();
    let mut changed = initial.clone();
    changed[..8].copy_from_slice(&payload);
    vec![
        json!({"record":"backing_read","ordinal":1,"physical_line":0x2000,"payload":initial}),
        json!({"record":"fill","ordinal":2,"slot":0,"physical_line":0x2000,"payload":initial}),
        operation(3, "first", "sink1"),
        json!({"record":"store64_subwrite","ordinal":4,"sequence":0,"event":"sink1","physical":0x2000,
            "slot":0,"payload":payload,"resident_after":changed}),
        operation(5, "repeat", "sink2"),
        json!({"record":"store64_subwrite","ordinal":6,"sequence":0,"event":"sink2","physical":0x2000,
            "slot":0,"payload":payload,"resident_after":changed}),
        json!({"record":"writeback_begin","ordinal":7,"slot":0,"physical_line":0x2000}),
        json!({"record":"backing_write","ordinal":8,"physical_line":0x2000,"payload":changed}),
        json!({"record":"writeback_end","ordinal":9,"slot":0}),
    ]
}
fn source(events: Vec<Value>) -> (Vec<u8>, String) {
    let bytes = serde_json::to_vec(&json!({"format":STORE64_FORMAT,"events":events})).unwrap();
    let digest = sha256(&bytes);
    (bytes, digest)
}

#[test]
fn equal_decoded_stores_export_latest_subwrite_and_all_untouched_fill_lanes() {
    let (bytes, digest) = source(fixture());
    let report = inspect_dcache_store64_history(&bytes, &digest).unwrap();
    assert_eq!(report.store64_operations.as_ref().unwrap().len(), 2);
    assert_eq!(report.writeback.receipts[0].resident_revision, 6);
    let origins = &report.writeback.receipts[0].origins;
    for (index, origin) in origins[..8].iter().enumerate() {
        assert_eq!(
            *origin,
            DcacheByteOrigin::Store64Subwrite {
                operation_ordinal: 5,
                subwrite_ordinal: 6,
                sequence: 0,
                byte_index: index as u8
            }
        );
    }
    for (index, origin) in origins[8..].iter().enumerate() {
        assert!(
            matches!(origin,DcacheByteOrigin::BackingFill{backing_read_ordinal:1,fill_ordinal:2,physical}
            if physical.0==0x2008+index as u32)
        );
    }
    verify_dcache_store64_report(&report, &bytes, &digest).unwrap();
    let mut forged = report.clone();
    forged.writeback.receipts[0].origins[0] = DcacheByteOrigin::Store64Subwrite {
        operation_ordinal: 3,
        subwrite_ordinal: 4,
        sequence: 0,
        byte_index: 0,
    };
    assert!(verify_dcache_store64_report(&forged, &bytes, &digest).is_err());
    assert!(!report.writeback.native_complete);
    assert!(inspect_dcache_resident_read_history(&bytes, &digest).is_err());
}

#[test]
fn missing_same_value_effect_and_false_decoded_context_fail_closed() {
    let mut missing = fixture();
    missing.remove(5);
    for (index, event) in missing.iter_mut().enumerate() {
        event["ordinal"] = json!(index + 1);
    }
    let (bytes, digest) = source(missing);
    assert!(inspect_dcache_store64_history(&bytes, &digest).is_err());
    for change in 0..7 {
        let mut events = fixture();
        match change {
            0 => events[2]["context"]["word"] = json!(0),
            1 => events[2]["context"]["gpr"][2] = json!(0),
            2 => events[2]["context"]["after_gpr"][2] = json!(0),
            3 => events[2]["context"]["after_pc"] = json!(0xffffffffa0001008u64),
            4 => events[3]["resident_after"][15] = json!(0),
            5 => events[3]["physical"] = json!(0x4000),
            _ => events[3]["sequence"] = json!(1),
        }
        let (bytes, digest) = source(events);
        assert!(
            inspect_dcache_store64_history(&bytes, &digest).is_err(),
            "{change}"
        );
    }
}
