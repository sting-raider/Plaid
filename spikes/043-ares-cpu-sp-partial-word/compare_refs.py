#!/usr/bin/env python3
"""Pinned source comparison for CPU SWL/SWR writes into SP memory.

This does not claim hardware truth. It checks whether two independent emulator
implementations imply the same full-word SP sink image and records the exact
counterexample when they do not.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import importlib.util
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GOPHER = ROOT / ".refs/gopher64"
SYSTEMTEST = ROOT / ".refs/n64-systemtest"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
SYSTEMTEST_REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"
DATA = 0x11223344

mspec = importlib.util.spec_from_file_location("partial_model_compare", HERE / "model.py")
model = importlib.util.module_from_spec(mspec)
sys.modules[mspec.name] = model
mspec.loader.exec_module(model)


def rev(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gopher_word(instr: str, offset: int) -> int:
    # Exact value passed by pinned Gopher64 SWL/SWR to data_write after address
    # alignment. rsp_interface::write_mem ignores the incoming mask and commits
    # this complete u32.
    n = offset & 3
    if instr == "SWL":
        return (DATA >> (8 * n)) & 0xffffffff
    if instr == "SWR":
        return (DATA << (8 * (3 - n))) & 0xffffffff
    raise ValueError(instr)


def ares_word(instr: str, offset: int) -> int:
    initial = bytes(range(0xa0, 0xb0))
    after, _ = model.execute(initial, instr, "big", offset)
    return int.from_bytes(after[0:4], "big")


def main() -> None:
    assert rev(GOPHER) == GOPHER_REV
    assert rev(SYSTEMTEST) == SYSTEMTEST_REV

    cpu_path = GOPHER / "src/device/cpu_instructions.rs"
    rsp_path = GOPHER / "src/device/rsp_interface.rs"
    st_path = SYSTEMTEST / "src/tests/sp_memory/mod.rs"
    cpu = cpu_path.read_text()
    rsp = rsp_path.read_text()
    st = st_path.read_text()

    # Guard the semantic source pieces used by the executable comparison.
    assert "pub fn swl(device: &mut device::Device, opcode: u32)" in cpu
    assert "let shift = 8 * n;" in cpu
    assert "(device.cpu.gpr[rt(opcode) as usize] >> shift) as u32" in cpu
    assert "pub fn swr(device: &mut device::Device, opcode: u32)" in cpu
    assert "let shift = 8 * (3 - n);" in cpu
    assert "(device.cpu.gpr[rt(opcode) as usize] << shift) as u32" in cpu
    assert "pub fn write_mem(device: &mut device::Device, address: u64, value: u32, _mask: u32)" in rsp
    assert "device::memory::masked_write_32(&mut data, value, 0xFFFFFFFF);" in rsp

    # The pinned hardware-facing systemtest establishes the general SP-memory
    # widening quirk for SB/SH, but does not contain an SWL/SWR SP-memory test.
    assert "SH/SB are broken: They overwrite the whole 32 bit" in st
    assert "pub struct SH" in st and "pub struct SB" in st
    assert "SWL" not in st and "SWR" not in st

    mismatches = []
    for instr in ("SWL", "SWR"):
        for offset in range(4):
            aw = ares_word(instr, offset)
            gw = gopher_word(instr, offset)
            if aw != gw:
                mismatches.append((instr, offset, aw, gw))
            print(f"CASE {instr} off{offset}: ares={aw:08x} gopher={gw:08x}")

    assert mismatches == [("SWR", 2, 0x22330000, 0x22334400)], mismatches
    print("PASS: pinned source comparison isolates one exact payload disagreement")
    print("mismatch=SWR/big/off2 ares=22330000 gopher=22334400")
    print("systemtest_spmem_swl_swr_oracle=absent")
    print("gopher_cpu_sha256=" + sha(cpu_path))
    print("gopher_rsp_sha256=" + sha(rsp_path))
    print("systemtest_spmem_sha256=" + sha(st_path))

if __name__ == "__main__":
    main()
