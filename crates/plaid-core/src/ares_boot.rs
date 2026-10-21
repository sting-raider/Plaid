//! Analysis-only reference execution. The native lowerer receives bytes and
//! content guards, never this executor or a guest instruction decoder.
use crate::rom::{CanonicalRom, sha256};
use serde::Deserialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    sync::{
        Mutex, OnceLock,
        atomic::{AtomicU64, Ordering},
    },
};

type MemoKey = (String, u32);

static MEMO: OnceLock<Mutex<BTreeMap<MemoKey, Capture>>> = OnceLock::new();
static SERIAL: AtomicU64 = AtomicU64::new(0);

#[derive(Debug, Clone, Deserialize)]
pub struct Capture {
    pub format: String,
    pub entry: u32,
    pub destination: u32,
    #[serde(default)]
    pub physical_start: Option<u32>,
    pub bytes: Vec<u8>,
    pub steps: u64,
    pub cpu_writes: Vec<(u32, u32)>,
    pub pi_dma: Vec<(u32, u32, u32)>,
    pub revision: String,
    pub rom_sha256: String,
    pub output_sha256: String,
    pub budget: u64,
}

/// Run from reset to the first fetch of `entry`. An in-process memo only avoids
/// replaying the same ROM/entry multiple times in one process.
pub fn execute(rom: &CanonicalRom, entry: u32) -> Result<Capture, String> {
    execute_many(rom, &[entry])?
        .remove(&entry)
        .ok_or_else(|| "ares boot capture batch omitted its requested entry".into())
}

/// Run one reset replay for every unique entry that is not already memoized.
/// Captures are validated as a complete batch before any of them enter the
/// process-local memo. The footer is metadata only and never supplies bytes.
pub fn execute_many(rom: &CanonicalRom, entries: &[u32]) -> Result<BTreeMap<u32, Capture>, String> {
    let requested: BTreeSet<_> = entries.iter().copied().collect();
    for &entry in &requested {
        validate_entry(entry)?;
    }
    if requested.is_empty() {
        return Ok(BTreeMap::new());
    }

    let memo = MEMO.get_or_init(Default::default);
    let mut captures = BTreeMap::new();
    {
        let memo = memo.lock().map_err(|e| e.to_string())?;
        for &entry in &requested {
            if let Some(capture) = memo.get(&(rom.identity.sha256.clone(), entry)) {
                captures.insert(entry, capture.clone());
            }
        }
    }
    let missing: Vec<_> = requested
        .iter()
        .copied()
        .filter(|entry| !captures.contains_key(entry))
        .collect();
    if missing.is_empty() {
        return Ok(captures);
    }

    let rows = capture_rows(rom, &missing)?;
    for (entry, capture) in rows {
        captures.insert(entry, capture);
    }
    if captures.len() != requested.len() {
        return Err("ares boot capture batch omitted a requested entry".into());
    }

    // Commit the fully validated batch under one lock. If another caller
    // completed a capture while this replay ran, retain that memoized value.
    let mut memo = memo.lock().map_err(|e| e.to_string())?;
    let mut committed = BTreeMap::new();
    for entry in requested {
        let capture = memo
            .entry((rom.identity.sha256.clone(), entry))
            .or_insert_with(|| captures[&entry].clone());
        committed.insert(entry, capture.clone());
    }
    Ok(committed)
}

fn validate_entry(entry: u32) -> Result<(), String> {
    if entry & 3 != 0 || (0x8080_0000..0xc000_0000).contains(&entry) {
        return Err("ares boot capture requires an aligned RAM or mapped target".into());
    }
    Ok(())
}

