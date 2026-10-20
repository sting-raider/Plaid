use plaid_core::{
    dcache_writeback::{
        DcacheByteOrigin, READ_FORMAT, inspect_dcache_resident_read_history,
        inspect_dcache_writeback_history, verify_dcache_resident_read_report,
    },
    rom::sha256,
};
use serde_json::{Value, json};

fn fill(ordinal: u64, physical: u32) -> Vec<Value> {
    vec![
        json!({"record":"backing_read","ordinal":ordinal,"physical_line":physical,"payload":([17;16])}),
        json!({"record":"fill","ordinal":ordinal+1,"slot":0,"physical_line":physical,"payload":([17;16])}),
    ]
}
fn read(ordinal: u64, byte: u8) -> Value {
    json!({"record":"cached_word_read","ordinal":ordinal,"pc":0x80006008u32,
        "effective_virtual":0x80002000u32,"physical":0x2000,"slot":0,"payload":([byte;4])})
}
fn source(events: Vec<Value>) -> (Vec<u8>, String) {
    let bytes = serde_json::to_vec(&json!({"format":READ_FORMAT,"events":events})).unwrap();
    let digest = sha256(&bytes);
    (bytes, digest)
}

#[test]
fn backing_changes_do_not_steal_resident_ancestry_and_exports_share_read_origins() {
    let mut events = fill(1, 0x2000);
    events.extend([
        json!({"record":"backing_word_mutation","ordinal":3,"physical":0x2000,"payload":([17;4])}),
        read(4, 17),
        json!({"record":"backing_word_mutation","ordinal":5,"physical":0x2000,"payload":([34;4])}),
        read(6, 17),
        json!({"record":"resident_word_mutation","ordinal":7,"physical":0x2000,"slot":0,"payload":([17;4])}),
        read(8, 17),
        json!({"record":"writeback_begin","ordinal":9,"slot":0,"physical_line":0x2000}),
        json!({"record":"backing_write","ordinal":10,"physical_line":0x2000,"payload":([17;16])}),
        json!({"record":"writeback_end","ordinal":11,"slot":0}),
        read(12, 17),
    ]);
    let (bytes, digest) = source(events);
    let report = inspect_dcache_resident_read_history(&bytes, &digest).unwrap();
    let reads = &report.reads;
    assert_eq!(reads[0].origins, reads[1].origins);
    assert_ne!(reads[1].origins, reads[2].origins);
    assert_eq!(reads[2].origins, reads[3].origins);
    assert_eq!(
        reads[1].current_captured_backing.as_ref().unwrap().payload,
        [34; 4]
    );
    assert_eq!(
        reads[3]
            .current_captured_backing
            .as_ref()
            .unwrap()
            .write_ordinal,
        10
    );
    assert_eq!(reads[2].origins, report.writeback.receipts[0].origins[..4]);
    assert_eq!(
        reads[2].resident_revision,
        report.writeback.receipts[0].resident_revision
    );
    assert!(!report.pointer_table_immutability_certified);
    assert!(!report.cpu_operand_dataflow_certified);
    assert!(!report.writeback.native_complete);
    verify_dcache_resident_read_report(&report, &bytes, &digest).unwrap();
    let mut forged = report.clone();
    forged.reads[2].origins = reads[0].origins;
    assert!(verify_dcache_resident_read_report(&forged, &bytes, &digest).is_err());
    assert!(inspect_dcache_writeback_history(&bytes, &digest).is_err());
    assert!(inspect_dcache_resident_read_history(&bytes, &"0".repeat(64)).is_err());
}

#[test]
fn equal_payload_conflict_replacement_and_invalidation_cannot_borrow_old_source() {
    let mut events = fill(1, 0x2000);
    events.push(read(3, 17));
    events.extend(fill(4, 0x4000));
    events.push(read(6, 17));
    let (bytes, digest) = source(events.clone());
    assert!(inspect_dcache_resident_read_history(&bytes, &digest).is_err());
    events.pop();
    events.extend(fill(6, 0x2000));
    events.push(read(8, 17));
    let (bytes, digest) = source(events.clone());
    let report = inspect_dcache_resident_read_history(&bytes, &digest).unwrap();
    assert_ne!(report.reads[0].origins, report.reads[1].origins);
    assert_eq!(report.reads[1].resident_generation, 7);
    assert!(matches!(
        report.reads[1].origins[0],
        DcacheByteOrigin::BackingFill {
            backing_read_ordinal: 6,
            ..
        }
    ));
    events.push(json!({"record":"invalidate","ordinal":9,"slot":0}));
    events.push(read(10, 17));
    let (bytes, digest) = source(events);
    assert!(inspect_dcache_resident_read_history(&bytes, &digest).is_err());
}

#[test]
fn impossible_geometry_changed_payload_and_deleted_mutation_are_rejected() {
    let mut events = fill(1, 0x2000);
    events.extend([
        json!({"record":"resident_word_mutation","ordinal":3,"physical":0x2000,"slot":0,"payload":([34;4])}),
        read(4, 34),
    ]);
    for (field, value) in [
        ("effective_virtual", json!(0xa0002000u32)),
        ("physical", json!(0x4000)),
        ("slot", json!(512)),
        ("payload", json!(([17; 4]))),
        ("pc", json!(0x80006009u32)),
    ] {
        let mut forged = events.clone();
        forged[3][field] = value;
        let (bytes, digest) = source(forged);
        assert!(
            inspect_dcache_resident_read_history(&bytes, &digest).is_err(),
            "{field}"
        );
    }
    events.remove(2);
    events[2]["ordinal"] = json!(3);
    let (bytes, digest) = source(events);
    assert!(inspect_dcache_resident_read_history(&bytes, &digest).is_err());
    let mut events = fill(2, 0x2000);
    events.insert(
        0,
        json!({"record":"backing_word_mutation","ordinal":1,"physical":0x2000,"payload":([34;4])}),
    );
    let (bytes, digest) = source(events);
    assert!(inspect_dcache_resident_read_history(&bytes, &digest).is_err());
}
