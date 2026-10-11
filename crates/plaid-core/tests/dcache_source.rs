use plaid_core::{
    dcache_source::{
        self, DcacheReadWitness, DcacheSourceReport, WordGeneration, WordGenerationKind,
    },
    rom::sha256,
};
use serde_json::{Value, json};

const TABLE: u32 = 0x2000;
const CONFLICT: u32 = 0x4000;
const PTR_A: u32 = 0x8000_7000;
const PTR_B: u32 = 0x8000_7100;
const PTR_C: u32 = 0x8000_7200;
const PRIME_PC: u64 = 0xffff_ffff_8000_6010;
const DISPATCH_PC: u64 = 0xffff_ffff_8000_6020;
const MUTATE_PC: u64 = 0xffff_ffff_8000_6004;
const TABLE_VA: u64 = 0xffff_ffff_8000_2000;
const CONFLICT_VA: u64 = 0xffff_ffff_8000_4000;
const SLOT: u16 = 7;
const TABLE_TAG: u32 = 0x2001;
const CONFLICT_TAG: u32 = 0x4001;

fn record(kind: &str, event: Value) -> Value {
    json!({"kind":kind,"event":event})
}

fn initial_backing(table: u32) -> Vec<Value> {
    vec![
        json!({"address":TABLE,"value":table}),
        json!({"address":TABLE+4,"value":0x1111_2222u32}),
        json!({"address":TABLE+8,"value":0x3333_4444u32}),
        json!({"address":TABLE+12,"value":0x5555_6666u32}),
        json!({"address":CONFLICT,"value":PTR_A}),
        json!({"address":CONFLICT+4,"value":0x1357_9bdfu32}),
        json!({"address":CONFLICT+8,"value":0x2468_ace0u32}),
        json!({"address":CONFLICT+12,"value":0x0bad_f00du32}),
    ]
}

fn burst(ordinal: u64, address: u32, first: u32) -> Value {
    let words = if address == TABLE {
        [first, 0x1111_2222, 0x3333_4444, 0x5555_6666]
    } else {
        [first, 0x1357_9bdf, 0x2468_ace0, 0x0bad_f00d]
    };
    record(
        "backing_burst_read",
        json!({"ordinal":ordinal,"address":address,"words":words}),
    )
}

#[allow(clippy::too_many_arguments)]
fn cache_read(
    ordinal: u64,
    pc: u64,
    vaddr: u64,
    paddr: u32,
    value: u32,
    tag: u32,
    dirty: u16,
    hit_before: bool,
) -> Value {
    record(
        "cache_read",
        json!({"ordinal":ordinal,"pc":pc,"vaddr":vaddr,"paddr":paddr,"value":value,
            "slot":SLOT,"tag":tag,"dirty":dirty,"hit_before":hit_before}),
    )
}

fn backing_write(ordinal: u64, value: u32) -> Value {
    record(
        "backing_write",
        json!({"ordinal":ordinal,"pc":MUTATE_PC,"address":TABLE,"value":value}),
    )
}

fn cache_write(ordinal: u64, value: u32) -> Value {
    record(
        "cache_write",
        json!({"ordinal":ordinal,"pc":MUTATE_PC,"vaddr":TABLE_VA,"paddr":TABLE,
            "value":value,"slot":SLOT,"tag":TABLE_TAG,"dirty":15,"hit_before":true}),
    )
}

fn fixture(name: &str) -> Value {
    let (initial, records) = match name {
        "stale" => (
            PTR_A,
            vec![
                burst(1, TABLE, PTR_A),
                cache_read(2, PRIME_PC, TABLE_VA, TABLE, PTR_A, TABLE_TAG, 0, false),
                backing_write(3, PTR_B),
                cache_read(4, DISPATCH_PC, TABLE_VA, TABLE, PTR_A, TABLE_TAG, 0, true),
            ],
        ),
        "same" => (
            PTR_A,
            vec![
                burst(1, TABLE, PTR_A),
                cache_read(2, PRIME_PC, TABLE_VA, TABLE, PTR_A, TABLE_TAG, 0, false),
                backing_write(3, PTR_A),
                cache_read(4, DISPATCH_PC, TABLE_VA, TABLE, PTR_A, TABLE_TAG, 0, true),
            ],
        ),
        "refill" => (
            PTR_A,
            vec![
                burst(1, TABLE, PTR_A),
                cache_read(2, PRIME_PC, TABLE_VA, TABLE, PTR_A, TABLE_TAG, 0, false),
                backing_write(3, PTR_B),
                burst(4, CONFLICT, PTR_A),
                cache_read(
                    5,
                    PRIME_PC + 4,
                    CONFLICT_VA,
                    CONFLICT,
                    PTR_A,
                    CONFLICT_TAG,
                    0,
                    false,
                ),
                burst(6, TABLE, PTR_B),
                cache_read(7, DISPATCH_PC, TABLE_VA, TABLE, PTR_B, TABLE_TAG, 0, false),
            ],
        ),
        "same_refill" => (
            PTR_A,
            vec![
                burst(1, TABLE, PTR_A),
                cache_read(2, PRIME_PC, TABLE_VA, TABLE, PTR_A, TABLE_TAG, 0, false),
                backing_write(3, PTR_A),
                burst(4, CONFLICT, PTR_A),
                cache_read(
                    5,
                    PRIME_PC + 4,
                    CONFLICT_VA,
                    CONFLICT,
                    PTR_A,
                    CONFLICT_TAG,
                    0,
                    false,
                ),
                burst(6, TABLE, PTR_A),
                cache_read(7, DISPATCH_PC, TABLE_VA, TABLE, PTR_A, TABLE_TAG, 0, false),
            ],
        ),
        "resident" => (
            PTR_B,
            vec![
                burst(1, TABLE, PTR_B),
                cache_read(2, PRIME_PC, TABLE_VA, TABLE, PTR_B, TABLE_TAG, 0, false),
                cache_write(3, PTR_C),
                cache_read(4, DISPATCH_PC, TABLE_VA, TABLE, PTR_C, TABLE_TAG, 15, true),
            ],
        ),
        _ => panic!("unknown fixture"),
    };
    json!({"format":dcache_source::FORMAT,"initial_backing":initial_backing(initial),"records":records})
}

