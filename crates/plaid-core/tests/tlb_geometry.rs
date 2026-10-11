use plaid_core::{
    program::GuestVirtualAddr,
    tlb_geometry::{TlbPageOffsetReceipt, derive_tlb_page_offset, verify_tlb_page_offset_receipt},
};
use serde_json::json;

#[test]
fn every_serialized_geometry_field_rechecks_against_external_input() {
    let va = GuestVirtualAddr(0x21000);
    let receipt = derive_tlb_page_offset(0x6000, va).unwrap();
    verify_tlb_page_offset_receipt(&receipt, 0x6000, va).unwrap();
    let original = serde_json::to_value(receipt).unwrap();
    for (path, value) in [
        (vec!["vaddr"], json!(0x21004)),
        (vec!["selected_half"], json!("odd")),
        (vec!["in_page_offset"], json!(0)),
        (vec!["geometry", "page_size"], json!("page4_kib")),
        (vec!["geometry", "page_mask"], json!(0)),
        (vec!["geometry", "half_select_mask"], json!(0x1000)),
        (vec!["geometry", "in_page_offset_mask"], json!(0xfff)),
    ] {
        let mut forged = original.clone();
        let mut selected = &mut forged;
        for field in path {
            selected = &mut selected[field];
        }
        *selected = value;
        let forged: TlbPageOffsetReceipt = serde_json::from_value(forged).unwrap();
        assert!(verify_tlb_page_offset_receipt(&forged, 0x6000, va).is_err());
    }
}

#[test]
fn equal_offsets_do_not_erase_external_mask_or_address_identity() {
    let va = GuestVirtualAddr(0);
    let receipt = derive_tlb_page_offset(0, va).unwrap();
    assert_eq!(
        derive_tlb_page_offset(0x6000, va).unwrap().in_page_offset,
        receipt.in_page_offset
    );
    assert!(verify_tlb_page_offset_receipt(&receipt, 0x6000, va).is_err());
    assert!(verify_tlb_page_offset_receipt(&receipt, 0, GuestVirtualAddr(0x2000)).is_err());
    for mask in [0x2000, 0x7e000, 0x1fe000, u32::MAX] {
        assert!(verify_tlb_page_offset_receipt(&receipt, mask, va).is_err());
    }
}

#[test]
fn serde_rejects_oversized_masks_and_extra_provenance_claims() {
    let receipt = derive_tlb_page_offset(0, GuestVirtualAddr(0)).unwrap();
    let value = serde_json::to_value(receipt).unwrap();
    for (path, extra) in [
        (vec!["geometry", "page_mask"], json!(1u64 << 32)),
        (vec!["geometry", "page_mask"], json!(true)),
        (vec!["mapping_generation"], json!(1)),
        (vec!["native_complete"], json!(true)),
    ] {
        let mut forged = value.clone();
        let mut selected = &mut forged;
        for field in path {
            selected = &mut selected[field];
        }
        *selected = extra;
        assert!(serde_json::from_value::<TlbPageOffsetReceipt>(forged).is_err());
    }
}
