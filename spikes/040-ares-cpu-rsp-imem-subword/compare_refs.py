#!/usr/bin/env python3
"""Source-guarded comparison of pinned Gopher64/Mupen SP-memory subword handling.

This is an independent source comparison, not a hardware execution oracle.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
GOPHER = ROOT / ".refs/gopher64"
MUPEN = ROOT / ".refs/mupen64plus-core"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
MUPEN_REV = "ba95bab92a76744753bfe61470823a4937850ab0"


def rev(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def merge(old: int, value: int, mask: int) -> int:
    return (old & ~mask) | (value & mask)


def main() -> None:
    assert rev(GOPHER) == GOPHER_REV
    assert rev(MUPEN) == MUPEN_REV

    gpath = GOPHER / "src/device/rsp_interface.rs"
    mipu = MUPEN / "src/device/r4300/mips_instructions.def"
    mrsp = MUPEN / "src/device/rcp/rsp/rsp_core.c"
    g = gpath.read_text()
    mi = mipu.read_text()
    mr = mrsp.read_text()

    assert "pub fn write_mem(device: &mut device::Device, address: u64, value: u32, _mask: u32)" in g
    assert "device::memory::masked_write_32(&mut data, value, 0xFFFFFFFF);" in g
    assert "SH/SB are broken: They overwrite the whole 32 bit, filling everything that isn't written with zeroes" in g

    assert "r4300_write_aligned_word(r4300, lsaddr, (uint32_t)*lsrtp << shift, UINT32_C(0xff) << shift);" in mi
    assert "r4300_write_aligned_word(r4300, lsaddr, (uint32_t)*lsrtp << shift, UINT32_C(0xffff) << shift);" in mi
    assert "masked_write(&sp->mem[addr], value, mask);" in mr

    old = 0xA0A1A2A3
    report = []
    for off in range(4):
        shift = ((off & 3) ^ 3) << 3
        mask = 0xFF << shift
        value = 0x88 << shift
        mupen = merge(old, value, mask)
        widened = value  # ares/Gopher-style full-word sink with zero in untouched lanes
        assert mupen != widened
        report.append({"op": "SB", "off": off, "old": old, "mupen": mupen, "widened": widened})
    for off in (0, 2):
        shift = ((off & 2) ^ 2) << 3
        mask = 0xFFFF << shift
        value = 0x7788 << shift
        mupen = merge(old, value, mask)
        widened = value
        assert mupen != widened
        report.append({"op": "SH", "off": off, "old": old, "mupen": mupen, "widened": widened})

    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    print("PASS: pinned Gopher widening bug is source-explicit; pinned Mupen preserves masked lanes")
    print("comparison_sha256=" + hashlib.sha256(encoded).hexdigest())
    for name, path in (("gopher_rsp", gpath), ("mupen_ipu", mipu), ("mupen_rsp", mrsp)):
        print(f"source_{name}_sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
