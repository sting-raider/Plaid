use plaid_core::{
    cop1_lineage::{self, Cop1LineageReport, FprByteOrigin, FprWriteKind},
    rom::sha256,
};
use serde_json::{Value, json};

const WORD: u64 = 0x1021_3243;
const DUAL_LOW: u64 = 0x5566_7788;

#[test]
fn normalized_completed_store_composes_exact_mixed_fpr_byte_origins() {
    use plaid_core::{
        cpu_mutation::{CompletedCop1StoreEffect, CpuMutationDomain, verify_cop1_store_effect},
        program::{GuestVirtualAddr, PhysicalAddr},
    };
    let value = history(vec![
        read(1, 1, 1, 0x4000, 4, WORD),
        fpr_write(2, 1, 1, "lwc1", 1, false, 0, &[0, 1, 2, 3], WORD, Some(1)),
        store(
            3,
            3,
            3,
            "sdc1",
            0,
            false,
            0,
            &[0, 1, 2, 3, 4, 5, 6, 7],
            0x5000,
            8,
            (WORD << 32) | DUAL_LOW,
        ),
    ]);
    let source = serde_json::to_vec(&value).unwrap();
    let digest = sha256(&source);
    let mut gpr = [0u64; 32];
    gpr[16] = 0xffff_ffff_a000_5000;
    let mut fprs: [u64; 32] = initial_fprs().try_into().unwrap();
    fprs[0] = (WORD << 32) | DUAL_LOW;
    let effect = CompletedCop1StoreEffect {
        effect_ordinal: 3,
        virtual_destination: GuestVirtualAddr(gpr[16]),
        physical_destination: PhysicalAddr(0x5000),
        domain: CpuMutationDomain::Backing,
        payload: fprs[0].to_be_bytes().to_vec(),
    };
    let word = (0x3du32 << 26) | (16 << 21);
    assert!(verify_cop1_store_effect(word, &gpr, &fprs, false, false, Some(&effect)).is_err());
    let witness = verify_cop1_store_effect(word, &gpr, &fprs, false, true, Some(&effect))
        .unwrap()
        .unwrap();
    assert_eq!(witness.effect_ordinal, 3);
    let input = cop1_lineage::Cop1MutationContext {
        instruction_word: word,
        gpr,
        raw_fprs: fprs,
        fr: false,
        cu1: true,
        effect,
    };
    let report =
        cop1_lineage::compose_cop1_mutation_history(&source, &digest, std::slice::from_ref(&input))
            .unwrap();
    assert_eq!(report.lineage.stores[0].byte_origins.len(), 8);
    assert!(matches!(
        report.lineage.stores[0].byte_origins[0],
        FprByteOrigin::RdramRead { .. }
    ));
    assert!(matches!(
        report.lineage.stores[0].byte_origins[4],
        FprByteOrigin::Initial { .. }
    ));
    assert!(!report.decoded_context_ancestry_certified);
    assert!(!report.mutation_census_certified);
    cop1_lineage::verify_cop1_mutation_lineage_report(
        &report,
        &source,
        &digest,
        std::slice::from_ref(&input),
    )
    .unwrap();
    assert!(cop1_lineage::compose_cop1_mutation_history(&source, &digest, &[]).is_err());
    assert!(
        cop1_lineage::compose_cop1_mutation_history(
            &source,
            &digest,
            &[input.clone(), input.clone()]
        )
        .is_err()
    );
    for change in 0..7 {
        let mut forged = input.clone();
        match change {
            0 => forged.effect.effect_ordinal = 2,
            1 => forged.raw_fprs[1] ^= 1,
            2 => forged.instruction_word = (0x39u32 << 26) | (16 << 21),
            3 => forged.effect.domain = CpuMutationDomain::CacheResident,
            4 => forged.effect.virtual_destination = GuestVirtualAddr(0x8000_5000),
            5 => forged.cu1 = false,
            _ => forged.effect.payload[0] ^= 1,
        }
        assert!(
            cop1_lineage::compose_cop1_mutation_history(&source, &digest, &[forged]).is_err(),
            "{change}"
        );
    }
    let mut forged = report.clone();
    forged.lineage.stores[0].byte_origins.swap(0, 4);
    assert!(
        cop1_lineage::verify_cop1_mutation_lineage_report(&forged, &source, &digest, &[input])
            .is_err()
    );
}

#[test]
fn source_event_envelope_rejects_unknown_fields() {
    let mut value = history(vec![failed_load(1, 1)]);
    value["events"][0]["native_complete"] = json!(true);
    assert!(inspect(&value).is_err());
}

fn initial_fprs() -> Vec<u64> {
    let mut values = (0..32)
        .map(|index| 0x7000_0000_0000_0000u64 + index)
        .collect::<Vec<_>>();
    values[0] = (WORD << 32) | DUAL_LOW;
    values[1] = 0x99aa_bbcc_1021_3243;
    values
}

