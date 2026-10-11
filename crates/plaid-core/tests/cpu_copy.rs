use plaid_core::{
    cpu_copy::{self, CpuCopyReport, LoadKind},
    rom::sha256,
};
use serde_json::{Value, json};

fn fixture(transform: Option<u16>, unsigned: bool, decoy: bool) -> Value {
    let mut instructions = Vec::new();
    let mut effects = Vec::new();
    let mut regs = [0u64; 32];
    regs[16] = 0xffff_ffff_a000_1000;
    regs[17] = 0xffff_ffff_a000_2000;
    let mut ordinal = 1u64;
    let mut pc = 0xffff_ffff_a000_6000u64;
    let mut loaded = regs;
    let mut append = |word: u32, after: [u64; 32], effect: Option<(bool, u32, u32)>| {
        let context = ordinal;
        instructions.push(json!({"begin":true,"ordinal":ordinal,"context":context,
            "phase":1,"pc":pc,"word":word,"gpr":regs}));
        ordinal += 1;
        if let Some((write, address, value)) = effect {
            effects.push(
                json!({"ordinal":ordinal,"context":context,"phase":1,"pc":pc,
                "write":write,"address":address,"bytes":4,"uncached_cpu":true,"value":value}),
            );
            ordinal += 1;
        }
        instructions.push(json!({"begin":false,"ordinal":ordinal,"context":context,
            "phase":1,"pc":pc,"word":word,"gpr":after}));
        ordinal += 1;
        pc += 4;
        regs = after;
    };
    loaded[8] = if unsigned {
        0x89ab_cdef
    } else {
        0xffff_ffff_89ab_cdef
    };
    append(
        if unsigned { 0x9e08_0000 } else { 0x8e08_0000 },
        loaded,
        Some((false, 0x1000, 0x89ab_cdef)),
    );
    if decoy {
        loaded[9] = 0xffff_ffff_89ab_cdef;
        append(0x8e09_0100, loaded, Some((false, 0x1100, 0x89ab_cdef)));
    }
    if let Some(mask) = transform {
        loaded[8] ^= u64::from(mask);
        append(0x3908_0000 | u32::from(mask), loaded, None);
    }
    append(0xae28_0000, loaded, Some((true, 0x2000, loaded[8] as u32)));
    json!({"format":cpu_copy::FORMAT,"instruction_events":instructions,"scalar_events":effects})
}
fn inspect(value: &Value) -> Result<CpuCopyReport, String> {
    let bytes = serde_json::to_vec(value).unwrap();
    cpu_copy::inspect_cpu_copy_history(&bytes, &sha256(&bytes))
}
#[test]
fn signed_unsigned_and_zero_transform_keep_distinct_definitions() {
    for unsigned in [false, true] {
        for mask in [None, Some(0), Some(0xf00f)] {
            let report = inspect(&fixture(mask, unsigned, false)).unwrap();
            let w = &report.witnesses[0];
            assert_eq!(report.witnesses.len(), 1);
            assert_eq!(
                w.load_kind,
                if unsigned {
                    LoadKind::Lwu
                } else {
                    LoadKind::Lw
                }
            );
            assert_eq!(w.xor_imm, mask);
            assert_eq!(w.transform_context.is_some(), mask.is_some());
            assert_eq!(
                (w.source.0, w.destination.0, w.read_ordinal),
                (0x1000, 0x2000, 2)
            );
            assert_eq!(w.result_word, 0x89ab_cdef ^ u32::from(mask.unwrap_or(0)));
            assert!(
                !report.native_complete
                    && !report.executable_lifetime_certified
                    && !report.mutation_coverage_certified
                    && !report.source_origin_certified
            );
        }
    }
}
#[test]
fn nearest_equal_read_cannot_replace_another_registers_definition() {
    assert!(
        inspect(&fixture(None, false, true))
            .unwrap()
            .witnesses
            .is_empty()
    );
    assert!(
        inspect(&fixture(Some(0xff), false, true))
            .unwrap()
            .witnesses
            .is_empty()
    );
}
#[test]
fn continuity_control_sink_and_decoded_width_forgeries_reject() {
    let original = fixture(Some(0xff), false, false);
    let mut cases = Vec::new();
    let mut v = original.clone();
    for e in v["instruction_events"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .skip(2)
    {
        e["gpr"][31] = json!(1u64 << 40);
    }
    cases.push(v);
    let mut v = original.clone();
    for e in v["instruction_events"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .skip(2)
    {
        e["pc"] = json!(e["pc"].as_u64().unwrap() + 0x100);
    }
    cases.push(v);
    let mut v = original.clone();
    v["scalar_events"][0]["address"] = json!(0x1100);
    cases.push(v);
    let mut v = original.clone();
    v["scalar_events"][0]["uncached_cpu"] = json!(false);
    cases.push(v);
    let mut v = original.clone();
    v["scalar_events"][0]["context"] = json!(0);
    cases.push(v);
    let mut v = original.clone();
    v["scalar_events"][0]["bytes"] = json!(8);
    cases.push(v);
    let mut v = original.clone();
    v["scalar_events"][0]["value"] = json!(1u64 << 32);
    cases.push(v);
    let mut v = original.clone();
    v["scalar_events"][0]["write"] = json!(0);
    cases.push(v);
    let mut v = original.clone();
    v["instruction_events"][2]["word"] = json!(0x390800ffu64 + (1u64 << 32));
    cases.push(v);
    let mut v = original.clone();
    v["instruction_events"].as_array_mut().unwrap().pop();
    cases.push(v);
    let mut v = original.clone();
    v["scalar_events"][0]["extra"] = json!(0);
    cases.push(v);
    for (n, v) in cases.iter().enumerate() {
        assert!(inspect(v).is_err(), "forgery {n} accepted");
    }
}
#[test]
fn complete_source_and_report_cannot_be_deleted_or_self_recertified() {
    let value = fixture(Some(0), false, false);
    let bytes = serde_json::to_vec(&value).unwrap();
    let expected = sha256(&bytes);
    let report = cpu_copy::inspect_cpu_copy_history(&bytes, &expected).unwrap();
    cpu_copy::verify_cpu_copy_report(&report, &bytes, &expected).unwrap();
    let mut deleted = value;
    deleted["instruction_events"] = json!([]);
    deleted["scalar_events"] = json!([]);
    let shortened = serde_json::to_vec(&deleted).unwrap();
    assert!(cpu_copy::inspect_cpu_copy_history(&shortened, &expected).is_err());
    let mut forged = report.clone();
    forged.witnesses.clear();
    assert!(cpu_copy::verify_cpu_copy_report(&forged, &bytes, &expected).is_err());
    let mut forged = report;
    forged.native_complete = true;
    assert!(cpu_copy::verify_cpu_copy_report(&forged, &bytes, &expected).is_err());
}

#[test]
fn zero_register_failed_reads_and_segment_boundaries_supply_no_copy() {
    let mut zero = fixture(None, false, false);
    for event in zero["instruction_events"].as_array_mut().unwrap() {
        event["gpr"][8] = json!(0);
        if event["context"] == 1 {
            event["word"] = json!(0x8e000000u32);
        }
    }
    zero["scalar_events"][1]["value"] = json!(0);
    assert!(inspect(&zero).unwrap().witnesses.is_empty());

    let mut failed = fixture(None, false, false);
    failed["scalar_events"].as_array_mut().unwrap().remove(0);
    for field in ["instruction_events", "scalar_events"] {
        for event in failed[field].as_array_mut().unwrap() {
            if event["ordinal"].as_u64().unwrap() > 2 {
                event["ordinal"] = json!(event["ordinal"].as_u64().unwrap() - 1);
            }
            if event["context"].as_u64().unwrap() > 2 {
                event["context"] = json!(event["context"].as_u64().unwrap() - 1);
            }
            if field == "instruction_events" {
                event["gpr"][8] = json!(0);
            }
        }
    }
    failed["scalar_events"][0]["value"] = json!(0);
    assert!(inspect(&failed).unwrap().witnesses.is_empty());

    let mut segmented = fixture(None, false, false);
    for field in ["instruction_events", "scalar_events"] {
        for event in segmented[field].as_array_mut().unwrap() {
            if event["context"] == 4 {
                event["phase"] = json!(2);
            }
        }
    }
    assert!(inspect(&segmented).unwrap().witnesses.is_empty());
}

#[test]
fn big_endian_byte_expressions_preserve_zero_transform_and_recheck_every_lane() {
    let value = fixture(Some(0xf00f), false, false);
    let bytes = serde_json::to_vec(&value).unwrap();
    let digest = sha256(&bytes);
    let report = cpu_copy::inspect_cpu_copy_history(&bytes, &digest).unwrap();
    let expression = &report.witnesses[0].byte_expr;
    assert_eq!(expression.each_ref().map(|e| e.xor), [0, 0, 0xf0, 0x0f]);
    assert_eq!(
        expression.each_ref().map(|e| e.source.0),
        [0x1000, 0x1001, 0x1002, 0x1003]
    );
    assert_eq!(
        expression.each_ref().map(|e| e.destination.0),
        [0x2000, 0x2001, 0x2002, 0x2003]
    );
    for lane in 0..4 {
        let mut forged = report.clone();
        forged.witnesses[0].byte_expr[lane].source.0 ^= 4;
        assert!(cpu_copy::verify_cpu_copy_report(&forged, &bytes, &digest).is_err());
        let mut forged = report.clone();
        forged.witnesses[0].byte_expr[lane].xor ^= 1;
        assert!(cpu_copy::verify_cpu_copy_report(&forged, &bytes, &digest).is_err());
    }
    let zero = inspect(&fixture(Some(0), false, false)).unwrap();
    let plain = inspect(&fixture(None, false, false)).unwrap();
    assert_eq!(zero.witnesses[0].byte_expr, plain.witnesses[0].byte_expr);
    assert_ne!(
        zero.witnesses[0].transform_context,
        plain.witnesses[0].transform_context
    );
}
