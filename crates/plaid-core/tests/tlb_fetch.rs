use plaid_core::{
    rom::sha256,
    tlb_fetch::{self, TlbFetchReport},
};
use serde_json::{Value, json};

fn half(valid: bool, cca: u8, physical_base: u32) -> Value {
    json!({"valid":valid,"cca":cca,"physical_base":physical_base})
}

#[allow(clippy::too_many_arguments)]
fn mapping(
    mapping_ref: &str,
    raw_page_mask: u32,
    virtual_address: u64,
    asid: u8,
    global: bool,
    lo0_base: u32,
    lo1_base: u32,
) -> Value {
    json!({
        "mapping_ref":mapping_ref,
        "raw_page_mask":raw_page_mask,
        "virtual_address":virtual_address,
        "asid":asid,
        "region":0,
        "global0":global,
        "global1":global,
        "lo0":half(true, 2, lo0_base),
        "lo1":half(true, 2, lo1_base)
    })
}

#[allow(clippy::too_many_arguments)]
fn begin(
    ordinal: u64,
    epoch: u64,
    vaddr: u64,
    current_asid: u8,
    mapping: Value,
    translated_paddr: u32,
    bus_paddr: u32,
    reverse_endian: bool,
) -> Value {
    json!({
        "record":"begin",
        "ordinal":ordinal,
        "context":ordinal,
        "epoch":epoch,
        "vaddr":vaddr,
        "current_asid":current_asid,
        "translation_context_ref":format!("ctx-{epoch}"),
        "mapping":mapping,
        "translated_paddr":translated_paddr,
        "bus_paddr":bus_paddr,
        "reverse_endian":reverse_endian
    })
}

fn read(ordinal: u64, address: u32, value: u32) -> Value {
    json!({
        "record":"rdram_read",
        "ordinal":ordinal,
        "address":address,
        "bytes":4,
        "requestor":"vr4300_uncached",
        "value":value
    })
}

fn end(ordinal: u64, context: u64, epoch: u64, vaddr: u64, word: u32) -> Value {
    json!({
        "record":"end",
        "ordinal":ordinal,
        "context":context,
        "epoch":epoch,
        "vaddr":vaddr,
        "word":word
    })
}

fn history(events: Vec<Value>) -> Value {
    json!({"format":tlb_fetch::FORMAT,"events":events})
}

fn inspect(value: &Value) -> Result<TlbFetchReport, String> {
    let bytes = serde_json::to_vec(value).unwrap();
    tlb_fetch::inspect_tlb_fetch_history(&bytes, &sha256(&bytes))
}

#[test]
fn execution_backed_pagemask_geometry_produces_exact_backing_witnesses() {
    let cases = [
        (
            0u32, 0x4000u64, 0x4000u64, 0x1000u32, 0x2000u32, 0x1000u32, 0u8,
        ),
        (
            0b11u32 << 13,
            0x21000,
            0x20000,
            0x10000,
            0x20000,
            0x11000,
            0,
        ),
        (
            0b11u32 << 13,
            0x2c000,
            0x28000,
            0x30000,
            0x40000,
            0x40000,
            1,
        ),
        (
            0b1111u32 << 13,
            0x45000,
            0x40000,
            0x50000,
            0x70000,
            0x55000,
            0,
        ),
        (
            0b1111u32 << 13,
            0x70000,
            0x60000,
            0x80000,
            0xa0000,
            0xa0000,
            1,
        ),
    ];

    for (index, (mask, vaddr, entry_va, p0, p1, expected_pa, selected)) in
        cases.into_iter().enumerate()
    {
        let word = 0x3409_1111u32 + index as u32;
        let value = history(vec![
            begin(
                1,
                1,
                vaddr,
                7,
                mapping("map-a", mask, entry_va, 7, false, p0, p1),
                expected_pa,
                expected_pa,
                false,
            ),
            read(2, expected_pa, word),
            end(3, 1, 1, vaddr, word),
        ]);
        let report = inspect(&value).unwrap();
        assert_eq!(report.fetches, 1);
        let witness = &report.witnesses[0];
        assert_eq!(witness.vaddr.0, vaddr);
        assert_eq!(witness.translated_paddr.0, expected_pa);
        assert_eq!(witness.bus_paddr.0, expected_pa);
        assert_eq!(witness.selected_half, selected);
        assert_eq!(witness.word, word);
        assert!(
            !report.sensor_coverage_certified
                && !report.mapping_history_certified
                && !report.translation_context_certified
                && !report.cache_residency_certified
                && !report.executable_lifetime_certified
                && !report.whole_rom_closed
                && !report.native_complete
        );
    }
}

