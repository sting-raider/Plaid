use plaid_core::{
    rom::sha256,
    rsp_imem_install::{
        RspImemInstallReport, RspImemWriterKind, inspect_rsp_imem_install_history,
        verify_rsp_imem_install_report,
    },
};
use serde_json::{Value, json};

fn fixture_value() -> Value {
    json!({
        "format": "plaid-rsp-imem-install-history-v0",
        "events": [
            {"kind":"promote","ordinal":1,"request":1,"pbus":512,"dram":4096,"length":8,"count":1,"skip":8},
            {"kind":"dma_sink","ordinal":2,"request":1,"pbus":512,"dram":4096,"value":1229782938247303441u64},
            {"kind":"cpu_sink","ordinal":3,"pbus":516,"value":286331153u32},
            {"kind":"dma_sink","ordinal":4,"request":1,"pbus":520,"dram":4112,"value":2459565876494606882u64},
            {"kind":"complete","ordinal":5,"request":1},

            {"kind":"promote","ordinal":6,"request":2,"pbus":768,"dram":8192,"length":16,"count":0,"skip":0},
            {"kind":"dma_sink","ordinal":7,"request":2,"pbus":768,"dram":8192,"value":3689348814741910323u64},
            {"kind":"dma_sink","ordinal":8,"request":2,"pbus":776,"dram":8200,"value":4919131752989213764u64},
            {"kind":"complete","ordinal":9,"request":2},
            {"kind":"promote","ordinal":10,"request":3,"pbus":768,"dram":12288,"length":16,"count":0,"skip":0},
            {"kind":"dma_sink","ordinal":11,"request":3,"pbus":768,"dram":12288,"value":3689348814741910323u64},
            {"kind":"dma_sink","ordinal":12,"request":3,"pbus":776,"dram":12296,"value":4919131752989213764u64},
            {"kind":"complete","ordinal":13,"request":3},

            {"kind":"promote","ordinal":14,"request":4,"pbus":4088,"dram":16384,"length":16,"count":0,"skip":0},
            {"kind":"dma_sink","ordinal":15,"request":4,"pbus":4088,"dram":16384,"value":6148914691236517205u64},
            {"kind":"dma_sink","ordinal":16,"request":4,"pbus":0,"dram":16392,"value":7378697629483820646u64},
            {"kind":"complete","ordinal":17,"request":4},

            {"kind":"promote","ordinal":18,"request":5,"pbus":896,"dram":20480,"length":8,"count":0,"skip":0},
            {"kind":"dma_sink","ordinal":19,"request":5,"pbus":896,"dram":20480,"value":8608480567731124087u64},
            {"kind":"complete","ordinal":20,"request":5},
            {"kind":"promote","ordinal":21,"request":6,"pbus":904,"dram":24576,"length":8,"count":0,"skip":0},
            {"kind":"dma_sink","ordinal":22,"request":6,"pbus":904,"dram":24576,"value":9838263505978427528u64},
            {"kind":"complete","ordinal":23,"request":6}
        ]
    })
}

fn encode(value: &Value) -> Vec<u8> {
    serde_json::to_vec(value).expect("fixture JSON")
}

fn inspect(value: &Value) -> RspImemInstallReport {
    let source = encode(value);
    inspect_rsp_imem_install_history(&source, &sha256(&source)).expect("valid install history")
}

fn owner_generation(report: &RspImemInstallReport, offset: u16) -> Option<u64> {
    report.current_owner_spans.iter().find_map(|span| {
        let end = span.offset + span.bytes;
        (offset >= span.offset && offset < end).then_some(span.generation)
    })
}

fn owner_kind(report: &RspImemInstallReport, offset: u16) -> Option<&RspImemWriterKind> {
    let generation = owner_generation(report, offset)?;
    report
        .writer_effects
        .iter()
        .find(|effect| effect.generation == generation)
        .map(|effect| &effect.kind)
}