fn read(ordinal: u64, context: u64, phase: u32, address: u32, bytes: u32, value: u64) -> Value {
    json!({
        "kind":"completed_read",
        "event":{
            "ordinal":ordinal,"context":context,"phase":phase,"address":address,
            "bytes":bytes,"uncached_cpu":true,"value":value
        }
    })
}

#[allow(clippy::too_many_arguments)]
fn fpr_write(
    ordinal: u64,
    context: u64,
    phase: u32,
    operation: &str,
    architectural_fpr: u8,
    fr: bool,
    physical_fpr: u8,
    slots: &[u8],
    value: u64,
    source_read_ordinal: Option<u64>,
) -> Value {
    json!({
        "kind":"fpr_write",
        "event":{
            "ordinal":ordinal,"context":context,"phase":phase,"operation":operation,
            "architectural_fpr":architectural_fpr,"fr":fr,"physical_fpr":physical_fpr,
            "slots":slots,"value":value,"source_read_ordinal":source_read_ordinal
        }
    })
}

#[allow(clippy::too_many_arguments)]
fn store(
    ordinal: u64,
    context: u64,
    phase: u32,
    operation: &str,
    architectural_fpr: u8,
    fr: bool,
    physical_fpr: u8,
    slots: &[u8],
    destination: u32,
    bytes: u32,
    value: u64,
) -> Value {
    json!({
        "kind":"store",
        "event":{
            "ordinal":ordinal,"context":context,"phase":phase,"operation":operation,
            "architectural_fpr":architectural_fpr,"fr":fr,"physical_fpr":physical_fpr,
            "slots":slots,"destination":destination,"bytes":bytes,"uncached_cpu":true,
            "value":value
        }
    })
}

fn failed_load(ordinal: u64, context: u64) -> Value {
    json!({
        "kind":"failed_load",
        "event":{
            "ordinal":ordinal,"context":context,"phase":1,"operation":"lwc1",
            "architectural_fpr":1,"fr":false,"reason":"tlb_miss"
        }
    })
}

fn history(events: Vec<Value>) -> Value {
    json!({
        "format":cop1_lineage::FORMAT,
        "initial_fprs":initial_fprs(),
        "events":events
    })
}

fn inspect(value: &Value) -> Result<Cop1LineageReport, String> {
    let bytes = serde_json::to_vec(value).unwrap();
    cop1_lineage::inspect_cop1_lineage_history(&bytes, &sha256(&bytes))
}