fn encoded(value: &Value) -> Vec<u8> {
    serde_json::to_vec(value).unwrap()
}

fn inspect(value: &Value) -> Result<DcacheSourceReport, String> {
    let bytes = encoded(value);
    dcache_source::inspect_dcache_source_history(&bytes, &sha256(&bytes))
}

fn dispatch(report: &DcacheSourceReport) -> &DcacheReadWitness {
    report
        .reads
        .iter()
        .find(|read| read.pc.0 == DISPATCH_PC)
        .expect("dispatch read")
}

fn generation_value(report: &DcacheSourceReport, generation: WordGeneration) -> u32 {
    report
        .generations
        .iter()
        .find(|record| record.generation == generation)
        .expect("generation record")
        .value
}

#[test]
fn five_reference_shapes_preserve_resident_and_backing_identity() {
    let stale = inspect(&fixture("stale")).unwrap();
    let stale_read = dispatch(&stale);
    assert_eq!(
        (stale_read.value, stale_read.current_backing_value),
        (PTR_A, PTR_B)
    );
    assert_ne!(
        stale_read.source_generation,
        stale_read.current_backing_generation
    );

    let same = inspect(&fixture("same")).unwrap();
    let same_read = dispatch(&same);
    assert_eq!(
        (same_read.value, same_read.current_backing_value),
        (PTR_A, PTR_A)
    );
    assert_ne!(
        same_read.source_generation,
        same_read.current_backing_generation
    );
    assert_eq!(
        same_read.current_backing_generation.kind,
        WordGenerationKind::BackingWrite
    );

    let refill = inspect(&fixture("refill")).unwrap();
    let refill_read = dispatch(&refill);
    assert_eq!(
        refill_read.source_generation.kind,
        WordGenerationKind::CacheFill
    );
    assert_eq!(refill_read.source_generation.ordinal, Some(6));
    assert_eq!(refill_read.current_backing_generation.ordinal, Some(3));
    let refill_record = refill
        .generations
        .iter()
        .find(|record| record.generation == refill_read.source_generation)
        .unwrap();
    assert_eq!(
        refill_record.source,
        Some(refill_read.current_backing_generation)
    );

    let same_refill = inspect(&fixture("same_refill")).unwrap();
    let same_refill_read = dispatch(&same_refill);
    assert_eq!(same_refill_read.source_generation.ordinal, Some(6));
    let old_fill = WordGeneration {
        kind: WordGenerationKind::CacheFill,
        ordinal: Some(1),
        address: plaid_core::program::PhysicalAddr(TABLE),
    };
    let decoy = WordGeneration {
        kind: WordGenerationKind::CacheFill,
        ordinal: Some(4),
        address: plaid_core::program::PhysicalAddr(CONFLICT),
    };
    assert_ne!(same_refill_read.source_generation, old_fill);
    assert_ne!(same_refill_read.source_generation, decoy);
    assert_eq!(generation_value(&same_refill, old_fill), PTR_A);
    assert_eq!(generation_value(&same_refill, decoy), PTR_A);
    assert_eq!(same_refill_read.value, PTR_A);

    let resident = inspect(&fixture("resident")).unwrap();
    let resident_read = dispatch(&resident);
    assert_eq!(
        resident_read.source_generation.kind,
        WordGenerationKind::ResidentWrite
    );
    assert_eq!(resident_read.source_generation.ordinal, Some(3));
    assert_eq!(
        resident_read.current_backing_generation.kind,
        WordGenerationKind::InitialBacking
    );
    assert_eq!(
        (resident_read.value, resident_read.current_backing_value),
        (PTR_C, PTR_B)
    );

    for report in [&stale, &same, &refill, &same_refill, &resident] {
        assert!(
            !report.source_history_coverage_certified
                && !report.mapping_history_certified
                && !report.mutation_coverage_certified
                && !report.executable_lifetime_certified
                && !report.native_complete
        );
    }
}

