#!/usr/bin/env python3
"""Source-guarded comparison of pinned SP-memory subword references.

n64-systemtest provides hardware-derived expected SPMEM behavior. Gopher64 models
that same widening and explicitly calls SH/SB "broken" in the hardware-facing
sense. Pinned Mupen instead preserves masked lanes and therefore disagrees with
that oracle. This script guards those exact source facts; it does not execute a
physical N64.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
GOPHER = ROOT / ".refs/gopher64"
MUPEN = ROOT / ".refs/mupen64plus-core"
SYSTEMTEST = ROOT / ".refs/n64-systemtest"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
MUPEN_REV = "ba95bab92a76744753bfe61470823a4937850ab0"
SYSTEMTEST_REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"


def rev(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def merge(old: int, value: int, mask: int) -> int:
    return (old & ~mask) | (value & mask)


def main() -> None:
    assert rev(GOPHER) == GOPHER_REV
    assert rev(MUPEN) == MUPEN_REV
    assert rev(SYSTEMTEST) == SYSTEMTEST_REV

    gpath = GOPHER / "src/device/rsp_interface.rs"
    mipu = MUPEN / "src/device/r4300/mips_instructions.def"
    mrsp = MUPEN / "src/device/rcp/rsp/rsp_core.c"
    stpath = SYSTEMTEST / "src/tests/sp_memory/mod.rs"
    g = gpath.read_text()
    mi = mipu.read_text()
    mr = mrsp.read_text()
    st = stpath.read_text()

    assert "pub fn write_mem(device: &mut device::Device, address: u64, value: u32, _mask: u32)" in g
    assert "device::memory::masked_write_32(&mut data, value, 0xFFFFFFFF);" in g
    assert "SH/SB are broken: They overwrite the whole 32 bit, filling everything that isn't written with zeroes" in g

    assert "r4300_write_aligned_word(r4300, lsaddr, (uint32_t)*lsrtp << shift, UINT32_C(0xff) << shift);" in mi
    assert "r4300_write_aligned_word(r4300, lsaddr, (uint32_t)*lsrtp << shift, UINT32_C(0xffff) << shift);" in mi
    assert "masked_write(&sp->mem[addr], value, mask);" in mr

    assert "SH/SB are broken: They overwrite the whole 32 bit, filling everything that isn't written with zeroes" in st
    assert "0x56780000, \"Reading 32 bit from SPMEM[0]\"" in st
    assert "0x12345678, \"Reading 32 bit from SPMEM[4]\"" in st
    assert "0x78000000, \"Reading 32 bit from SPMEM[0]\"" in st
    assert "0x34567800, \"Reading 32 bit from SPMEM[8]\"" in st

    old = 0xA0A1A2A3
    rt = 0x12345678
    report = []
    # Big-endian hardware oracle cases. Mupen masks the nominal byte/halfword;
    # the hardware-facing widened path replaces the full word with shifted rt.u32.
    for off in range(4):
        shift = ((off & 3) ^ 3) << 3
        mask = 0xFF << shift
        shifted = (rt << shift) & 0xFFFFFFFF
        mupen = merge(old, shifted, mask)
        hardware = shifted
        assert mupen != hardware
        report.append({"op": "SB", "off": off, "old": old, "mupen": mupen, "hardware": hardware})
    for off in (0, 2):
        shift = ((off & 2) ^ 2) << 3
        mask = 0xFFFF << shift
        shifted = (rt << shift) & 0xFFFFFFFF
        mupen = merge(old, shifted, mask)
        hardware = shifted
        assert mupen != hardware
        report.append({"op": "SH", "off": off, "old": old, "mupen": mupen, "hardware": hardware})

    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    print("PASS: n64-systemtest/Gopher widening agrees; pinned Mupen masked sink disagrees")
    print("comparison_sha256=" + hashlib.sha256(encoded).hexdigest())
    for name, path in (("gopher_rsp", gpath), ("mupen_ipu", mipu), ("mupen_rsp", mrsp), ("systemtest_spmem", stpath)):
        print(f"source_{name}_sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