#[test]
fn fixed_4k_equal_value_decoy_cannot_replace_large_page_translation() {
    let word = 0x340a_2222;
    let value = history(vec![
        begin(
            1,
            1,
            0x21000,
            7,
            mapping("map-16k", 0b11 << 13, 0x20000, 7, false, 0x10000, 0x20000),
            0x20000,
            0x20000,
            false,
        ),
        read(2, 0x20000, word),
        end(3, 1, 1, 0x21000, word),
    ]);
    assert!(inspect(&value).is_err());
}

#[test]
fn selected_half_validity_and_asid_are_checked_before_certification() {
    let mut invalid_mapping = mapping(
        "map-invalid",
        0b11 << 13,
        0x90000,
        7,
        false,
        0x10000,
        0x20000,
    );
    invalid_mapping["lo0"]["valid"] = json!(false);
    let invalid = history(vec![
        begin(1, 1, 0x91000, 7, invalid_mapping, 0x11000, 0x11000, false),
        read(2, 0x11000, 0x340b_3333),
        end(3, 1, 1, 0x91000, 0x340b_3333),
    ]);
    assert!(inspect(&invalid).is_err());

    let mismatch = history(vec![
        begin(
            1,
            1,
            0x21000,
            99,
            mapping("map-asid", 0b11 << 13, 0x20000, 7, false, 0x10000, 0x20000),
            0x11000,
            0x11000,
            false,
        ),
        read(2, 0x11000, 0x340b_3333),
        end(3, 1, 1, 0x21000, 0x340b_3333),
    ]);
    assert!(inspect(&mismatch).is_err());

    let global = history(vec![
        begin(
            1,
            1,
            0x2c000,
            99,
            mapping("map-global", 0b11 << 13, 0x28000, 7, true, 0x30000, 0x40000),
            0x40000,
            0x40000,
            false,
        ),
        read(2, 0x40000, 0x340e_6666),
        end(3, 1, 1, 0x2c000, 0x340e_6666),
    ]);
    assert!(inspect(&global).is_ok());
}

