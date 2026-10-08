use plaid_core::{
    fetch,
    history::{self, AccessHistoryReport, inspect_boot_history, verify_boot_history_report},
    rom::{CanonicalRom, sha256},
    solver::{ClosureStatus, Scope, solve},
};
use serde_json::{Value, json};
use std::io::{BufRead, Cursor, Read, Seek, SeekFrom};

struct Fixture {
    rom: CanonicalRom,
    firmware: Vec<u8>,
    history: Vec<Value>,
    fetches: Vec<Value>,
}
fn wire(rows: &[Value]) -> String {
    rows.iter().map(|r| r.to_string() + "\n").collect()
}
fn fixture() -> Fixture {
    let mut bytes = vec![0; 512];
    bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    let rom = CanonicalRom::from_bytes(&bytes).unwrap();
    let firmware = vec![0; 1984];
    let boot = json!({"firmware_sha256":sha256(&firmware),"firmware_size":1984,"region":"ntsc",
        "cic":"CIC-NUS-6102","rdram_size":8388608,"deterministic_entropy":true,
        "pif_processor":"reference_hle","pif_checksum_enforced":true});
    let mut fetches = vec![
        json!({"record":"header","format":fetch::CACHE_FORMAT,"revision":fetch::REVISION,
        "rom_sha256":rom.identity.sha256,"budget":3,"initial_state":fetch::BOOT_INITIAL_STATE,
        "mapped_cartridge_size":512,"source_policy":fetch::SOURCE_POLICY,"boot_inputs":boot,"cache_policy":fetch::CACHE_POLICY}),
    ];
    let mut rows = vec![
        json!({"record":"header","format":history::FORMAT,"revision":fetch::REVISION,
        "rom_sha256":rom.identity.sha256,"budget":3,"mapped_cartridge_size":512,"firmware_sha256":sha256(&firmware),
        "policy":history::POLICY,"lifecycle_policy":history::LIFECYCLE_POLICY,"paired_fetch_format":fetch::CACHE_FORMAT}),
    ];
    let words = [0x24100009u32, 0, 0, 0, 0, 0, 0, 0];
    for (seq, pc, pa, cached, word, id) in [
        (0, 0xffff_ffff_bfc0_0000u64, 0x1fc00000u32, false, 0, 1),
        (1, 0xffff_ffff_a000_1000, 0x1000, false, 0x24100001, 5),
        (2, 0xffff_ffff_8000_4000, 0x4000, true, words[0], 9),
    ] {
        if seq == 1 {
            rows.push(
                json!({"record":"scalar","ordinal":4,"context":0,"pc":pc,"write":false,
                "address":0x2000,"aligned_address":0x2000,"bytes":4,"device":3,"value":word}),
            );
        }
        let begin = json!({"record":"fetch_begin","ordinal":id,"context":id,"pc":pc,"vaddr":pc,
            "translated":pa,"bus":pa,"cached":cached,"value":0});
        rows.push(begin.clone());
        if seq == 1 {
            rows.push(
                json!({"record":"scalar","ordinal":6,"context":id,"pc":pc,"write":false,
                "address":pa,"aligned_address":pa,"bytes":4,"device":3,"value":word}),
            );
        } else if seq == 2 {
            rows.push(
                json!({"record":"burst","ordinal":10,"context":id,"pc":pc,"write":false,
                "address":pa,"bytes":32,"device":1,"words":words}),
            );
            rows.push(
                json!({"record":"fill","ordinal":11,"context":id,"pc":pc,"slot":0,
                "physical":pa,"index":0,"words":words}),
            );
        }
        let mut end = begin;
        end["record"] = "fetch_end".into();
        end["ordinal"] = json!(rows.len());
        end["value"] = word.into();
        rows.push(end);
        rows.push(
            json!({"record":"fetch","ordinal":rows.len(),"context":0,"pc":pc,"fetch_context":id,
            "fetch_seq":seq,"word":word,"physical":pa,"cached":cached}),
        );
        let mut fetch = json!({"record":"fetch","seq":seq,"pc":pc,"word":word,"delay_slot":false,
            "physical":pa,"cached":cached,"source":{"kind":"unknown"}});
        if cached {
            fetch["cache_line"] = json!({"slot":0,"tag_key":0x4001,"index":0,"words":words});
        }
        fetches.push(fetch);
    }
    rows.push(json!({"record":"end","record_count":13,"fetch_count":3,"reason":"instruction_call_budget"}));
    fetches.push(json!({"record":"end","fetch_count":3,"reason":"instruction_call_budget"}));
    Fixture {
        rom,
        firmware,
        history: rows,
        fetches,
    }
}
fn inspect(f: &Fixture) -> Result<AccessHistoryReport, String> {
    inspect_boot_history(
        Cursor::new(wire(&f.history)),
        Cursor::new(wire(&f.fetches)),
        &f.rom,
        &f.firmware,
    )
}

