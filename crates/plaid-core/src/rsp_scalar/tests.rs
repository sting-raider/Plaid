use super::*;
use serde_json::Value;

fn i(op: u32, rs: u8, rt: u8, immediate: i16) -> u32 {
    (op << 26) | (u32::from(rs) << 21) | (u32::from(rt) << 16) | u32::from(immediate as u16)
}

fn r(rs: u8, rt: u8, rd: u8, funct: u32) -> u32 {
    (u32::from(rs) << 21) | (u32::from(rt) << 16) | (u32::from(rd) << 11) | funct
}

fn inst(meta: (bool, u64, u64, u32, u32), values: [u32; 3]) -> Event {
    let (begin, ordinal, context, pc, word) = meta;
    let [rs_value, rt_value, rd_value] = values;
    let (_, rs, rt, rd, _, _) = decode(word);
    Event::Instruction {
        begin,
        ordinal,
        context,
        phase: 1,
        pc,
        word,
        rs,
        rt,
        rd,
        rs_value,
        rt_value,
        rd_value,
        halted: false,
    }
}

fn sink(ordinal: u64, context: u64, pc: u32, offset: u32, value: u8) -> Event {
    Event::DmemWrite {
        ordinal,
        context,
        phase: 1,
        pc,
        offset,
        bytes: 1,
        value: u32::from(value),
    }
}

fn source(memory: Vec<u8>, events: Vec<Event>) -> Vec<u8> {
    serde_json::to_vec(&History {
        format: FORMAT.into(),
        phases: vec![Phase {
            phase: 1,
            initial_dmem: memory,
        }],
        events,
    })
    .unwrap()
}

fn inspect(source: &[u8]) -> Result<RspScalarLineageReport, String> {
    inspect_rsp_scalar_history(source, &sha256(source))
}

fn equal_value_history() -> Vec<u8> {
    let mut memory = vec![0; 4096];
    memory[0x100..0x104].copy_from_slice(&0x1122_3344u32.to_be_bytes());
    memory[0x104..0x108].copy_from_slice(&0x1122_3344u32.to_be_bytes());
    let a = i(0x23, 1, 2, 0);
    let b = i(0x23, 1, 2, 4);
    let unrelated = i(0x0d, 0, 4, 7);
    let sw = i(0x2b, 3, 2, 0);
    source(
        memory,
        vec![
            inst((true, 1, 1, 0, a), [0x100, 0, 0]),
            inst((false, 2, 1, 0, a), [0x100, 0x1122_3344, 0]),
            inst((true, 3, 3, 4, b), [0x100, 0x1122_3344, 0]),
            inst((false, 4, 3, 4, b), [0x100, 0x1122_3344, 0]),
            inst((true, 5, 5, 8, unrelated), [0, 0, 0]),
            inst((false, 6, 5, 8, unrelated), [0, 7, 0]),
            inst((true, 7, 7, 12, sw), [0x300, 0x1122_3344, 0]),
            sink(8, 7, 12, 0x300, 0x11),
            sink(9, 7, 12, 0x301, 0x22),
            sink(10, 7, 12, 0x302, 0x33),
            sink(11, 7, 12, 0x303, 0x44),
            inst((false, 12, 7, 12, sw), [0x300, 0x1122_3344, 0]),
        ],
    )
}

#[test]
fn equal_payload_uses_fresh_generation_not_value_identity() {
    let report = inspect(&equal_value_history()).unwrap();
    assert_eq!(report.load_generations, 2);
    assert_eq!(report.stores[0].producer_load_context, Some(3));
    assert_eq!(report.stores[0].producer_load_generation, Some(2));
    assert_eq!(
        report.stores[0]
            .bytes
            .iter()
            .map(|byte| byte.source.unwrap().offset)
            .collect::<Vec<_>>(),
        vec![0x104, 0x105, 0x106, 0x107]
    );
    assert!(!report.primitive_read_coverage_certified);
    assert!(!report.gpr_writer_coverage_certified);
    assert!(!report.source_storage_ancestry_certified);
    assert!(!report.mutation_coverage_certified);
    assert!(!report.executable_lifetime_certified);
    assert!(!report.native_complete);
}

#[test]
fn same_source_reload_still_mints_a_fresh_generation() {
    let mut memory = vec![0; 4096];
    memory[0x120..0x124].copy_from_slice(&0xaabb_ccddu32.to_be_bytes());
    let lw = i(0x23, 1, 2, 0);
    let sw = i(0x2b, 3, 2, 0);
    let source = source(
        memory,
        vec![
            inst((true, 1, 1, 0, lw), [0x120, 0, 0]),
            inst((false, 2, 1, 0, lw), [0x120, 0xaabb_ccdd, 0]),
            inst((true, 3, 3, 4, lw), [0x120, 0xaabb_ccdd, 0]),
            inst((false, 4, 3, 4, lw), [0x120, 0xaabb_ccdd, 0]),
            inst((true, 5, 5, 8, sw), [0x240, 0xaabb_ccdd, 0]),
            sink(6, 5, 8, 0x240, 0xaa),
            sink(7, 5, 8, 0x241, 0xbb),
            sink(8, 5, 8, 0x242, 0xcc),
            sink(9, 5, 8, 0x243, 0xdd),
            inst((false, 10, 5, 8, sw), [0x240, 0xaabb_ccdd, 0]),
        ],
    );
    let report = inspect(&source).unwrap();
    assert_eq!(report.load_generations, 2);
    assert_eq!(report.stores[0].producer_load_context, Some(3));
    assert_eq!(report.stores[0].producer_load_generation, Some(2));
    assert_eq!(
        report.stores[0]
            .bytes
            .iter()
            .map(|byte| byte.source.unwrap().offset)
            .collect::<Vec<_>>(),
        vec![0x120, 0x121, 0x122, 0x123]
    );
}

