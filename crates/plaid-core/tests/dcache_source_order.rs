use plaid_core::{dcache_source, rom::sha256};
use serde_json::json;

#[test]
fn intervening_same_value_backing_write_cannot_launder_old_fill() {
    let source = json!({
        "format": dcache_source::FORMAT,
        "initial_backing": [
            {"address": 0x2000u32, "value": 0x8000_7000u32},
            {"address": 0x2004u32, "value": 0x1111_2222u32},
            {"address": 0x2008u32, "value": 0x3333_4444u32},
            {"address": 0x200cu32, "value": 0x5555_6666u32}
        ],
        "records": [
            {"kind":"backing_burst_read","event":{
                "ordinal":1u64,"address":0x2000u32,
                "words":[0x8000_7000u32,0x1111_2222u32,0x3333_4444u32,0x5555_6666u32]
            }},
            {"kind":"backing_write","event":{
                "ordinal":2u64,"pc":0xffff_ffff_8000_6004u64,
                "address":0x2000u32,"value":0x8000_7000u32
            }},
            {"kind":"cache_read","event":{
                "ordinal":3u64,"pc":0xffff_ffff_8000_6020u64,
                "vaddr":0xffff_ffff_8000_2000u64,"paddr":0x2000u32,
                "value":0x8000_7000u32,"slot":7u16,"tag":0x2001u32,
                "dirty":0u16,"hit_before":false
            }}
        ]
    });
    let bytes = serde_json::to_vec(&source).unwrap();
    let error = dcache_source::inspect_dcache_source_history(&bytes, &sha256(&bytes))
        .expect_err("intervening write must break fill pairing");
    assert!(error.contains("immediately follow"));
}
