use plaid_core::{
    rom::sha256,
    sp_dma_egress::{self, SpDmaEgressReport},
};
use serde_json::{Value, json};

fn fixture() -> Value {
    json!({
        "format": sp_dma_egress::FORMAT,
        "events": [
            {"kind":"imem_word_sink","ordinal":1,"region":1,"offset":0x040,"bytes":4,"value":0x11223344u32,"cpu":true},
            {"kind":"imem_word_sink","ordinal":2,"region":1,"offset":0x040,"bytes":4,"value":0x11223344u32,"cpu":true},
            {"kind":"imem_word_sink","ordinal":3,"region":1,"offset":0x044,"bytes":4,"value":0x55667788u32,"cpu":true},
            {"kind":"imem_word_sink","ordinal":4,"region":1,"offset":0x080,"bytes":4,"value":0x11223344u32,"cpu":true},
            {"kind":"imem_word_sink","ordinal":5,"region":1,"offset":0x084,"bytes":4,"value":0x55667788u32,"cpu":true},
            {"kind":"dma_rdram_write","ordinal":6,"region":1,"dma_region":1,"source":0x040,"dma_pbus":0x040,
             "dram":0x1000,"dma_dram":0x1000,"bytes":8,"value":0x1122334455667788u64,"dma_count":1,"dma_skip":8},
            {"kind":"imem_word_sink","ordinal":7,"region":1,"offset":0xff8,"bytes":4,"value":0xaabbccddu32,"cpu":true},
            {"kind":"imem_word_sink","ordinal":8,"region":1,"offset":0xffc,"bytes":4,"value":0xeeff0011u32,"cpu":true},
            {"kind":"imem_word_sink","ordinal":9,"region":1,"offset":0x000,"bytes":4,"value":0x22334455u32,"cpu":true},
            {"kind":"imem_word_sink","ordinal":10,"region":1,"offset":0x004,"bytes":4,"value":0x66778899u32,"cpu":true},
            {"kind":"dma_rdram_write","ordinal":11,"region":1,"dma_region":1,"source":0xff8,"dma_pbus":0xff8,
             "dram":0x2000,"dma_dram":0x2000,"bytes":8,"value":0xaabbccddeeff0011u64,"dma_count":1,"dma_skip":0},
            {"kind":"dma_rdram_write","ordinal":12,"region":1,"dma_region":1,"source":0x000,"dma_pbus":0x000,
             "dram":0x2008,"dma_dram":0x2008,"bytes":8,"value":0x2233445566778899u64,"dma_count":0,"dma_skip":0}
        ]
    })
}

fn inspect(value: &Value) -> Result<SpDmaEgressReport, String> {
    let bytes = serde_json::to_vec(value).unwrap();
    sp_dma_egress::inspect_sp_dma_egress_history(&bytes, &sha256(&bytes))
}

#[test]
fn same_value_writer_and_equal_payload_decoy_keep_causal_identity() {
    let report = inspect(&fixture()).unwrap();
    assert_eq!((report.imem_word_sinks, report.dma_rdram_writes), (9, 3));
    assert_eq!((report.fully_attributed_bytes, report.unknown_source_bytes), (24, 0));
    let first = &report.receipts[0];
    assert_eq!((first.source_region, first.source_offset), (1, 0x040));
    assert_eq!((first.descriptor_count, first.descriptor_skip), (1, 8));
    assert_eq!(
        first.source_bytes.each_ref().map(|byte| byte.writer_ordinal),
        [Some(2), Some(2), Some(2), Some(2), Some(3), Some(3), Some(3), Some(3)]
    );
    assert_eq!(
        first.source_bytes.each_ref().map(|byte| byte.source_offset),
        [0x040, 0x041, 0x042, 0x043, 0x044, 0x045, 0x046, 0x047]
    );
    assert!(
        !report.dma_request_lifecycle_certified
            && !report.imem_mutation_census_certified
            && !report.executable_lifetime_certified
            && !report.hardware_semantics_certified
            && !report.native_complete
    );
}