#[test]
fn reverse_endian_uses_post_translation_bus_address() {
    let value = history(vec![
        begin(
            1,
            1,
            0x10000,
            7,
            mapping("map-re", 0, 0x10000, 7, false, 0x7000, 0x8000),
            0x7000,
            0x7004,
            true,
        ),
        read(2, 0x7004, 0x340f_9abc),
        end(3, 1, 1, 0x10000, 0x340f_9abc),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(report.witnesses[0].translated_paddr.0, 0x7000);
    assert_eq!(report.witnesses[0].bus_paddr.0, 0x7004);

    let mut forged = value;
    forged["events"][0]["bus_paddr"] = json!(0x7000);
    forged["events"][1]["address"] = json!(0x7000);
    assert!(inspect(&forged).is_err());
}

#[test]
fn outside_equal_value_read_does_not_steal_fetch_lineage() {
    let word = 0;
    let value = history(vec![
        read(1, 0xb000, word),
        begin(
            2,
            1,
            0x14000,
            7,
            mapping("map-code", 0, 0x14000, 7, false, 0x9000, 0xa000),
            0x9000,
            0x9000,
            false,
        ),
        read(3, 0x9000, word),
        end(4, 2, 1, 0x14000, word),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(report.outside_fetch_reads, 1);
    assert_eq!(report.witnesses[0].read_ordinal, 3);
}

#[test]
fn missing_ambiguous_or_foreign_in_window_reads_fail_closed() {
    let base_mapping = || mapping("map-a", 0, 0x4000, 7, false, 0x1000, 0x2000);
    let cases = [
        history(vec![
            begin(1, 1, 0x4000, 7, base_mapping(), 0x1000, 0x1000, false),
            end(2, 1, 1, 0x4000, 0x3409_1111),
        ]),
        history(vec![
            begin(1, 1, 0x4000, 7, base_mapping(), 0x1000, 0x1000, false),
            read(2, 0x1000, 0x3409_1111),
            read(3, 0x1000, 0x3409_1111),
            end(4, 1, 1, 0x4000, 0x3409_1111),
        ]),
        history(vec![
            begin(1, 1, 0x4000, 7, base_mapping(), 0x1000, 0x1000, false),
            read(2, 0x2000, 0x3409_1111),
            end(3, 1, 1, 0x4000, 0x3409_1111),
        ]),
        history(vec![
            begin(1, 1, 0x4000, 7, base_mapping(), 0x1000, 0x1000, false),
            read(2, 0x1000, 0x3409_1111),
            end(3, 1, 1, 0x4000, 0x3409_2222),
        ]),
    ];
    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "forgery {index} accepted");
    }
}

#[test]
fn unsupported_or_cacheable_mapping_stays_outside_certificate_scope() {
    let unsupported = history(vec![
        begin(
            1,
            1,
            0x41000,
            7,
            mapping("map-256k", 0b111111 << 13, 0x0, 7, false, 0x1000, 0x2000),
            0x11000,
            0x11000,
            false,
        ),
        read(2, 0x11000, 1),
        end(3, 1, 1, 0x41000, 1),
    ]);
    assert!(inspect(&unsupported).is_err());

    let mut cacheable_mapping = mapping("map-cache", 0, 0x4000, 7, false, 0x1000, 0x2000);
    cacheable_mapping["lo0"]["cca"] = json!(3);
    let cacheable = history(vec![
        begin(1, 1, 0x4000, 7, cacheable_mapping, 0x1000, 0x1000, false),
        read(2, 0x1000, 1),
        end(3, 1, 1, 0x4000, 1),
    ]);
    assert!(inspect(&cacheable).is_err());
}

#[test]
fn malformed_masks_stay_outside_canonical_execution_backed_scope() {
    let value = history(vec![
        begin(
            1,
            1,
            0x21000,
            7,
            mapping(
                "map-normalized",
                0b111 << 13,
                0x20000,
                7,
                false,
                0x10000,
                0x20000,
            ),
            0x11000,
            0x11000,
            false,
        ),
        read(2, 0x11000, 0x340a_2222),
        end(3, 1, 1, 0x21000, 0x340a_2222),
    ]);
    assert!(inspect(&value).is_err());
}

#[test]
fn source_order_and_report_rechecking_resist_deletion_and_forgery() {
    let value = history(vec![
        begin(
            1,
            2,
            0x21000,
            7,
            mapping("map-a", 0b11 << 13, 0x20000, 7, false, 0x10000, 0x20000),
            0x11000,
            0x11000,
            false,
        ),
        read(2, 0x11000, 0x340a_2222),
        end(3, 1, 2, 0x21000, 0x340a_2222),
    ]);
    let bytes = serde_json::to_vec(&value).unwrap();
    let expected = sha256(&bytes);
    let report = tlb_fetch::inspect_tlb_fetch_history(&bytes, &expected).unwrap();
    tlb_fetch::verify_tlb_fetch_report(&report, &bytes, &expected).unwrap();

    let mut reordered = value.clone();
    reordered["events"][1]["ordinal"] = json!(3);
    assert!(inspect(&reordered).is_err());

    let shortened = serde_json::to_vec(&history(vec![])).unwrap();
    assert!(tlb_fetch::inspect_tlb_fetch_history(&shortened, &expected).is_err());

    let mut forged = report.clone();
    forged.witnesses[0].mapping_ref = "equal-value-decoy".into();
    assert!(tlb_fetch::verify_tlb_fetch_report(&forged, &bytes, &expected).is_err());

    let mut forged = report;
    forged.native_complete = true;
    assert!(tlb_fetch::verify_tlb_fetch_report(&forged, &bytes, &expected).is_err());
}
