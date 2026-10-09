#!/usr/bin/env python3
"""Execute exact-pinned Gopher64 SWL/SWR against CPU-visible SP memory.

This is a research-only patch injector. It appends a cfg(test) module to the
exact pinned Gopher64 checkout, executes encoded SWL/SWR through Gopher's real
CPU decoder and SP memory map, and removes the patch afterward. An observer
replaces only the SP memory-map callback and delegates immediately to the real
sink; baseline and observed complete SP memory must remain identical.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
GOPHER = Path(os.environ.get("GOPHER64_DIR", ROOT / ".refs" / "gopher64")).resolve()
REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
MARKER = "// PLAID_GOPHER_SWR_SP_EXEC_PROBE_V1"
PROBE_PATH = GOPHER / "src/plaid_swr_sp_probe.rs"
LIB_PATH = GOPHER / "src/lib.rs"

RUST_PROBE = r'''
use crate::device;
use std::sync::Mutex;

const RS: usize = 1;
const RT: usize = 2;
const SWL_MAJOR: u32 = 42;
const SWR_MAJOR: u32 = 46;
const KSEG1_SP: u64 = 0xffff_ffff_a400_0000;
const SP_MAP_INDEX: usize = 0x0400_0000usize >> 16;
const PAYLOAD: u32 = 0x1122_3344;

static WRITES: Mutex<Vec<(u64, u32, u32)>> = Mutex::new(Vec::new());

fn observed_sp_write(d: &mut device::Device, address: u64, value: u32, mask: u32) {
    WRITES.lock().unwrap().push((address, value, mask));
    device::rsp_interface::write_mem(d, address, value, mask);
}

fn opcode(major: u32, offset: u16) -> u32 {
    (major << 26) | ((RS as u32) << 21) | ((RT as u32) << 16) | offset as u32
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct Obs {
    all_sp: Vec<u8>,
    word: [u8; 4],
    neighbor: [u8; 4],
    writes: Vec<(u64, u32, u32)>,
}

fn run_one(major: u32, bank: u64, offset: u16, observed: bool) -> Obs {
    let mut d = device::Device::new(false);
    device::memory::init(&mut d);
    device::rsp_interface::init(&mut d);
    device::cpu::map_instructions(&mut d);

    let start = bank as usize;
    d.rsp.mem[start..start + 8].copy_from_slice(&[0xa0,0xa1,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7]);
    d.cpu.gpr[RS] = KSEG1_SP + bank;
    d.cpu.gpr[RT] = PAYLOAD as u64;
    WRITES.lock().unwrap().clear();
    if observed {
        d.memory.memory_map_write[SP_MAP_INDEX] = observed_sp_write;
    }

    let op = opcode(major, offset);
    let func = device::cpu::decode_opcode(&d, op);
    func(&mut d, op);

    Obs {
        all_sp: d.rsp.mem.to_vec(),
        word: d.rsp.mem[start..start + 4].try_into().unwrap(),
        neighbor: d.rsp.mem[start + 4..start + 8].try_into().unwrap(),
        writes: WRITES.lock().unwrap().clone(),
    }
}

fn hex4(v: &[u8; 4]) -> String {
    v.iter().map(|b| format!("{b:02x}")).collect::<String>()
}

fn event_text(v: &[(u64, u32, u32)]) -> String {
    v.iter()
        .map(|(a, x, m)| format!("{a:08x}:{x:08x}:{m:08x}"))
        .collect::<Vec<_>>()
        .join(",")
}

fn check(name: &str, major: u32, bank: u64, offset: u16, expected: u32) {
    let base = run_one(major, bank, offset, false);
    let seen = run_one(major, bank, offset, true);
    assert_eq!(base.all_sp, seen.all_sp, "observer changed SP state: {name}");
    assert_eq!(base.word, expected.to_be_bytes(), "wrong final word: {name}");
    assert_eq!(base.neighbor, [0xa4,0xa5,0xa6,0xa7], "neighbor changed: {name}");
    assert_eq!(seen.writes.len(), 1, "expected one completed SP callback: {name}");
    let expected_phys = 0x0400_0000u64 + bank;
    assert_eq!(seen.writes[0].0, expected_phys, "callback address not aligned SP word: {name}");
    assert_eq!(seen.writes[0].1, expected, "callback payload differs from final word: {name}");
    println!(
        "PLAID_PROBE scenario={name} final={} neighbor={} writes={} event={} neutrality=equal",
        hex4(&base.word), hex4(&base.neighbor), seen.writes.len(), event_text(&seen.writes)
    );
}

#[test]
fn gopher_swl_swr_sp_exec() {
    // Source-derived exact-pin Gopher expectations. The purpose of executing
    // them is to falsify these values if the real decoder/memory path differs.
    let swl = [0x1122_3344, 0x0011_2233, 0x0000_1122, 0x0000_0011];
    let swr = [0x4400_0000, 0x3344_0000, 0x2233_4400, 0x1122_3344];

    for &(bank_name, bank) in &[("dmem", 0u64), ("imem", 0x1000u64)] {
        for offset in 0u16..4 {
            check(
                &format!("swl_{bank_name}_off{offset}"),
                SWL_MAJOR,
                bank,
                offset,
                swl[offset as usize],
            );
            check(
                &format!("swr_{bank_name}_off{offset}"),
                SWR_MAJOR,
                bank,
                offset,
                swr[offset as usize],
            );
        }
    }
}
'''


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> str:
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode != 0:
        sys.stdout.write(p.stdout)
        raise SystemExit(f"command failed ({p.returncode}): {' '.join(cmd)}")
    return p.stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_guard() -> dict[str, str]:
    if not GOPHER.is_dir():
        raise SystemExit(f"missing exact Gopher checkout: {GOPHER}")
    head = run(["git", "rev-parse", "HEAD"], GOPHER).strip()
    if head != REV:
        raise SystemExit(f"Gopher revision mismatch: {head} != {REV}")
    dirty = run(["git", "status", "--porcelain"], GOPHER).strip()
    if dirty:
        raise SystemExit(f"Gopher checkout must begin clean:\n{dirty}")

    cpu = GOPHER / "src/device/cpu_instructions.rs"
    cpu_map = GOPHER / "src/device/cpu.rs"
    memory = GOPHER / "src/device/memory.rs"
    rsp = GOPHER / "src/device/rsp_interface.rs"
    cpu_text = cpu.read_text()
    map_text = cpu_map.read_text()
    memory_text = memory.read_text()
    rsp_text = rsp.read_text()

    swl = cpu_text.split("pub fn swl(", 1)[1].split("pub fn sw(", 1)[0]
    swr = cpu_text.split("pub fn swr(", 1)[1].split("pub fn cache(", 1)[0]
    assert swl.count("device::memory::data_write(") == 1
    assert swr.count("device::memory::data_write(") == 1
    assert "device::cpu_instructions::swl" in map_text
    assert "device::cpu_instructions::swr" in map_text
    assert "device.memory.memory_map_write[i] = device::rsp_interface::write_mem;" in memory_text
    assert "device::memory::masked_write_32(&mut data, value, 0xFFFFFFFF);" in rsp_text
    assert "copy_from_slice(&data.to_be_bytes())" in rsp_text

    return {
        "cpu_instructions_rs": sha256(cpu),
        "cpu_rs": sha256(cpu_map),
        "memory_rs": sha256(memory),
        "rsp_interface_rs": sha256(rsp),
    }


def install_probe() -> None:
    text = LIB_PATH.read_text()
    if MARKER in text or PROBE_PATH.exists():
        raise SystemExit("probe already installed")
    LIB_PATH.write_text(text + f"\n{MARKER}\n#[cfg(test)]\nmod plaid_swr_sp_probe;\n")
    PROBE_PATH.write_text(RUST_PROBE)


def remove_probe() -> None:
    run(["git", "checkout", "--", "src/lib.rs"], GOPHER, check=False)
    if PROBE_PATH.exists():
        PROBE_PATH.unlink()


def execute_once() -> list[str]:
    env = os.environ.copy()
    env["CARGO_TERM_COLOR"] = "never"
    p = subprocess.run(
        [
            "cargo", "test", "--no-default-features", "--lib",
            "plaid_swr_sp_probe::gopher_swl_swr_sp_exec",
            "--", "--nocapture", "--test-threads=1",
        ],
        cwd=GOPHER,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    sys.stdout.write(p.stdout)
    if p.returncode != 0:
        raise SystemExit(f"Gopher probe failed with exit {p.returncode}")
    lines = sorted(
        line.strip()[line.index("PLAID_PROBE "):]
        for line in p.stdout.splitlines()
        if "PLAID_PROBE " in line
    )
    if len(lines) != 16:
        raise SystemExit(f"expected 16 probe records, got {len(lines)}")
    return lines


def parse(lines: list[str]) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in lines:
        fields = dict(part.split("=", 1) for part in line.split()[1:])
        rows[fields["scenario"]] = fields
    return rows


def main() -> None:
    source_hashes = source_guard()
    install_probe()
    try:
        first = execute_once()
        second = execute_once()
        if first != second:
            raise SystemExit("probe records changed across repeated executions")
        rows = parse(first)
        for bank in ("dmem", "imem"):
            key = f"swr_{bank}_off2"
            if rows[key]["final"] != "22334400":
                raise SystemExit(f"discriminating case falsified source model: {key}={rows[key]['final']}")
            if rows[key]["writes"] != "1" or rows[key]["neutrality"] != "equal":
                raise SystemExit(f"bad callback/neutrality evidence for {key}")
    finally:
        remove_probe()

    result = {
        "plaid_base": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
        "gopher_revision": REV,
        "source_sha256": source_hashes,
        "repeat_deterministic": True,
        "observer_neutrality": "complete SP memory equal for all 16 cases",
        "cases": rows,
        "discriminating_gopher_swr_off2": "22334400",
        "prior_exact_ares_swr_off2": "22330000",
        "hardware_truth": "unresolved",
    }
    encoded = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    print("PASS: exact pinned Gopher64 executed SWL/SWR through the real SP memory map")
    print("cases=16/16 repeat=identical observer_neutrality=equal")
    print("gopher_swr_big_off2=22334400 ares_swr_big_off2=22330000")
    print("RESULT_SHA256=" + digest)
    for line in first:
        print(line)


if __name__ == "__main__":
    main()