fn validate_capture(capture: &Capture, rom: &CanonicalRom, entry: u32) -> Result<(), String> {
    let end = u64::from(capture.destination) + capture.bytes.len() as u64;
    let valid_source = match capture.physical_start {
        Some(p) => {
            !(0x8000_0000..0xc000_0000).contains(&capture.destination)
                && p.is_multiple_of(4)
                && u64::from(p) + capture.bytes.len() as u64 <= 0x800000
                && end
                    <= if capture.destination < 0x8000_0000 {
                        0x8000_0000
                    } else {
                        0x1_0000_0000
                    }
        }
        None => capture.destination >= 0x8000_0000 && end <= 0x8080_0000,
    };
    if capture.format != "plaid-ares-boot-harvest-v1"
        || capture.revision != "9408cb43d4948fc3ea6e152a307a34348df3fe04"
        || capture.rom_sha256 != rom.identity.sha256
        || capture.entry != entry
        || capture.budget != 100_000_000
        || capture.steps >= capture.budget
        || capture.destination & 3 != 0
        || capture.bytes.is_empty()
        || !capture.bytes.len().is_multiple_of(4)
        || !valid_source
        || entry < capture.destination
        || u64::from(entry) >= u64::from(capture.destination) + capture.bytes.len() as u64
        || sha256(&capture.bytes) != capture.output_sha256
    {
        return Err("invalid ares boot capture identity/range/budget".into());
    }
    Ok(())
}

fn capture_rows(rom: &CanonicalRom, entries: &[u32]) -> Result<BTreeMap<u32, Capture>, String> {
    let directory = std::env::temp_dir().join(format!(
        "plaid-ares-{}-{}",
        std::process::id(),
        SERIAL.fetch_add(1, Ordering::Relaxed)
    ));
    std::fs::create_dir(&directory).map_err(|e| e.to_string())?;
    let result = (|| {
        let path = directory.join("input.z64");
        std::fs::write(&path, rom.bytes()).map_err(|e| e.to_string())?;
        let helper =
            std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../scripts/ares_boot.py");
        let entry_list = entries
            .iter()
            .map(|entry| format!("{entry:#x}"))
            .collect::<Vec<_>>()
            .join(",");
        let output = std::process::Command::new(if cfg!(windows) { "python" } else { "python3" })
            .arg(helper)
            .arg(path)
            .arg(entry_list)
            .arg("--exact-many")
            .output()
            .map_err(|e| e.to_string())?;
        if !output.status.success() {
            return Err(format!(
                "analysis-time ares failed: {}",
                String::from_utf8_lossy(&output.stderr)
            ));
        }
        parse_capture_rows(&output.stdout, rom, entries)
    })();
    let cleanup = std::fs::remove_dir_all(&directory).map_err(|e| e.to_string());
    cleanup?;
    result
}