#[test]
fn access_report_is_source_bound_and_does_not_close_execution() {
    let f = fixture();
    let report = inspect(&f).unwrap();
    assert_eq!(
        (
            report.records,
            report.fetches,
            report.scalar_fetch_witnesses,
            report.outside_uncached_cpu_reads
        ),
        (13, 3, 1, 1)
    );
    assert_eq!(
        (
            report.matched_context_ram_fills,
            report.unknown_context_fills
        ),
        (1, 0)
    );
    assert_eq!(report.history_sha256, sha256(wire(&f.history).as_bytes()));
    assert_eq!(report.fetch_sha256, sha256(wire(&f.fetches).as_bytes()));
    assert_eq!(
        report,
        serde_json::from_str::<AccessHistoryReport>(&serde_json::to_string(&report).unwrap())
            .unwrap()
    );
    verify_boot_history_report(
        &report,
        Cursor::new(wire(&f.history)),
        Cursor::new(wire(&f.fetches)),
        &f.rom,
        &f.firmware,
    )
    .unwrap();
    let map = fetch::import_boot_fetch(Cursor::new(wire(&f.fetches)), &f.rom, &f.firmware).unwrap();
    let closed = solve(&map, &[], Scope::WholeRom).unwrap();
    assert_eq!(closed.status, ClosureStatus::Open);
    assert!(!closed.native_complete && map.regions.is_empty() && map.loads.is_empty());
}

#[test]
fn decoy_reads_and_unfetched_lanes_cannot_fabricate_backing_witnesses() {
    let mut f = fixture();
    f.history.swap(4, 5);
    f.history[4]["ordinal"] = 4.into();
    f.history[4]["context"] = 4.into();
    f.history[5]["ordinal"] = 5.into();
    f.history[5]["context"] = 4.into();
    f.history[6]["context"] = 4.into();
    f.history[7]["context"] = 4.into();
    f.history[8]["fetch_context"] = 4.into();
    let ambiguous = inspect(&f).unwrap();
    assert_eq!(ambiguous.scalar_fetch_witnesses, 0);
    assert_eq!(ambiguous.outside_uncached_cpu_reads, 0);
    for case in 0..3 {
        let mut f = fixture();
        match case {
            0 => {
                f.history[10]["words"][1] = 7.into();
                f.history[11]["words"][1] = 7.into();
            }
            1 => {
                f.history.swap(10, 11);
                f.history[10]["ordinal"] = 10.into();
                f.history[11]["ordinal"] = 11.into();
            }
            _ => f.history[6]["value"] = 0.into(),
        }
        let report = inspect(&f).unwrap();
        if case < 2 {
            assert_eq!(
                (
                    report.matched_context_ram_fills,
                    report.unknown_context_fills
                ),
                (0, 1)
            );
        } else {
            assert_eq!(report.scalar_fetch_witnesses, 0);
        }
    }
}