#[test]
fn complete_source_recheck_rejects_deletion_reordering_and_self_recertification() {
    let original = fixture("same");
    let original_bytes = encoded(&original);
    let original_digest = sha256(&original_bytes);
    let report =
        dcache_source::inspect_dcache_source_history(&original_bytes, &original_digest).unwrap();
    dcache_source::verify_dcache_source_report(&report, &original_bytes, &original_digest).unwrap();

    let mut deleted_write = original.clone();
    deleted_write["records"].as_array_mut().unwrap().remove(2);
    deleted_write["records"][2]["event"]["ordinal"] = json!(3);
    let bytes = encoded(&deleted_write);
    assert!(dcache_source::inspect_dcache_source_history(&bytes, &original_digest).is_err());
    let digest = sha256(&bytes);
    assert!(dcache_source::verify_dcache_source_report(&report, &bytes, &digest).is_err());

    let mut reordered = original.clone();
    reordered["records"].as_array_mut().unwrap().swap(2, 3);
    reordered["records"][2]["event"]["ordinal"] = json!(3);
    reordered["records"][3]["event"]["ordinal"] = json!(4);
    let bytes = encoded(&reordered);
    let digest = sha256(&bytes);
    let changed = dcache_source::inspect_dcache_source_history(&bytes, &digest).unwrap();
    assert_ne!(
        dispatch(&changed).current_backing_generation,
        dispatch(&report).current_backing_generation
    );
    assert!(dcache_source::verify_dcache_source_report(&report, &bytes, &digest).is_err());

    let mut deleted_dispatch = original;
    deleted_dispatch["records"].as_array_mut().unwrap().pop();
    let bytes = encoded(&deleted_dispatch);
    let digest = sha256(&bytes);
    assert!(dcache_source::inspect_dcache_source_history(&bytes, &digest).is_ok());
    assert!(dcache_source::verify_dcache_source_report(&report, &bytes, &digest).is_err());

    let mut forged = report;
    forged.native_complete = true;
    assert!(
        dcache_source::verify_dcache_source_report(&forged, &original_bytes, &original_digest)
            .is_err()
    );
}

#[test]
fn slot_tag_ordinal_and_source_decoys_fail_closed() {
    let original = fixture("same_refill");

    let mut forged_tag = original.clone();
    forged_tag["records"][6]["event"]["tag"] = json!(CONFLICT_TAG);
    assert!(inspect(&forged_tag).is_err());

    let mut forged_source = original.clone();
    forged_source["records"][6]["event"]["paddr"] = json!(CONFLICT);
    assert!(inspect(&forged_source).is_err());

    let mut duplicate_ordinal = original.clone();
    duplicate_ordinal["records"][6]["event"]["ordinal"] = json!(6);
    assert!(inspect(&duplicate_ordinal).is_err());

    let mut forged_hit = original.clone();
    forged_hit["records"][6]["event"]["hit_before"] = json!(true);
    assert!(inspect(&forged_hit).is_err());

    let mut unknown = original;
    unknown["records"][6]["event"]["claimed_source_generation"] = json!("equal-payload-decoy");
    assert!(inspect(&unknown).is_err());
}

#[test]
fn unsupported_dirty_replacement_and_unconsumed_fill_remain_unknown() {
    let mut dirty_replacement = fixture("resident");
    dirty_replacement["records"]
        .as_array_mut()
        .unwrap()
        .push(burst(5, CONFLICT, PTR_A));
    dirty_replacement["records"]
        .as_array_mut()
        .unwrap()
        .push(cache_read(
            6,
            PRIME_PC + 4,
            CONFLICT_VA,
            CONFLICT,
            PTR_A,
            CONFLICT_TAG,
            0,
            false,
        ));
    assert!(inspect(&dirty_replacement).is_err());

    let mut dangling = fixture("stale");
    dangling["records"]
        .as_array_mut()
        .unwrap()
        .push(burst(5, CONFLICT, PTR_A));
    assert!(inspect(&dangling).is_err());
}

#[test]
fn exact_source_schema_and_alignment_are_strict() {
    let mut wrong_format = fixture("stale");
    wrong_format["format"] = json!("plaid-dcache-word-source-v1");
    assert!(inspect(&wrong_format).is_err());

    let mut extra = fixture("stale");
    extra["records"][3]["event"]["extra"] = json!(0);
    assert!(inspect(&extra).is_err());

    let mut unaligned = fixture("stale");
    unaligned["records"][3]["event"]["paddr"] = json!(TABLE + 1);
    assert!(inspect(&unaligned).is_err());
}