#[test]
fn same_value_ori_and_addu_cut_lineage() {
    for writer in [i(0x0d, 0, 2, 0x1234), r(2, 0, 2, 0x21)] {
        let mut memory = vec![0; 4096];
        memory[0x80..0x84].copy_from_slice(&0x0000_1234u32.to_be_bytes());
        let lw = i(0x23, 1, 2, 0);
        let sw = i(0x2b, 3, 2, 0);
        let writer_values = if writer >> 26 == 0 {
            [0x1234, 0, 0x1234]
        } else {
            [0, 0x1234, 0x1234]
        };
        let source = source(
            memory,
            vec![
                inst((true, 1, 1, 0, lw), [0x80, 0, 0]),
                inst((false, 2, 1, 0, lw), [0x80, 0x1234, 0]),
                inst((true, 3, 3, 4, writer), writer_values),
                inst((false, 4, 3, 4, writer), writer_values),
                inst((true, 5, 5, 8, sw), [0x200, 0x1234, 0]),
                sink(6, 5, 8, 0x200, 0),
                sink(7, 5, 8, 0x201, 0),
                sink(8, 5, 8, 0x202, 0x12),
                sink(9, 5, 8, 0x203, 0x34),
                inst((false, 10, 5, 8, sw), [0x200, 0x1234, 0]),
            ],
        );
        let report = inspect(&source).unwrap();
        assert_eq!(report.stores[0].producer_load_generation, None);
        assert!(
            report.stores[0]
                .bytes
                .iter()
                .all(|byte| byte.source.is_none())
        );
    }
}

#[test]
fn wrap_and_bit12_alias_preserve_exact_lanes() {
    let mut memory = vec![0; 4096];
    memory[0xffe] = 0xa1;
    memory[0xfff] = 0xb2;
    memory[0] = 0xc3;
    memory[1] = 0xd4;
    let lw = i(0x23, 1, 2, 0);
    let sw = i(0x2b, 3, 2, 0);
    let source = source(
        memory,
        vec![
            inst((true, 1, 1, 0, lw), [0x1ffe, 0, 0]),
            inst((false, 2, 1, 0, lw), [0x1ffe, 0xa1b2_c3d4, 0]),
            inst((true, 3, 3, 4, sw), [0x200, 0xa1b2_c3d4, 0]),
            sink(4, 3, 4, 0x200, 0xa1),
            sink(5, 3, 4, 0x201, 0xb2),
            sink(6, 3, 4, 0x202, 0xc3),
            sink(7, 3, 4, 0x203, 0xd4),
            inst((false, 8, 3, 4, sw), [0x200, 0xa1b2_c3d4, 0]),
        ],
    );
    let report = inspect(&source).unwrap();
    assert_eq!(
        report.stores[0]
            .bytes
            .iter()
            .map(|byte| byte.source.unwrap().offset)
            .collect::<Vec<_>>(),
        vec![0xffe, 0xfff, 0, 1]
    );
}

#[test]
fn malformed_or_partial_histories_fail_closed() {
    let valid = equal_value_history();
    let mut missing: Value = serde_json::from_slice(&valid).unwrap();
    missing["events"].as_array_mut().unwrap().remove(9);
    for (index, event) in missing["events"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .enumerate()
    {
        event["ordinal"] = Value::from(index as u64 + 1);
    }
    assert!(inspect(&serde_json::to_vec(&missing).unwrap()).is_err());

    let mut selector: Value = serde_json::from_slice(&valid).unwrap();
    selector["events"][0]["rs"] = Value::from(31);
    assert!(inspect(&serde_json::to_vec(&selector).unwrap()).is_err());

    let mut bad_load_result: Value = serde_json::from_slice(&valid).unwrap();
    bad_load_result["events"][1]["rt_value"] = Value::from(0x1122_3345u32);
    assert!(inspect(&serde_json::to_vec(&bad_load_result).unwrap()).is_err());

    let mut duplicate: Value = serde_json::from_slice(&valid).unwrap();
    duplicate["events"][1]["ordinal"] = Value::from(1);
    assert!(inspect(&serde_json::to_vec(&duplicate).unwrap()).is_err());
}

#[test]
fn source_hash_and_report_recheck_bind_every_field() {
    let source = equal_value_history();
    let digest = sha256(&source);
    assert!(inspect_rsp_scalar_history(&source, "00").is_err());
    let mut report = inspect_rsp_scalar_history(&source, &digest).unwrap();
    report.stores[0].producer_load_generation = Some(1);
    assert!(verify_rsp_scalar_report(&report, &source, &digest).is_err());

    let mut reordered: Value = serde_json::from_slice(&source).unwrap();
    reordered["events"].as_array_mut().unwrap().swap(0, 2);
    let reordered = serde_json::to_vec(&reordered).unwrap();
    assert!(inspect_rsp_scalar_history(&reordered, &digest).is_err());
}