#[test]
fn mixed_width_store_preserves_loaded_and_initial_byte_generations() {
    let value = history(vec![
        read(1, 1, 1, 0x4000, 4, WORD),
        fpr_write(2, 1, 1, "lwc1", 1, false, 0, &[0, 1, 2, 3], WORD, Some(1)),
        store(
            3,
            3,
            3,
            "sdc1",
            0,
            false,
            0,
            &[0, 1, 2, 3, 4, 5, 6, 7],
            0x5000,
            8,
            (WORD << 32) | DUAL_LOW,
        ),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(
        (
            report.completed_reads,
            report.fpr_writes,
            report.stores.len()
        ),
        (1, 1, 1)
    );
    let origins = &report.stores[0].byte_origins;
    for (lane, origin) in origins[..4].iter().enumerate() {
        match origin {
            FprByteOrigin::RdramRead {
                read_ordinal,
                fpr_write_ordinal,
                fr,
                source,
                source_byte,
            } => {
                assert_eq!(*read_ordinal, 1);
                assert_eq!(*fpr_write_ordinal, 2);
                assert!(!fr);
                assert_eq!(source.0, 0x4000 + lane as u32);
                assert_eq!(usize::from(*source_byte), lane);
            }
            other => panic!("loaded byte {lane} lost lineage: {other:?}"),
        }
    }
    for (slot, origin) in origins[4..].iter().enumerate() {
        assert_eq!(
            origin,
            &FprByteOrigin::Initial {
                physical_fpr: 0,
                slot: (slot + 4) as u8,
            }
        );
    }
    assert!(
        !report.rdram_source_ancestry_certified
            && !report.fpr_writer_census_certified
            && !report.executable_lifetime_certified
            && !report.native_complete
    );
}

#[test]
fn same_value_mtc1_overwrite_replaces_load_origin() {
    let value = history(vec![
        read(1, 1, 1, 0x4000, 4, WORD),
        fpr_write(2, 1, 1, "lwc1", 1, false, 0, &[0, 1, 2, 3], WORD, Some(1)),
        fpr_write(3, 2, 2, "mtc1", 1, false, 0, &[0, 1, 2, 3], WORD, None),
        store(4, 3, 3, "swc1", 1, false, 0, &[0, 1, 2, 3], 0x5000, 4, WORD),
    ]);
    let report = inspect(&value).unwrap();
    assert!(report.stores[0].byte_origins.iter().all(|origin| matches!(
        origin,
        FprByteOrigin::CapturedWriter {
            writer_ordinal: 3,
            operation: FprWriteKind::Mtc1,
            fr: false,
            ..
        }
    )));
}

#[test]
fn equal_payload_and_fr_metadata_cannot_select_a_different_physical_lane() {
    let value = history(vec![
        read(1, 1, 1, 0x4000, 4, WORD),
        fpr_write(2, 1, 1, "lwc1", 1, false, 0, &[0, 1, 2, 3], WORD, Some(1)),
        store(3, 3, 3, "swc1", 1, true, 1, &[4, 5, 6, 7], 0x5000, 4, WORD),
    ]);
    let report = inspect(&value).unwrap();
    assert!(report.stores[0].byte_origins.iter().all(|origin| matches!(
        origin,
        FprByteOrigin::Initial {
            physical_fpr: 1,
            ..
        }
    )));
}

#[test]
fn failed_load_is_recorded_but_mints_no_fpr_generation() {
    let value = history(vec![
        failed_load(1, 1),
        store(2, 2, 2, "swc1", 1, true, 1, &[4, 5, 6, 7], 0x5000, 4, WORD),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(
        (
            report.failed_loads,
            report.completed_reads,
            report.fpr_writes
        ),
        (1, 0, 0)
    );
    assert!(
        report.stores[0]
            .byte_origins
            .iter()
            .all(|origin| matches!(origin, FprByteOrigin::Initial { .. }))
    );
}

#[test]
fn load_requires_its_exact_completed_read_context() {
    let mut missing = history(vec![fpr_write(
        1,
        1,
        1,
        "lwc1",
        0,
        true,
        0,
        &[4, 5, 6, 7],
        WORD,
        None,
    )]);
    assert!(inspect(&missing).is_err());

    missing = history(vec![
        read(1, 1, 1, 0x4000, 4, WORD),
        fpr_write(2, 2, 1, "lwc1", 0, true, 0, &[4, 5, 6, 7], WORD, Some(1)),
    ]);
    assert!(inspect(&missing).is_err());
}

#[test]
fn lane_shape_payload_read_reuse_and_ordinal_forgeries_reject() {
    let original = history(vec![
        read(1, 1, 1, 0x4000, 4, WORD),
        fpr_write(2, 1, 1, "lwc1", 0, true, 0, &[4, 5, 6, 7], WORD, Some(1)),
        store(3, 3, 3, "swc1", 0, true, 0, &[4, 5, 6, 7], 0x5000, 4, WORD),
    ]);
    let mut cases = Vec::new();
    let mut value = original.clone();
    value["events"][1]["event"]["slots"] = json!([3, 4, 5, 6]);
    cases.push(value);
    let mut value = original.clone();
    value["events"][1]["event"]["value"] = json!(WORD ^ 1);
    cases.push(value);
    let mut value = original.clone();
    value["events"][2]["event"]["value"] = json!(WORD ^ 1);
    cases.push(value);
    let mut value = original.clone();
    value["events"][2]["event"]["ordinal"] = json!(4);
    cases.push(value);
    let mut value = original.clone();
    value["events"].as_array_mut().unwrap().remove(0);
    cases.push(value);
    let mut value = original.clone();
    value["events"].as_array_mut().unwrap().insert(
        2,
        fpr_write(3, 1, 1, "lwc1", 0, true, 0, &[4, 5, 6, 7], WORD, Some(1)),
    );
    value["events"][3]["event"]["ordinal"] = json!(4);
    cases.push(value);
    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "forgery {index} accepted");
    }
}

#[test]
fn complete_source_receipt_and_report_recheck_resist_deletion_and_forgery() {
    let value = history(vec![
        read(1, 1, 1, 0x4000, 4, WORD),
        fpr_write(2, 1, 1, "lwc1", 0, true, 0, &[4, 5, 6, 7], WORD, Some(1)),
        store(3, 3, 3, "swc1", 0, true, 0, &[4, 5, 6, 7], 0x5000, 4, WORD),
    ]);
    let bytes = serde_json::to_vec(&value).unwrap();
    let digest = sha256(&bytes);
    let report = cop1_lineage::inspect_cop1_lineage_history(&bytes, &digest).unwrap();
    cop1_lineage::verify_cop1_lineage_report(&report, &bytes, &digest).unwrap();

    let mut deleted = value;
    deleted["events"].as_array_mut().unwrap().remove(0);
    let deleted_bytes = serde_json::to_vec(&deleted).unwrap();
    assert!(cop1_lineage::inspect_cop1_lineage_history(&deleted_bytes, &digest).is_err());

    let mut forged = report.clone();
    forged.stores[0].byte_origins[0] = FprByteOrigin::Initial {
        physical_fpr: 0,
        slot: 4,
    };
    assert!(cop1_lineage::verify_cop1_lineage_report(&forged, &bytes, &digest).is_err());
    let mut forged = report;
    forged.native_complete = true;
    assert!(cop1_lineage::verify_cop1_lineage_report(&forged, &bytes, &digest).is_err());
}
