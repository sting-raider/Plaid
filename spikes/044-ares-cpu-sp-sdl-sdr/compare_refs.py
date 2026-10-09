#!/usr/bin/env python3
"""Compare exact pinned ares SP SDL/SDR effects with Gopher64 and n64-systemtest evidence.

This is a source comparison, not a hardware oracle for SDL/SDR. The hardware-facing
systemtest validates the aligned SD control only and has no SDL/SDR cases.
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
DATA = 0x1122334455667788

spec = importlib.util.spec_from_file_location("sp_sdl_sdr_model_compare", HERE / "model.py")
model = importlib.util.module_from_spec(spec); sys.modules[spec.name] = model; spec.loader.exec_module(model)


def rev(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gopher_big_image(instr: str, offset: int) -> bytes:
    """Pinned Gopher64 CPU partial-store value plus its SP sink ignoring both masks."""
    initial = bytearray(range(0xa0, 0xa8))
    n = offset & 7
    if instr == "SDL":
        value = DATA >> (8 * n)
    elif instr == "SDR":
        value = (DATA << (8 * (7 - n))) & 0xffffffffffffffff
    else:
        raise ValueError(instr)
    # cpu_instructions.rs issues both 32-bit data_write calls. rsp_interface::write_mem
    # ignores each incoming mask and commits the complete u32 value.
    initial[0:4] = ((value >> 32) & 0xffffffff).to_bytes(4, "big")
    initial[4:8] = (value & 0xffffffff).to_bytes(4, "big")
    return bytes(initial)


def ares_big_image(instr: str, offset: int) -> bytes:
    initial = bytes(range(0xa0, 0xb8))
    after, _ = model.execute(initial, instr, "big", offset, bank="imem")
    return after[:8]


def main() -> None:
    assert rev(GOPHER) == GOPHER_REV
    assert rev(SYSTEMTEST) == SYSTEMTEST_REV
    cpu_path = GOPHER / "src/device/cpu_instructions.rs"
    rsp_path = GOPHER / "src/device/rsp_interface.rs"
    st_path = SYSTEMTEST / "src/tests/sp_memory/mod.rs"
    cpu = cpu_path.read_text()
    rsp = rsp_path.read_text()
    st = st_path.read_text()

    assert "pub fn sdl(device: &mut device::Device, opcode: u32)" in cpu
    assert "pub fn sdr(device: &mut device::Device, opcode: u32)" in cpu
    assert "let shift = 8 * n;" in cpu
    assert "let shift = 8 * (7 - n);" in cpu
    assert "(value >> 32) as u32" in cpu
    assert "phys_address + 4" in cpu
    assert "pub fn write_mem(device: &mut device::Device, address: u64, value: u32, _mask: u32)" in rsp
    assert "device::memory::masked_write_32(&mut data, value, 0xFFFFFFFF);" in rsp

    # This pinned hardware-facing suite directly validates the same surprising SD
    # sink width that ares produces, but contains no SDL/SDR test.
    assert "SD is broken: It only writes the upper 32 bit of the value, touching only 4 bytes" in st
    assert "pub struct SD {}" in st
    assert "0xABCDEF98_76543210" in st
    assert "0xABCDEF98" in st and "0xBADDECAF" in st
    assert "SDL" not in st and "SDR" not in st

    mismatches: list[tuple[str,int,str,str]] = []
    for instr in ("SDL", "SDR"):
        for offset in range(8):
            ares = ares_big_image(instr, offset)
            gopher = gopher_big_image(instr, offset)
            print(f"CASE {instr} off{offset}: ares={ares.hex()} gopher={gopher.hex()}")
            if ares != gopher:
                mismatches.append((instr, offset, ares.hex(), gopher.hex()))

    expected_keys = [
        ("SDL",0),("SDL",4),("SDL",5),("SDL",6),("SDL",7),
        ("SDR",0),("SDR",1),("SDR",2),("SDR",3),("SDR",7),
    ]
    assert [(i,o) for i,o,_,_ in mismatches] == expected_keys, mismatches

    initial = bytes(range(0xa0, 0xb8))
    sd_after, _ = model.execute(initial, "SD", "big", 0, bank="imem")
    assert sd_after[:8].hex() == "11223344a4a5a6a7"

    print("PASS: exact pinned references disagree on 10/16 big-endian SDL/SDR SP images")
    print("ares_gopher_mismatches=10/16")
    print("hardware_systemtest_sdl_sdr_oracle=absent")
    print("hardware_systemtest_sd_control=upper32_only")
    print("gopher_cpu_sha256=" + sha(cpu_path))
    print("gopher_rsp_sha256=" + sha(rsp_path))
    print("systemtest_spmem_sha256=" + sha(st_path))

if __name__ == "__main__":
    main()
