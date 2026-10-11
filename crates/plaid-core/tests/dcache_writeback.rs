use plaid_core::{
    dcache_writeback::{
        DcacheByteOrigin, FORMAT, inspect_dcache_writeback_history, verify_dcache_writeback_report,
    },
    program::PhysicalAddr,
    rom::sha256,
};
use serde_json::{Value, json};

const SLOT: u16 = 0x100;

fn line(word: u32) -> [u8; 16] {
    let words = [word, 0x1020_3040, 0x5060_7080, 0x90a0_b0c0];
    let mut result = [0u8; 16];
    for (index, value) in words.into_iter().enumerate() {
        result[index * 4..index * 4 + 4].copy_from_slice(&value.to_be_bytes());
    }
    result
}

fn source(events: Vec<Value>) -> (Vec<u8>, String) {
    let bytes = serde_json::to_vec(&json!({"format": FORMAT, "events": events})).unwrap();
    let digest = sha256(&bytes);
    (bytes, digest)
}

fn fill_pair(read: u64, fill: u64, address: u32, payload: [u8; 16]) -> Vec<Value> {
    vec![
        json!({"record":"backing_read","ordinal":read,"physical_line":address,"payload":payload}),
        json!({"record":"fill","ordinal":fill,"slot":SLOT,"physical_line":address,"payload":payload}),
    ]
}

#[test]
fn exact_writeback_exports_resident_and_fill_origins() {
    let original = line(0x1111_1111);
    let mut mutated = original;
    mutated[..4].copy_from_slice(&0xa1b2_c3d4u32.to_be_bytes());
    let mut events = fill_pair(1, 2, 0x1000, original);
    events.extend([
        json!({"record":"resident_word_mutation","ordinal":3,"slot":SLOT,"physical":0x1000,"payload":[0xa1,0xb2,0xc3,0xd4]}),
        json!({"record":"writeback_begin","ordinal":4,"slot":SLOT,"physical_line":0x1000}),
        json!({"record":"backing_write","ordinal":5,"physical_line":0x1000,"payload":mutated}),
        json!({"record":"writeback_end","ordinal":6,"slot":SLOT}),
    ]);
    let (bytes, digest) = source(events);
    let report = inspect_dcache_writeback_history(&bytes, &digest).unwrap();
    assert_eq!(report.successful_backing_writebacks, 1);
    let receipt = &report.receipts[0];
    assert_eq!(
        (receipt.resident_generation, receipt.resident_revision),
        (2, 3)
    );
    for (index, origin) in receipt.origins.iter().enumerate() {
        if index < 4 {
            assert_eq!(
                *origin,
                DcacheByteOrigin::ResidentWordMutation {
                    mutation_ordinal: 3,
                    byte_index: index as u8,
                }
            );
        } else {
            assert_eq!(
                *origin,
                DcacheByteOrigin::BackingFill {
                    backing_read_ordinal: 1,
                    fill_ordinal: 2,
                    physical: PhysicalAddr(0x1000 + index as u32),
                }
            );
        }
    }
    assert!(!report.sensor_coverage_certified);
    assert!(!report.cache_semantics_complete);
    assert!(!report.executable_lifetime_certified);
    assert!(!report.native_complete);
}

#[test]
fn dirty_eviction_exports_before_replacement_fill() {
    let original = line(0x1111_1111);
    let mut mutated = original;
    mutated[..4].copy_from_slice(&0xa1b2_c3d4u32.to_be_bytes());
    let mut events = fill_pair(1, 2, 0x1000, original);
    events.extend([
        json!({"record":"resident_word_mutation","ordinal":3,"slot":SLOT,"physical":0x1000,"payload":[0xa1,0xb2,0xc3,0xd4]}),
        json!({"record":"writeback_begin","ordinal":4,"slot":SLOT,"physical_line":0x1000}),
        json!({"record":"backing_write","ordinal":5,"physical_line":0x1000,"payload":mutated}),
        json!({"record":"writeback_end","ordinal":6,"slot":SLOT}),
        json!({"record":"backing_read","ordinal":7,"physical_line":0x3000,"payload":original}),
        json!({"record":"fill","ordinal":8,"slot":SLOT,"physical_line":0x3000,"payload":original}),
    ]);
    let (bytes, digest) = source(events);
    let report = inspect_dcache_writeback_history(&bytes, &digest).unwrap();
    assert_eq!(report.successful_backing_writebacks, 1);
    assert_eq!(report.fills, 2);
}

#[test]
fn clean_equal_payload_replacement_exports_nothing() {
    let original = line(0x1111_1111);
    let mut events = fill_pair(1, 2, 0x1000, original);
    events.extend(fill_pair(3, 4, 0x3000, original));
    let (bytes, digest) = source(events);
    let report = inspect_dcache_writeback_history(&bytes, &digest).unwrap();
    assert!(report.receipts.is_empty());
}