#[test]
fn wrapped_offset_does_not_change_the_captured_imem_bank() {
    let report = inspect(&fixture()).unwrap();
    let before_wrap = &report.receipts[1];
    let after_wrap = &report.receipts[2];
    assert_eq!((before_wrap.source_region, before_wrap.source_offset), (1, 0xff8));
    assert_eq!((after_wrap.source_region, after_wrap.source_offset), (1, 0x000));
    assert_eq!(
        before_wrap.source_bytes.each_ref().map(|byte| byte.source_offset),
        [0xff8, 0xff9, 0xffa, 0xffb, 0xffc, 0xffd, 0xffe, 0xfff]
    );
    assert_eq!(
        after_wrap.source_bytes.each_ref().map(|byte| byte.source_offset),
        [0, 1, 2, 3, 4, 5, 6, 7]
    );
    assert!(before_wrap.source_bytes.iter().all(|byte| byte.writer_ordinal.is_some()));
    assert!(after_wrap.source_bytes.iter().all(|byte| byte.writer_ordinal.is_some()));
}

#[test]
fn uncaptured_source_bytes_stay_unknown_instead_of_being_value_inferred() {
    let value = json!({
        "format": sp_dma_egress::FORMAT,
        "events": [
            {"kind":"imem_word_sink","ordinal":1,"region":1,"offset":0x100,"bytes":4,"value":0x01020304u32,"cpu":true},
            {"kind":"dma_rdram_write","ordinal":2,"region":1,"dma_region":1,"source":0x100,"dma_pbus":0x100,
             "dram":0x3000,"dma_dram":0x3000,"bytes":8,"value":0x01020304deadbeefu64,"dma_count":0,"dma_skip":0}
        ]
    });
    let report = inspect(&value).unwrap();
    assert_eq!((report.fully_attributed_bytes, report.unknown_source_bytes), (4, 4));
    assert_eq!(
        report.receipts[0]
            .source_bytes
            .each_ref()
            .map(|byte| byte.writer_ordinal),
        [Some(1), Some(1), Some(1), Some(1), None, None, None, None]
    );

    let mut forged = value;
    forged["events"][1]["value"] = json!(0x00020304deadbeefu64);
    assert!(inspect(&forged).is_err(), "known source-lane payload forgery accepted");
}

#[test]
fn descriptor_bank_source_and_chronology_forgeries_fail_closed() {
    let original = fixture();
    let mut cases = Vec::new();

    let mut value = original.clone();
    value["events"][5]["source"] = json!(0x080);
    cases.push(value);

    let mut value = original.clone();
    value["events"][5]["region"] = json!(0);
    cases.push(value);

    let mut value = original.clone();
    value["events"][10]["dma_region"] = json!(0);
    cases.push(value);

    let mut value = original.clone();
    value["events"][11]["source"] = json!(0xff8);
    cases.push(value);

    let mut value = original.clone();
    value["events"][5]["dram"] = json!(0x1008);
    cases.push(value);

    let mut value = original.clone();
    value["events"][6]["ordinal"] = json!(99);
    cases.push(value);

    let mut value = original;
    value["events"][0]["extra"] = json!(0);
    cases.push(value);

    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "forgery {index} accepted");
    }
}

#[test]
fn trusted_source_receipt_and_replayed_report_are_deletion_resistant() {
    let value = fixture();
    let bytes = serde_json::to_vec(&value).unwrap();
    let digest = sha256(&bytes);
    let report = sp_dma_egress::inspect_sp_dma_egress_history(&bytes, &digest).unwrap();
    sp_dma_egress::verify_sp_dma_egress_report(&report, &bytes, &digest).unwrap();

    let mut deleted = value.clone();
    deleted["events"].as_array_mut().unwrap().remove(1);
    for (index, event) in deleted["events"].as_array_mut().unwrap().iter_mut().enumerate() {
        event["ordinal"] = json!(index as u64 + 1);
    }
    let shortened = serde_json::to_vec(&deleted).unwrap();
    assert!(
        sp_dma_egress::inspect_sp_dma_egress_history(&shortened, &digest).is_err(),
        "deleted same-value writer was recertified with a changed source"
    );

    let mut forged = report.clone();
    forged.receipts[0].source_bytes[0].writer_ordinal = Some(4);
    assert!(sp_dma_egress::verify_sp_dma_egress_report(&forged, &bytes, &digest).is_err());

    let mut forged = report;
    forged.native_complete = true;
    assert!(sp_dma_egress::verify_sp_dma_egress_report(&forged, &bytes, &digest).is_err());
}
