//! Analysis-only reference execution. The native lowerer receives bytes and
//! content guards, never this executor or a guest instruction decoder.
use crate::rom::{CanonicalRom, sha256};
use serde::Deserialize;
use std::{
    collections::BTreeMap,
    sync::{
        Mutex, OnceLock,
        atomic::{AtomicU64, Ordering},
    },
};

#[derive(Debug, Clone, Deserialize)]
pub struct Capture {
    pub format: String,
    pub entry: u32,
    pub destination: u32,
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
/// replaying the same ROM/entry for multiple loads in one composition.
pub fn execute(rom: &CanonicalRom, entry: u32) -> Result<Capture, String> {
    static MEMO: OnceLock<Mutex<BTreeMap<(String, u32), Capture>>> = OnceLock::new();
    static SERIAL: AtomicU64 = AtomicU64::new(0);
    if entry & 3 != 0 || !(0x8000_0000..0x8080_0000).contains(&entry) {
        return Err("ares boot capture requires an aligned KSEG0 RAM target".into());
    }
    let key = (rom.identity.sha256.clone(), entry);
    let memo = MEMO.get_or_init(Default::default);
    if let Some(capture) = memo.lock().map_err(|e| e.to_string())?.get(&key) {
        return Ok(capture.clone());
    }
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
        let output = std::process::Command::new(if cfg!(windows) { "python" } else { "python3" })
            .arg(helper)
            .arg(path)
            .arg(format!("{entry:#x}"))
            .output()
            .map_err(|e| e.to_string())?;
        if !output.status.success() {
            return Err(format!(
                "analysis-time ares failed: {}",
                String::from_utf8_lossy(&output.stderr)
            ));
        }
        let capture: Capture = serde_json::from_slice(&output.stdout).map_err(|e| {
            format!(
                "ares did not reach a harvestable target: {e}; {}",
                String::from_utf8_lossy(&output.stdout)
            )
        })?;
        if capture.format != "plaid-ares-boot-harvest-v1"
            || capture.revision != "9408cb43d4948fc3ea6e152a307a34348df3fe04"
            || capture.rom_sha256 != rom.identity.sha256
            || capture.entry != entry
            || capture.budget != 100_000_000
            || capture.steps >= capture.budget
            || capture.destination & 3 != 0
            || capture.bytes.is_empty()
            || !capture.bytes.len().is_multiple_of(4)
            || capture.destination < 0x8000_0000
            || u64::from(capture.destination) + capture.bytes.len() as u64 > 0x8080_0000
            || entry < capture.destination
            || u64::from(entry) >= u64::from(capture.destination) + capture.bytes.len() as u64
            || sha256(&capture.bytes) != capture.output_sha256
        {
            return Err("invalid ares boot capture identity/range/budget".into());
        }
        Ok(capture)
    })();
    let cleanup = std::fs::remove_dir_all(&directory).map_err(|e| e.to_string());
    cleanup?;
    let capture = result?;
    memo.lock()
        .map_err(|e| e.to_string())?
        .insert(key, capture.clone());
    Ok(capture)
}