#[test]
fn groups_only_measured_dma_effects_and_preserves_latest_byte_writers() {
    let report = inspect(&fixture_value());
    assert_eq!(report.events, 23);
    assert_eq!(
        report.requests.iter().map(|r| r.request).collect::<Vec<_>>(),
        vec![1, 2, 3, 4, 5, 6]
    );
    assert_eq!(report.requests[0].effect_generations.len(), 2);

    for offset in 0x204..0x208 {
        assert_eq!(owner_kind(&report, offset), Some(&RspImemWriterKind::Cpu));
    }
    for offset in (0x200..0x204).chain(0x208..0x210) {
        assert_eq!(
            owner_kind(&report, offset),
            Some(&RspImemWriterKind::Dma { request: 1 })
        );
    }

    for offset in 0x300..0x310 {
        assert_eq!(
            owner_kind(&report, offset),
            Some(&RspImemWriterKind::Dma { request: 3 })
        );
    }
    assert_ne!(
        report.requests[1].effect_generations,
        report.requests[2].effect_generations
    );

    assert_eq!(report.writer_effects[6].offset, 0xff8);
    assert_eq!(report.writer_effects[7].offset, 0x000);
    for offset in 0xff8..0x1000 {
        assert_eq!(
            owner_kind(&report, offset),
            Some(&RspImemWriterKind::Dma { request: 4 })
        );
    }
    for offset in 0x000..0x008 {
        assert_eq!(
            owner_kind(&report, offset),
            Some(&RspImemWriterKind::Dma { request: 4 })
        );
    }

    assert!(!report.source_backing_certified);
    assert!(!report.mutation_coverage_certified);
    assert!(!report.executable_lifetime_certified);
    assert!(!report.rsp_closure_certified);
    assert!(!report.native_complete);
}

#[test]
fn same_value_writes_and_reload_payloads_do_not_collapse_writer_identity() {
    let report = inspect(&fixture_value());
    let first_dma = &report.writer_effects[0];
    let cpu = &report.writer_effects[1];
    assert_eq!((first_dma.value >> 32) as u32, cpu.value as u32);
    assert_ne!(first_dma.generation, cpu.generation);

    assert_eq!(report.writer_effects[3].value, report.writer_effects[5].value);
    assert_eq!(report.writer_effects[4].value, report.writer_effects[6].value);
    assert_ne!(report.requests[1].request, report.requests[2].request);
    assert_ne!(
        report.requests[1].effect_generations,
        report.requests[2].effect_generations
    );
}

#[test]
fn rejects_request_identity_completion_order_and_schema_forgeries() {
    let original = fixture_value();

    let mut wrong_owner = original.clone();
    wrong_owner["events"][10]["request"] = json!(2);
    let source = encode(&wrong_owner);
    assert!(inspect_rsp_imem_install_history(&source, &sha256(&source)).is_err());

    let mut reused_request = original.clone();
    reused_request["events"][9]["request"] = json!(1);
    let source = encode(&reused_request);
    assert!(inspect_rsp_imem_install_history(&source, &sha256(&source)).is_err());

    let mut missing_completion = original.clone();
    missing_completion["events"].as_array_mut().expect("events").pop();
    let source = encode(&missing_completion);
    assert!(inspect_rsp_imem_install_history(&source, &sha256(&source)).is_err());

    let mut reordered = original.clone();
    reordered["events"][1]["ordinal"] = json!(99);
    let source = encode(&reordered);
    assert!(inspect_rsp_imem_install_history(&source, &sha256(&source)).is_err());

    let mut forged_cpu_owner = original.clone();
    forged_cpu_owner["events"][2]["request"] = json!(1);
    let source = encode(&forged_cpu_owner);
    assert!(inspect_rsp_imem_install_history(&source, &sha256(&source)).is_err());

    let mut invalid_endpoint = original.clone();
    invalid_endpoint["events"][1]["pbus"] = json!(4095);
    let source = encode(&invalid_endpoint);
    assert!(inspect_rsp_imem_install_history(&source, &sha256(&source)).is_err());
}

#[test]
fn rejects_source_and_report_tampering_and_empty_completed_requests() {
    let original = fixture_value();
    let source = encode(&original);
    let digest = sha256(&source);
    let report = inspect_rsp_imem_install_history(&source, &digest).expect("valid source");

    let mut tampered_source = original.clone();
    tampered_source["events"][1]["value"] = json!(0u64);
    let tampered_source = encode(&tampered_source);
    assert!(inspect_rsp_imem_install_history(&tampered_source, &digest).is_err());

    let mut tampered_report = report.clone();
    tampered_report.native_complete = true;
    assert!(verify_rsp_imem_install_report(&tampered_report, &source, &digest).is_err());
    verify_rsp_imem_install_report(&report, &source, &digest).expect("report recheck");

    let empty = json!({
        "format": "plaid-rsp-imem-install-history-v0",
        "events": [
            {"kind":"promote","ordinal":1,"request":1,"pbus":0,"dram":0,"length":8,"count":0,"skip":0},
            {"kind":"complete","ordinal":2,"request":1}
        ]
    });
    let source = encode(&empty);
    assert!(inspect_rsp_imem_install_history(&source, &sha256(&source)).is_err());
}