#[test]
fn malformed_contexts_transactions_inputs_and_footers_fail_closed() {
    for (index, key, value) in [
        (0, "policy", json!("all_ram")),
        (0, "budget", json!(4)),
        (0, "revision", json!("other")),
        (0, "firmware_sha256", json!("a".repeat(64))),
        (0, "mapped_cartridge_size", json!(504)),
        (5, "context", json!(4)),
        (6, "ordinal", json!(5)),
        (7, "bus", json!(0x2000)),
        (8, "fetch_context", json!(1)),
        (8, "fetch_seq", json!(0)),
        (8, "word", json!(0)),
        (6, "bytes", json!(3)),
        (6, "value", json!(1u64 << 32)),
        (6, "aligned_address", json!(0x1004)),
        (10, "words", json!(vec![0; 7])),
        (11, "slot", json!(512)),
        (11, "index", json!(32)),
        (6, "device", json!(14)),
        (6, "extra", json!(0)),
        (6, "value", Value::Null),
        (14, "fetch_count", json!(2)),
        (14, "record_count", json!(12)),
    ] {
        let mut f = fixture();
        f.history[index][key] = value;
        assert!(inspect(&f).is_err(), "{index}/{key}");
    }
    let mut f = fixture();
    f.firmware[10] = 1;
    assert!(inspect(&f).is_err());
    for truncated in [true, false] {
        let mut f = fixture();
        if truncated {
            f.history.pop();
        } else {
            f.history.push(f.history[6].clone());
        }
        assert!(inspect(&f).is_err());
    }
    let f = fixture();
    let history = wire(&f.history);
    assert!(
        inspect_boot_history(
            Cursor::new(history.trim_end()),
            Cursor::new(wire(&f.fetches)),
            &f.rom,
            &f.firmware
        )
        .is_err()
    );
    let duplicate = history.replace("\"ordinal\":6", "\"ordinal\":6,\"ordinal\":6");
    assert!(
        inspect_boot_history(
            Cursor::new(duplicate),
            Cursor::new(wire(&f.fetches)),
            &f.rom,
            &f.firmware
        )
        .is_err()
    );
    let oversized = format!("{}\n", "x".repeat(plaid_core::trace::MAX_RECORD_BYTES + 1));
    assert!(
        inspect_boot_history(
            Cursor::new(oversized),
            Cursor::new(wire(&f.fetches)),
            &f.rom,
            &f.firmware
        )
        .is_err()
    );
}

#[test]
fn rechecking_detects_even_unreferenced_payload_and_report_changes() {
    let mut f = fixture();
    let report = inspect(&f).unwrap();
    f.history[4]["value"] = 2.into(); // outside the fetch context; counts still equal
    assert_eq!(
        inspect(&f).unwrap().scalar_fetch_witnesses,
        report.scalar_fetch_witnesses
    );
    assert!(
        verify_boot_history_report(
            &report,
            Cursor::new(wire(&f.history)),
            Cursor::new(wire(&f.fetches)),
            &f.rom,
            &f.firmware
        )
        .is_err()
    );
    let f = fixture();
    let mut report = inspect(&f).unwrap();
    report.records += 1;
    assert!(
        verify_boot_history_report(
            &report,
            Cursor::new(wire(&f.history)),
            Cursor::new(wire(&f.fetches)),
            &f.rom,
            &f.firmware
        )
        .is_err()
    );
    let mut encoded = serde_json::to_value(inspect(&f).unwrap()).unwrap();
    encoded["extra"] = true.into();
    assert!(serde_json::from_value::<AccessHistoryReport>(encoded).is_err());
    let encoded = serde_json::to_string(&inspect(&f).unwrap())
        .unwrap()
        .replace("\"fill\":1", "\"fill\":1,\"fill\":1");
    assert!(serde_json::from_str::<AccessHistoryReport>(&encoded).is_err());
}

struct ChangedOnRewind {
    cursor: Cursor<String>,
    second: String,
}
impl Read for ChangedOnRewind {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        self.cursor.read(buf)
    }
}
impl BufRead for ChangedOnRewind {
    fn fill_buf(&mut self) -> std::io::Result<&[u8]> {
        self.cursor.fill_buf()
    }
    fn consume(&mut self, amount: usize) {
        self.cursor.consume(amount)
    }
}
impl Seek for ChangedOnRewind {
    fn seek(&mut self, pos: SeekFrom) -> std::io::Result<u64> {
        if pos == SeekFrom::Start(0) {
            self.cursor = Cursor::new(self.second.clone());
        }
        self.cursor.seek(pos)
    }
}

#[test]
fn paired_source_must_stay_identical_between_validation_and_replay() {
    let mut f = fixture();
    let first = wire(&f.fetches);
    f.fetches[3]["cache_line"]["words"][1] = 17.into();
    let fetched = ChangedOnRewind {
        cursor: Cursor::new(first),
        second: wire(&f.fetches),
    };
    assert!(
        inspect_boot_history(Cursor::new(wire(&f.history)), fetched, &f.rom, &f.firmware).is_err()
    );
}
