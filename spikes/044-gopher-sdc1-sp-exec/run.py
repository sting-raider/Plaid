#!/usr/bin/env python3
"""Execute pinned Gopher64 COP1 stores into CPU-visible SP memory."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
GOPHER = ROOT / ".refs" / "gopher64"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
MARKER = "// PLAID_GOPHER_SDC1_SP_EXEC_PROBE"

RUST_PROBE = r'''
use crate::device;
use std::sync::Mutex;

const SP_MAP_INDEX: usize = 0x04000000usize >> 16;
const RS: u32 = 1;
const FT: u32 = 3;
const OPC_SWC1: u32 = 57;
const OPC_SDC1: u32 = 61;
const SENTINEL_LEN: usize = 12;

static EVENTS: Mutex<Vec<(u64, u32, u32)>> = Mutex::new(Vec::new());

fn observed_rsp_write(device: &mut device::Device, address: u64, value: u32, mask: u32) {
    EVENTS.lock().unwrap().push((address, value, mask));
    device::rsp_interface::write_mem(device, address, value, mask);
}

fn opcode(primary: u32, rs: u32, ft: u32) -> u32 {
    (primary << 26) | (rs << 21) | (ft << 16)
}

fn make_device(fr: bool, cu1: bool) -> Box<device::Device> {
    let mut d = device::Device::new(false);
    device::memory::init(&mut d);
    device::rsp_interface::init(&mut d);
    let mut status = 0;
    if fr { status |= device::cop0::COP0_STATUS_FR; }
    if cu1 { status |= device::cop0::COP0_STATUS_CU1; }
    d.cpu.cop0.regs[device::cop0::COP0_STATUS_REG] = status;
    d
}

fn seed_window(d: &mut device::Device, start: usize) {
    let seed: Vec<u8> = (0..SENTINEL_LEN)
        .map(|i| 0xa0u8.wrapping_add(i as u8))
        .collect();
    d.rsp.mem[start..start + SENTINEL_LEN].copy_from_slice(&seed);
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect::<String>()
}

fn event_hex(events: &[(u64, u32, u32)]) -> String {
    events.iter()
        .map(|(a, v, m)| format!("{a:08x}:{v:08x}:{m:08x}"))
        .collect::<Vec<_>>()
        .join(",")
}

fn run_sdc1(base: u64, fr: bool, payload: u64, observed: bool, cu1: bool)
    -> (Vec<u8>, Vec<u8>, Vec<(u64, u32, u32)>)
{
    let mut d = make_device(fr, cu1);
    let start = (base as usize) & 0x1fff;
    seed_window(&mut d, start);
    d.cpu.gpr[RS as usize] = base;
    device::cop1::set_fpr_double(&mut d, FT as usize, f64::from_bits(payload));
    EVENTS.lock().unwrap().clear();
    if observed { d.memory.memory_map_write[SP_MAP_INDEX] = observed_rsp_write; }
    device::cop1::sdc1(&mut d, opcode(OPC_SDC1, RS, FT));
    let window = d.rsp.mem[start..start + SENTINEL_LEN].to_vec();
    let all = d.rsp.mem.to_vec();
    let events = EVENTS.lock().unwrap().clone();
    if !observed { assert!(events.is_empty()); }
    (all, window, events)
}

fn run_swc1(base: u64, bits: u32, observed: bool)
    -> (Vec<u8>, Vec<u8>, Vec<(u64, u32, u32)>)
{
    let mut d = make_device(true, true);
    let start = (base as usize) & 0x1fff;
    seed_window(&mut d, start);
    d.cpu.gpr[RS as usize] = base;
    device::cop1::set_fpr_single(&mut d, FT as usize, f32::from_bits(bits), false);
    EVENTS.lock().unwrap().clear();
    if observed { d.memory.memory_map_write[SP_MAP_INDEX] = observed_rsp_write; }
    device::cop1::swc1(&mut d, opcode(OPC_SWC1, RS, FT));
    let window = d.rsp.mem[start..start + SENTINEL_LEN].to_vec();
    let all = d.rsp.mem.to_vec();
    let events = EVENTS.lock().unwrap().clone();
    if !observed { assert!(events.is_empty()); }
    (all, window, events)
}

fn check_sdc1(name: &str, base: u64, fr: bool, payload: u64) {
    let (baseline_all, baseline, _) = run_sdc1(base, fr, payload, false, true);
    let (observed_all, observed, events) = run_sdc1(base, fr, payload, true, true);
    assert_eq!(baseline_all, observed_all, "observer changed SP state for {name}");
    assert_eq!(baseline, observed);
    assert_eq!(&observed[..8], &payload.to_be_bytes());
    assert_eq!(&observed[8..], &[0xa8, 0xa9, 0xaa, 0xab]);
    let phys = base & 0x1fff_ffff;
    assert_eq!(events, vec![
        (phys, (payload >> 32) as u32, 0xffff_ffff),
        (phys + 4, payload as u32, 0xffff_ffff),
    ]);
    println!(
        "PLAID_PROBE scenario={name} neutrality=equal writes={} events={} bytes={} next={}",
        events.len(), event_hex(&events), hex(&observed[..8]), hex(&observed[8..])
    );
}

fn check_swc1(name: &str, base: u64, bits: u32) {
    let (baseline_all, baseline, _) = run_swc1(base, bits, false);
    let (observed_all, observed, events) = run_swc1(base, bits, true);
    assert_eq!(baseline_all, observed_all, "observer changed SP state for {name}");
    assert_eq!(baseline, observed);
    assert_eq!(&observed[..4], &bits.to_be_bytes());
    assert_eq!(&observed[4..], &[0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xab]);
    let phys = base & 0x1fff_ffff;
    assert_eq!(events, vec![(phys, bits, 0xffff_ffff)]);
    println!(
        "PLAID_PROBE scenario={name} neutrality=equal writes={} events={} bytes={} next={}",
        events.len(), event_hex(&events), hex(&observed[..4]), hex(&observed[4..8])
    );
}

#[test]
fn gopher_cop1_sp_storage_effect() {
    check_sdc1("sdc1_dmem_fr1", 0xffff_ffff_a400_0020, true, 0x1122_3344_5566_7788);
    check_sdc1("sdc1_imem_fr1", 0xffff_ffff_a400_1020, true, 0x0123_4567_89ab_cdef);
    check_sdc1("sdc1_dmem_fr0_odd", 0xffff_ffff_a400_0040, false, 0x1020_3040_5060_7080);
    check_swc1("swc1_dmem_control", 0xffff_ffff_a400_0060, 0xdead_beef);
    check_swc1("swc1_imem_control", 0xffff_ffff_a400_1060, 0x1357_9bdf);

    let base = 0xffff_ffff_a400_0080;
    let (baseline_all, baseline, _) = run_sdc1(base, true, 0x8877_6655_4433_2211, false, false);
    let (observed_all, observed, events) = run_sdc1(base, true, 0x8877_6655_4433_2211, true, false);
    assert_eq!(baseline_all, observed_all);
    assert_eq!(baseline, observed);
    assert!(events.is_empty());
    assert_eq!(observed, vec![0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xab]);
    println!(
        "PLAID_PROBE scenario=sdc1_cu1_disabled neutrality=equal writes=0 events=none bytes={} next={}",
        hex(&observed[..8]), hex(&observed[8..])
    );
}
'''


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=GOPHER, text=True).strip()


def source_guard() -> str:
    if not GOPHER.is_dir():
        raise SystemExit(f"missing exact Gopher checkout: {GOPHER}")
    head = git("rev-parse", "HEAD")
    if head != GOPHER_REV:
        raise SystemExit(f"Gopher pin mismatch: expected {GOPHER_REV}, got {head}")

    cop1 = (GOPHER / "src/device/cop1.rs").read_text()
    memory = (GOPHER / "src/device/memory.rs").read_text()
    rsp = (GOPHER / "src/device/rsp_interface.rs").read_text()
    start = cop1.index("pub fn sdc1(")
    end = cop1.index("fn mfc1(", start)
    sdc1 = cop1[start:end]
    assert sdc1.count("device::memory::data_write(") == 2
    assert "phys_address + 4" in sdc1
    assert "u32::from_ne_bytes(value[4..8].try_into().unwrap())" in sdc1
    assert "u32::from_ne_bytes(value[0..4].try_into().unwrap())" in sdc1
    assert "device.memory.memory_map_write[(phys_address >> 16) as usize]" in memory
    assert "device.memory.memory_map_write[i] = device::rsp_interface::write_mem;" in memory
    assert "device.rsp.mem[masked_address..masked_address + 4].copy_from_slice(&data.to_be_bytes());" in rsp

    evidence = {
        "gopher_revision": GOPHER_REV,
        "sdc1_data_write_calls": 2,
        "sdc1_second_address": True,
        "sp_memory_map": "rsp_interface::write_mem",
        "sp_primitive_sink_bytes": 4,
    }
    encoded = (json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    print("PASS: exact pinned Gopher source topology guarded")
    print("source_guard_sha256=" + digest)
    print(encoded.decode().strip())
    return digest


def install_probe() -> None:
    lib = GOPHER / "src/lib.rs"
    probe = GOPHER / "src/plaid_sdc1_probe.rs"
    text = lib.read_text()
    if MARKER not in text:
        lib.write_text(text + f"\n{MARKER}\n#[cfg(test)]\nmod plaid_sdc1_probe;\n")
    probe.write_text(RUST_PROBE)


def extract_probe_lines(output: str) -> list[str]:
    lines: list[str] = []
    for raw in output.splitlines():
        marker = raw.find("PLAID_PROBE ")
        if marker >= 0:
            lines.append(raw[marker:].strip())
    return lines


def run_once() -> list[str]:
    env = os.environ.copy()
    env["CARGO_TERM_COLOR"] = "never"
    env["RUST_BACKTRACE"] = "1"
    cmd = [
        "cargo", "test", "--no-default-features", "--lib",
        "plaid_sdc1_probe::gopher_cop1_sp_storage_effect",
        "--", "--nocapture", "--test-threads=1",
    ]
    proc = subprocess.run(
        cmd, cwd=GOPHER, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit(f"Gopher executable probe failed with exit {proc.returncode}")
    lines = extract_probe_lines(proc.stdout)
    if len(lines) != 6:
        raise SystemExit(f"expected 6 probe lines, got {len(lines)}: {lines!r}")
    return lines


def verify(lines: list[str]) -> None:
    by_name = {}
    for line in lines:
        fields = dict(part.split("=", 1) for part in line.split()[1:] if "=" in part)
        by_name[fields["scenario"]] = fields

    for name in ("sdc1_dmem_fr1", "sdc1_imem_fr1", "sdc1_dmem_fr0_odd"):
        row = by_name[name]
        assert row["neutrality"] == "equal"
        assert row["writes"] == "2"
        assert row["events"].count(",") == 1
    for name in ("swc1_dmem_control", "swc1_imem_control"):
        row = by_name[name]
        assert row["neutrality"] == "equal"
        assert row["writes"] == "1"
        assert "," not in row["events"]
    row = by_name["sdc1_cu1_disabled"]
    assert row["neutrality"] == "equal"
    assert row["writes"] == "0"
    assert row["events"] == "none"


def main() -> None:
    source_guard()
    install_probe()
    first = run_once()
    second = run_once()
    if first != second:
        raise SystemExit("probe output changed across repeated executions")
    verify(first)
    payload = ("\n".join(first) + "\n").encode()
    digest = hashlib.sha256(payload).hexdigest()
    print("PASS: exact-pin Gopher COP1-to-SP executable probe repeated identically")
    print("results_sha256=" + digest)
    for line in first:
        print(line)


if __name__ == "__main__":
    main()
