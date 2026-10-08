use plaid_core::{
    fetch, history,
    pi_history::{self, PiHistoryReport, inspect_pi_boot_history, verify_pi_boot_history_report},
    rom::{CanonicalRom, sha256},
    solver::{self, ClosureStatus, Scope},
};
use serde_json::{Value, json};
use std::io::Cursor;

fn wire(rows: &[Value]) -> Vec<u8> {
    rows.iter()
        .map(|row| row.to_string() + "\n")
        .collect::<String>()
        .into_bytes()
}
struct Fixture {
    rom: CanonicalRom,
    firmware: Vec<u8>,
    history: Vec<Value>,
    fetches: Vec<Value>,
}
fn append(rows: &mut Vec<Value>, mut row: Value, context: u64, pc: u64) {
    row["ordinal"] = json!(rows.len() as u64);
    row["context"] = json!(context);
    row["pc"] = json!(pc);
    rows.push(row);
}
fn fixture() -> Fixture {
    let mut source = vec![0; 16384];
    source[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    source[0x2000..0x2004].copy_from_slice(&7u32.to_be_bytes());
    source[0x3000..0x3004].copy_from_slice(&7u32.to_be_bytes());
    let rom = CanonicalRom::from_bytes(&source).unwrap();
    let firmware = vec![0; 1984];
    let boot = json!({"firmware_sha256":sha256(&firmware),"firmware_size":1984,"region":"ntsc","cic":"CIC-NUS-6102",
        "rdram_size":8388608,"deterministic_entropy":true,"pif_processor":"reference_hle","pif_checksum_enforced":true});
    let mut rows = vec![
        json!({"record":"header","format":pi_history::FORMAT,"revision":fetch::REVISION,
        "rom_sha256":rom.identity.sha256,"budget":2,"mapped_cartridge_size":16384,"firmware_sha256":sha256(&firmware),
        "policy":pi_history::POLICY,"lifecycle_policy":history::LIFECYCLE_POLICY,"paired_fetch_format":fetch::CACHE_FORMAT}),
    ];
    let mut fetches = vec![
        json!({"record":"header","format":fetch::CACHE_FORMAT,"revision":fetch::REVISION,
        "rom_sha256":rom.identity.sha256,"budget":2,"initial_state":fetch::BOOT_INITIAL_STATE,"mapped_cartridge_size":16384,
        "source_policy":fetch::SOURCE_POLICY,"boot_inputs":boot,"cache_policy":fetch::CACHE_POLICY}),
    ];
    let fetch_word = |rows: &mut Vec<Value>,
                      fetches: &mut Vec<Value>,
                      seq: u64,
                      pc: u64,
                      physical: u32,
                      word: u32| {
        let context = rows.len() as u64;
        append(
            rows,
            json!({"record":"fetch_begin","vaddr":pc,"translated":physical,"bus":physical,"cached":false,"value":0}),
            context,
            pc,
        );
        if seq == 1 {
            append(
                rows,
                json!({"record":"scalar","write":false,"address":physical,"aligned_address":physical,
            "bytes":4,"device":3,"value":word}),
                context,
                pc,
            );
        }
        append(
            rows,
            json!({"record":"fetch_end","vaddr":pc,"translated":physical,"bus":physical,"cached":false,"value":word}),
            context,
            pc,
        );
        append(
            rows,
            json!({"record":"fetch","fetch_context":context,"fetch_seq":seq,"word":word,"physical":physical,"cached":false}),
            0,
            pc,
        );
        fetches.push(
            json!({"record":"fetch","seq":seq,"pc":pc,"word":word,"delay_slot":false,
            "physical":physical,"cached":false,"source":{"kind":"unknown"}}),
        );
    };
    fetch_word(
        &mut rows,
        &mut fetches,
        0,
        0xffffffffbfc00000,
        0x1fc00000,
        0,
    );
    let pc = 0xffffffffbfc00004;
    for (transfer, destination, bytes, witnessed) in [
        (1u64, 0x1000u32, vec![0u8, 0, 0, 7], true),
        (2, 0x2000, vec![0x12, 0x34], false),
        (3, 8388608, vec![0, 0], true),
    ] {
        let pbus = if witnessed { 0x10002000u32 } else { 0x1ff00000 };
        let length = bytes.len() as u32;
        let pi = |rows: &mut Vec<Value>,
                  event: u32,
                  block: u32,
                  dram: u32,
                  address: u32,
                  lane: u32,
                  value: u32| {
            append(
                rows,
                json!({"record":"pi_dma","event":event,"transfer":transfer,"block":block,
                "dram":dram,"pbus":address,"length":length,"lane":lane,"value":value}),
                0,
                pc,
            );
        };
        pi(&mut rows, 1, 0, destination, pbus, 0, 0);
        pi(&mut rows, 2, 1, destination, pbus, 0, 1);
        for (lane, half) in bytes.chunks(2).enumerate() {
            let lane = lane as u32 * 2;
            let value = u16::from_be_bytes([half[0], half[1]]);
            if witnessed {
                append(
                    &mut rows,
                    json!({"record":"pi_rom_half","transfer":transfer,"block":1,
                "offset":0x2000+lane,"value":value}),
                    0,
                    pc,
                );
            }
            pi(
                &mut rows,
                3,
                1,
                destination,
                pbus + lane,
                lane,
                value.into(),
            );
        }
        for (lane, value) in bytes.iter().copied().enumerate() {
            let lane = lane as u32;
            pi(
                &mut rows,
                4,
                1,
                destination + lane,
                pbus + length,
                lane,
                value.into(),
            );
            if destination < 8388608 {
                append(
                    &mut rows,
                    json!({"record":"scalar","write":true,"address":destination+lane,
                "aligned_address":destination+lane,"bytes":1,"device":5,"value":value,
                "pi":{"transfer":transfer,"block":1,"lane":lane}}),
                    0,
                    pc,
                );
            }
            pi(
                &mut rows,
                5,
                1,
                destination + lane,
                pbus + length,
                lane,
                value.into(),
            );
        }
        pi(&mut rows, 6, 1, destination + length, pbus + length, 0, 1);
        pi(&mut rows, 7, 1, destination + length, pbus + length, 0, 0);
        if transfer == 1 {
            pi(&mut rows, 8, 1, destination + length, pbus + length, 0, 1);
        }
    }
    fetch_word(&mut rows, &mut fetches, 1, 0xffffffffa0001000, 0x1000, 7);
    rows.push(json!({"record":"end","record_count":rows.len()-1,"fetch_count":2,"reason":"instruction_call_budget"}));
    fetches.push(json!({"record":"end","fetch_count":2,"reason":"instruction_call_budget"}));
    Fixture {
        rom,
        firmware,
        history: rows,
        fetches,
    }
}
fn inspect(f: &Fixture) -> Result<PiHistoryReport, String> {
    inspect_pi_boot_history(
        Cursor::new(wire(&f.history)),
        Cursor::new(wire(&f.fetches)),
        &f.rom,
        &f.firmware,
    )
}

#[test]
fn finite_sources_effects_and_projection_keep_completion_and_closure_unknown() {
    let f = fixture();
    let report = inspect(&f).unwrap();
    assert_eq!(report.history_sha256, sha256(&wire(&f.history)));
    assert_eq!(
        (
            report.successful_pi_writes,
            report.canonical_rom_byte_origins,
            report.unknown_pi_byte_origins,
            report.failed_destination_witnesses
        ),
        (6, 4, 2, 2)
    );
    assert_eq!(report.source_half_reads, 3);
    assert_eq!(report.returned_transfers, 3);
    assert_eq!(report.observer_write_contexts_at_status, vec![1]);
    assert_eq!(report.writes_without_observer_status, vec![2, 3]);
    assert!(!report.transfer_completion_certified);
    assert_eq!(
        (
            report.projection.records,
            report.projection.fetches,
            report.projection.scalar_fetch_witnesses
        ),
        (13, 2, 1)
    );
    verify_pi_boot_history_report(
        &report,
        Cursor::new(wire(&f.history)),
        Cursor::new(wire(&f.fetches)),
        &f.rom,
        &f.firmware,
    )
    .unwrap();
    assert!(
        history::inspect_boot_history(
            Cursor::new(wire(&f.history)),
            Cursor::new(wire(&f.fetches)),
            &f.rom,
            &f.firmware
        )
        .is_err()
    );
    let map = fetch::import_boot_fetch(Cursor::new(wire(&f.fetches)), &f.rom, &f.firmware).unwrap();
    let solved = solver::solve(&map, &[], Scope::WholeRom).unwrap();
    assert_eq!(solved.status, ClosureStatus::Open);
    assert!(!solved.native_complete);
}

#[test]
fn equal_rom_offsets_lose_attribution_and_raw_payloads_bind_report() {
    let mut f = fixture();
    let report = inspect(&f).unwrap();
    let first = f
        .history
        .iter_mut()
        .find(|r| r["record"] == "pi_rom_half")
        .unwrap();
    first["offset"] = json!(0x3000);
    let changed = inspect(&f).unwrap();
    assert_eq!(changed.canonical_rom_byte_origins, 2);
    assert_ne!(
        changed.pi_origin_effects_sha256,
        report.pi_origin_effects_sha256
    );
    assert!(
        verify_pi_boot_history_report(
            &report,
            Cursor::new(wire(&f.history)),
            Cursor::new(wire(&f.fetches)),
            &f.rom,
            &f.firmware
        )
        .is_err()
    );
    let mut f = fixture();
    let block_end = f
        .history
        .iter_mut()
        .find(|r| r["record"] == "pi_dma" && r["event"] == 6)
        .unwrap();
    block_end["dram"] = json!(0x3333);
    let changed = inspect(&f).unwrap();
    assert_eq!(
        changed.pi_origin_effects_sha256,
        report.pi_origin_effects_sha256
    );
    assert_ne!(changed.history_sha256, report.history_sha256);
    assert!(
        verify_pi_boot_history_report(
            &report,
            Cursor::new(wire(&f.history)),
            Cursor::new(wire(&f.fetches)),
            &f.rom,
            &f.firmware
        )
        .is_err()
    );
    let mut forged = report;
    forged.transfer_completion_certified = true;
    let f = fixture();
    assert!(
        verify_pi_boot_history_report(
            &forged,
            Cursor::new(wire(&f.history)),
            Cursor::new(wire(&f.fetches)),
            &f.rom,
            &f.firmware
        )
        .is_err()
    );
}

#[test]
fn forged_protocol_context_metadata_and_inputs_fail() {
    let original = fixture();
    for (kind, field, value) in [
        ("pi_rom_half", "value", json!(65535)),
        ("pi_dma", "transfer", json!(2)),
        ("scalar", "pi", json!({"transfer":true,"block":1,"lane":0})),
        ("scalar", "bytes", json!(2)),
        ("scalar", "value", json!(99)),
        ("scalar", "address", json!(0x5000)),
        ("fetch", "fetch_context", json!(999)),
    ] {
        let mut f = fixture();
        let row = f
            .history
            .iter_mut()
            .find(|r| r["record"] == kind && (kind != "scalar" || r["write"] == true))
            .unwrap();
        row[field] = value;
        assert!(inspect(&f).is_err(), "accepted {kind}.{field}");
    }
    for (field, value) in [
        ("format", json!(history::FORMAT)),
        ("policy", json!(history::POLICY)),
        ("revision", json!("wrong")),
        ("budget", json!(true)),
        ("lifecycle_policy", json!("restore_untracked")),
    ] {
        let mut f = fixture();
        f.history[0][field] = value;
        assert!(inspect(&f).is_err());
    }
    let mut f = fixture();
    f.history[2]["ordinal"] = json!(1);
    assert!(inspect(&f).is_err());
    let mut f = fixture();
    f.history.pop();
    assert!(inspect(&f).is_err());
    let mut f = fixture();
    f.firmware[1] = 1;
    assert!(inspect(&f).is_err());
    let mut f = fixture();
    f.fetches[2]["word"] = json!(8);
    assert!(inspect(&f).is_err());
    let raw = wire(&original.history);
    assert!(
        inspect_pi_boot_history(
            Cursor::new(&raw[..raw.len() - 1]),
            Cursor::new(wire(&original.fetches)),
            &original.rom,
            &original.firmware
        )
        .is_err()
    );
    let mut oversized = raw.clone();
    oversized.splice(0..0, vec![b' '; 1024 * 1024]);
    assert!(
        inspect_pi_boot_history(
            Cursor::new(oversized),
            Cursor::new(wire(&original.fetches)),
            &original.rom,
            &original.firmware
        )
        .is_err()
    );
}

#[test]
fn duplicate_unknown_null_and_missing_fields_cannot_hide_in_wire_variants() {
    let f = fixture();
    let raw = String::from_utf8(wire(&f.history)).unwrap();
    for changed in [
        raw.replacen("\"transfer\":1", "\"transfer\":1,\"transfer\":1", 1),
        raw.replacen(
            "\"record\":\"pi_dma\"",
            "\"record\":\"pi_dma\",\"record\":\"pi_dma\"",
            1,
        ),
        raw.replacen("\"block\":1", "\"unexpected\":1,\"block\":1", 1),
        raw.replacen("\"pi\":{", "\"pi\":null,\"unused\":{", 1),
        raw.replacen("\"lane\":0,", "", 1),
    ] {
        assert!(
            inspect_pi_boot_history(
                Cursor::new(changed),
                Cursor::new(wire(&f.fetches)),
                &f.rom,
                &f.firmware
            )
            .is_err()
        );
    }
    let report = inspect(&f).unwrap();
    let wire = serde_json::to_string(&report).unwrap();
    assert!(
        serde_json::from_str::<PiHistoryReport>(&wire.replacen(
            "\"records\":",
            "\"unexpected\":1,\"records\":",
            1
        ))
        .is_err()
    );
}

#[test]
fn dropping_pi_records_cannot_launder_fetch_interval_ordering() {
    let mut f = fixture();
    let original = f.history.clone();
    let second_begin = original
        .iter()
        .position(|r| r["record"] == "fetch_begin" && r["pc"] == json!(0xffffffffa0001000u64))
        .unwrap();
    // Move the second access begin before all synchronous PI copies, then make
    // every PI record look internally consistent with that fabricated context.
    // A projection that merely drops PI records would hide this forbidden order.
    let mut rows = original[..4].to_vec();
    let mut begin = original[second_begin].clone();
    begin["ordinal"] = json!(4);
    begin["context"] = json!(4);
    rows.push(begin);
    for row in &original[4..second_begin] {
        let mut row = row.clone();
        row["ordinal"] = json!(rows.len());
        row["context"] = json!(4);
        row["pc"] = json!(0xffffffffa0001000u64);
        rows.push(row);
    }
    for row in &original[second_begin + 1..original.len() - 1] {
        let mut row = row.clone();
        row["ordinal"] = json!(rows.len());
        if row["record"] == "fetch" {
            row["fetch_context"] = json!(4);
        } else {
            row["context"] = json!(4);
        }
        rows.push(row);
    }
    rows.push(json!({"record":"end","record_count":rows.len()-1,"fetch_count":2,"reason":"instruction_call_budget"}));
    f.history = rows;
    assert!(inspect(&f).is_err());
}