fn parse_capture_rows(
    stdout: &[u8],
    rom: &CanonicalRom,
    entries: &[u32],
) -> Result<BTreeMap<u32, Capture>, String> {
    let requested: BTreeSet<_> = entries.iter().copied().collect();
    let output: serde_json::Value = serde_json::from_slice(stdout).map_err(|e| {
        format!(
            "ares did not reach all requested harvestable targets: {e}; {}",
            String::from_utf8_lossy(stdout)
        )
    })?;
    let rows = output
        .as_array()
        .ok_or("ares batch output is not a capture-row array")?;
    let mut captures = BTreeMap::new();
    let mut footer_seen = false;
    for (index, row) in rows.iter().enumerate() {
        let object = row
            .as_object()
            .ok_or("ares batch output contains a non-object row")?;
        // The final stop/footer record has no `entry`; it is metadata, not a
        // capture. A payload without an entry is malformed and must fail shut.
        if !object.contains_key("entry") {
            if object.contains_key("bytes") {
                return Err("ares batch output contains unkeyed payload bytes".into());
            }
            if object.contains_key("rejected_entry")
                || object
                    .get("stop_pc")
                    .and_then(serde_json::Value::as_u64)
                    .is_none()
                || object.get("remaining").and_then(serde_json::Value::as_u64) != Some(0)
                || index + 1 != rows.len()
                || footer_seen
            {
                return Err("invalid ares batch footer or rejected target".into());
            }
            footer_seen = true;
            continue;
        }
        let capture: Capture = serde_json::from_value(row.clone())
            .map_err(|e| format!("invalid ares batch capture row: {e}"))?;
        if !requested.contains(&capture.entry) {
            return Err(format!(
                "ares batch returned unrequested entry {:#010x}",
                capture.entry
            ));
        }
        validate_capture(&capture, rom, capture.entry)?;
        if captures.insert(capture.entry, capture).is_some() {
            return Err("ares batch returned a duplicate capture entry".into());
        }
    }
    if !footer_seen {
        return Err("ares batch output is missing its final footer".into());
    }
    if let Some(entry) = requested.iter().find(|entry| !captures.contains_key(entry)) {
        return Err(format!(
            "ares did not reach requested harvestable target {entry:#010x}"
        ));
    }
    Ok(captures)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rom() -> CanonicalRom {
        let mut bytes = vec![0; 0x1000];
        bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
        CanonicalRom::from_bytes(&bytes).unwrap()
    }

    fn capture(rom: &CanonicalRom, entry: u32, value: u32) -> serde_json::Value {
        let bytes = value.to_be_bytes().to_vec();
        let output_sha256 = sha256(&bytes);
        serde_json::json!({
            "format": "plaid-ares-boot-harvest-v1",
            "entry": entry,
            "destination": entry,
            "bytes": bytes,
            "steps": 17,
            "cpu_writes": [[0x1000, 0x1004]],
            "pi_dma": [],
            "revision": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
            "rom_sha256": rom.identity.sha256,
            "output_sha256": output_sha256,
            "budget": 100_000_000u64,
        })
    }

    #[test]
    fn exact_batch_rows_match_independent_rows_and_ignore_the_footer() {
        let rom = rom();
        let first = capture(&rom, 0x80001000, 0x24020001);
        let second = capture(&rom, 0x80001020, 0x2402002a);
        let footer = serde_json::json!({"stop_pc": 0x80001024u32, "remaining": 0});
        let batch = serde_json::to_vec(&serde_json::json!([
            first.clone(),
            second.clone(),
            footer.clone()
        ]))
        .unwrap();
        let captures = parse_capture_rows(&batch, &rom, &[0x80001000, 0x80001020]).unwrap();

        for (entry, row) in [(0x80001000, first), (0x80001020, second)] {
            let independent =
                serde_json::to_vec(&serde_json::json!([row, footer.clone()])).unwrap();
            let replay = parse_capture_rows(&independent, &rom, &[entry]).unwrap();
            let batched = &captures[&entry];
            let independently_replayed = &replay[&entry];
            assert_eq!(batched.entry, independently_replayed.entry);
            assert_eq!(batched.destination, independently_replayed.destination);
            assert_eq!(batched.bytes, independently_replayed.bytes);
            assert_eq!(batched.output_sha256, independently_replayed.output_sha256);
            assert_eq!(batched.steps, independently_replayed.steps);
        }
    }

    #[test]
    fn missing_or_mutated_capture_rows_reject_the_whole_batch() {
        let rom = rom();
        let first = capture(&rom, 0x80001000, 0x24020001);
        let footer = serde_json::json!({"stop_pc": 0x80001024u32, "remaining": 0});
        let missing =
            serde_json::to_vec(&serde_json::json!([first.clone(), footer.clone()])).unwrap();
        assert!(parse_capture_rows(&missing, &rom, &[0x80001000, 0x80001020]).is_err());

        let mut mutated = capture(&rom, 0x80001020, 0x2402002a);
        mutated["bytes"] = serde_json::json!([0x24, 0x02, 0x00, 0x2b]);
        let invalid = serde_json::to_vec(&serde_json::json!([first, mutated, footer])).unwrap();
        assert!(parse_capture_rows(&invalid, &rom, &[0x80001000, 0x80001020]).is_err());
    }

    #[test]
    fn footer_payload_and_unrequested_entries_are_rejected() {
        let rom = rom();
        let first = capture(&rom, 0x80001000, 0x24020001);
        let footer_with_bytes = serde_json::json!([first.clone(), {"stop_pc": 0x80001024u32,
            "remaining": 0, "bytes": [0x24, 0x02, 0x00, 0x2a]}]);
        let serialized = serde_json::to_vec(&footer_with_bytes).unwrap();
        assert!(parse_capture_rows(&serialized, &rom, &[0x80001000]).is_err());

        let unexpected = serde_json::to_vec(&serde_json::json!([
            capture(&rom, 0x80001020, 0x2402002a),
            {"stop_pc": 0x80001024u32, "remaining": 0}
        ]))
        .unwrap();
        assert!(parse_capture_rows(&unexpected, &rom, &[0x80001000]).is_err());
    }

    #[test]
    fn duplicate_rejected_and_invalid_identity_rows_fail_closed() {
        let rom = rom();
        let entry = 0x80001000;
        let first = capture(&rom, entry, 0x24020001);
        let footer = serde_json::json!({"stop_pc": 0x80001004u32, "remaining": 0});

        let duplicate = serde_json::to_vec(&serde_json::json!([
            first.clone(),
            first.clone(),
            footer.clone()
        ]))
        .unwrap();
        assert!(parse_capture_rows(&duplicate, &rom, &[entry]).is_err());

        let rejected = serde_json::to_vec(&serde_json::json!([
            {"rejected_entry": entry, "steps": 19, "reason": "stale instruction cache"},
            footer.clone()
        ]))
        .unwrap();
        assert!(parse_capture_rows(&rejected, &rom, &[entry]).is_err());

        for (field, value) in [
            ("revision", serde_json::json!("unexpected-reference")),
            ("budget", serde_json::json!(99_999_999u64)),
            ("destination", serde_json::json!(0x807ffffcu32)),
        ] {
            let mut invalid = first.clone();
            invalid[field] = value;
            let serialized =
                serde_json::to_vec(&serde_json::json!([invalid, footer.clone()])).unwrap();
            assert!(
                parse_capture_rows(&serialized, &rom, &[entry]).is_err(),
                "accepted invalid {field}"
            );
        }

        let upper_entry = 0x807ffffc;
        let mut overflow = capture(&rom, upper_entry, 0x24020001);
        let bytes = [0x24, 0x02, 0x00, 0x01, 0x03, 0xe0, 0x00, 0x08];
        overflow["bytes"] = serde_json::json!(bytes);
        overflow["output_sha256"] = serde_json::json!(sha256(&bytes));
        let serialized = serde_json::to_vec(&serde_json::json!([
            overflow,
            {"stop_pc": 0x807ffffcu32, "remaining": 0}
        ]))
        .unwrap();
        assert!(parse_capture_rows(&serialized, &rom, &[upper_entry]).is_err());

        assert!(validate_entry(0x80001002).is_err());
        assert!(validate_entry(0x7fffffff).is_err());
        assert!(validate_entry(0x80800000).is_err());
    }

    #[test]
    fn mapped_capture_requires_bounded_physical_source_and_virtual_extent() {
        let rom = rom();
        let entry = 0x60001000;
        let mut row = capture(&rom, entry, 0x2402002a);
        let parse = |row| {
            parse_capture_rows(
                &serde_json::to_vec(&serde_json::json!([
                row, {"remaining": 0, "stop_pc": entry}
                ]))
                .unwrap(),
                &rom,
                &[entry],
            )
        };
        assert!(parse(row.clone()).is_err());
        row["physical_start"] = serde_json::json!(0x2000);
        assert!(parse(row.clone()).is_ok());
        for (key, value) in [
            ("physical_start", 0x800000u32),
            ("physical_start", 0x2002),
            ("destination", 0x80001000),
            ("destination", 0x60001004),
            ("destination", 0x7fffffff),
        ] {
            let mut changed = row.clone();
            changed[key] = serde_json::json!(value);
            assert!(parse(changed).is_err(), "{key}={value:x}");
        }
    }
}
