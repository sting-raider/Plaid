use plaid_core::{rom::sha256, tlb_fetch};
use serde_json::{Value, json};

fn source(region: u8, vaddr: u64, mask: u32, reverse_endian: bool) -> Value {
    let translated = if mask == 0 { 0x1000 } else { 0x11000 };
    let bus = if reverse_endian {
        translated ^ 4
    } else {
        translated
    };
    json!({
        "format":tlb_fetch::FORMAT,
        "events":[
            {
                "record":"begin",
                "ordinal":1,
                "context":1,
                "epoch":1,
                "vaddr":vaddr,
                "current_asid":7,
                "translation_context_ref":"ctx-1",
                "mapping":{
                    "mapping_ref":"mapping-1",
                    "raw_page_mask":mask,
                    "virtual_address":if mask == 0 { vaddr & !0x1fffu64 } else { vaddr & !0x7fffu64 },
                    "asid":7,
                    "region":region,
                    "global0":false,
                    "global1":false,
                    "lo0":{"valid":true,"cca":2,"physical_base":if mask == 0 { 0x1000 } else { 0x10000 }},
                    "lo1":{"valid":true,"cca":2,"physical_base":0x20000}
                },
                "translated_paddr":translated,
                "bus_paddr":bus,
                "reverse_endian":reverse_endian
            },
            {
                "record":"rdram_read",
                "ordinal":2,
                "address":bus,
                "bytes":4,
                "requestor":"vr4300_uncached",
                "value":0x34091111u32
            },
            {
                "record":"end",
                "ordinal":3,
                "context":1,
                "epoch":1,
                "vaddr":vaddr,
                "word":0x34091111u32
            }
        ]
    })
}

fn inspect(value: &Value) -> Result<tlb_fetch::TlbFetchReport, String> {
    let bytes = serde_json::to_vec(value).unwrap();
    tlb_fetch::inspect_tlb_fetch_history(&bytes, &sha256(&bytes))
}

#[test]
fn unexecuted_nonzero_region_stays_unknown() {
    let value = source(1, (1u64 << 62) | 0x4000, 0, false);
    assert!(inspect(&value).is_err());
}

#[test]
fn large_page_reverse_endian_composition_stays_unknown() {
    let value = source(0, 0x21000, 0b11 << 13, true);
    assert!(inspect(&value).is_err());
}

#[test]
fn forged_pfn_low_bits_cannot_become_arithmetically_consistent_fetch_ancestry() {
    let mut value = source(0, 0x4000, 0, false);
    value["events"][0]["mapping"]["lo0"]["physical_base"] = json!(0x1004);
    value["events"][0]["translated_paddr"] = json!(0x1004);
    value["events"][0]["bus_paddr"] = json!(0x1004);
    value["events"][1]["address"] = json!(0x1004);
    assert!(inspect(&value).is_err());
}

#[test]
fn canonical_masks_and_typed_boundaries_cannot_be_bypassed() {
    let base = source(0, 0x4000, 0, false);
    for (index, field, forged_value) in [
        (0, "ordinal", json!(true)),
        (0, "epoch", json!(0)),
        (0, "translation_context_ref", json!("")),
        (1, "bytes", json!(true)),
        (1, "requestor", json!("cached_cpu")),
        (2, "word", json!(1u64 << 32)),
        (2, "native_complete", json!(true)),
    ] {
        let mut forged = base.clone();
        forged["events"][index][field] = forged_value;
        assert!(inspect(&forged).is_err(), "accepted {index}:{field}");
    }
    for mask in [1, 0x2000, 0x6001, 0xe000, 0x7e000, u32::MAX] {
        let mut forged = base.clone();
        forged["events"][0]["mapping"]["raw_page_mask"] = json!(mask);
        assert!(inspect(&forged).is_err(), "accepted mask {mask:x}");
    }
}