#[test]
fn dirty_invalidate_retires_unexported_same_value_origin() {
    let original = line(0x1111_1111);
    let mut events = fill_pair(1, 2, 0x1000, original);
    events.extend([
        json!({"record":"resident_word_mutation","ordinal":3,"slot":SLOT,"physical":0x1000,"payload":[0x11,0x11,0x11,0x11]}),
        json!({"record":"invalidate","ordinal":4,"slot":SLOT}),
    ]);
    let (bytes, digest) = source(events);
    let report = inspect_dcache_writeback_history(&bytes, &digest).unwrap();
    assert_eq!(report.retired_unexported_mutations, 1);
    assert!(report.receipts.is_empty());
}

#[test]
fn same_payload_new_generation_cannot_resurrect_old_origin() {
    let original = line(0x1111_1111);
    let mut events = fill_pair(1, 2, 0x1000, original);
    events.extend([
        json!({"record":"resident_word_mutation","ordinal":3,"slot":SLOT,"physical":0x1000,"payload":[0x11,0x11,0x11,0x11]}),
        json!({"record":"invalidate","ordinal":4,"slot":SLOT}),
        json!({"record":"backing_read","ordinal":5,"physical_line":0x3000,"payload":original}),
        json!({"record":"fill","ordinal":6,"slot":SLOT,"physical_line":0x3000,"payload":original}),
        json!({"record":"backing_write","ordinal":7,"physical_line":0x1000,"payload":original}),
    ]);
    let (bytes, digest) = source(events);
    assert_eq!(
        inspect_dcache_writeback_history(&bytes, &digest).unwrap_err(),
        "backing write without active D-cache writeback"
    );
}

#[test]
fn same_payload_new_revision_invalidates_pending_snapshot() {
    let original = line(0x1111_1111);
    let mut events = fill_pair(1, 2, 0x1000, original);
    events.extend([
        json!({"record":"resident_word_mutation","ordinal":3,"slot":SLOT,"physical":0x1000,"payload":[0x11,0x11,0x11,0x11]}),
        json!({"record":"writeback_begin","ordinal":4,"slot":SLOT,"physical_line":0x1000}),
        json!({"record":"resident_word_mutation","ordinal":5,"slot":SLOT,"physical":0x1000,"payload":[0x11,0x11,0x11,0x11]}),
        json!({"record":"backing_write","ordinal":6,"physical_line":0x1000,"payload":original}),
    ]);
    let (bytes, digest) = source(events);
    assert_eq!(
        inspect_dcache_writeback_history(&bytes, &digest).unwrap_err(),
        "resident generation/revision changed after writeback begin"
    );
}

#[test]
fn missing_writeback_or_fill_causality_rejects() {
    let original = line(0x1111_1111);
    let mut dirty_replace = fill_pair(1, 2, 0x1000, original);
    dirty_replace.extend([
        json!({"record":"resident_word_mutation","ordinal":3,"slot":SLOT,"physical":0x1000,"payload":[0xa1,0xb2,0xc3,0xd4]}),
        json!({"record":"backing_read","ordinal":4,"physical_line":0x3000,"payload":original}),
        json!({"record":"fill","ordinal":5,"slot":SLOT,"physical_line":0x3000,"payload":original}),
    ]);
    let (bytes, digest) = source(dirty_replace);
    assert_eq!(
        inspect_dcache_writeback_history(&bytes, &digest).unwrap_err(),
        "dirty replacement without successful writeback"
    );

    let (bytes, digest) = source(vec![
        json!({"record":"backing_read","ordinal":1,"physical_line":0x1000,"payload":original}),
        json!({"record":"invalidate","ordinal":2,"slot":SLOT}),
    ]);
    assert_eq!(
        inspect_dcache_writeback_history(&bytes, &digest).unwrap_err(),
        "backing read was not immediately consumed by a fill"
    );
}

#[test]
fn payload_forgery_report_forgery_and_source_forgery_reject() {
    let original = line(0x1111_1111);
    let mut mutated = original;
    mutated[..4].copy_from_slice(&0xa1b2_c3d4u32.to_be_bytes());
    let mut events = fill_pair(1, 2, 0x1000, original);
    events.extend([
        json!({"record":"resident_word_mutation","ordinal":3,"slot":SLOT,"physical":0x1000,"payload":[0xa1,0xb2,0xc3,0xd4]}),
        json!({"record":"writeback_begin","ordinal":4,"slot":SLOT,"physical_line":0x1000}),
        json!({"record":"backing_write","ordinal":5,"physical_line":0x1000,"payload":original}),
    ]);
    let (bytes, digest) = source(events);
    assert_eq!(
        inspect_dcache_writeback_history(&bytes, &digest).unwrap_err(),
        "backing write does not match the captured resident snapshot"
    );
    assert_ne!(mutated, original);

    let (bytes, digest) = source(fill_pair(1, 2, 0x1000, original));
    let mut report = inspect_dcache_writeback_history(&bytes, &digest).unwrap();
    verify_dcache_writeback_report(&report, &bytes, &digest).unwrap();
    report.native_complete = true;
    assert_eq!(
        verify_dcache_writeback_report(&report, &bytes, &digest).unwrap_err(),
        "D-cache writeback report does not match complete source/receipt"
    );
    assert_eq!(
        inspect_dcache_writeback_history(&bytes, &"0".repeat(64)).unwrap_err(),
        "D-cache writeback source receipt mismatch"
    );
}
