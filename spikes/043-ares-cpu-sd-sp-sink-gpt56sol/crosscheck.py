#!/usr/bin/env python3
"""Guard the exact pinned ares/Gopher integer-SD SP sink topology."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"


def head(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError("unterminated function")


def main() -> None:
    assert head(ARES) == ARES_REV
    assert head(GOPHER) == GOPHER_REV
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ARES, check=True)
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=GOPHER, check=True)

    ares_ipu = (ARES / "ares/n64/cpu/interpreter-ipu.cpp").read_text()
    ares_sd = function_body(ares_ipu, "auto CPU::SD(cr64& rt, cr64& rs, s16 imm) -> void")
    assert ares_sd.count("write<Dual>(rs.u64 + imm, rt.u64);") == 1
    assert "reservedInstruction" in ares_sd

    ares_io = (ARES / "ares/n64/memory/io.hpp").read_text()
    dual_marker = """if constexpr(Size == Dual) {\n      ((T*)this)->writeWord(address, data >> 32, thread);\n    }"""
    assert ares_io.count(dual_marker) == 1
    assert "writeWord(address + 4" not in dual_marker

    ares_rsp = (ARES / "ares/n64/rsp/io.cpp").read_text()
    assert "imem.write<Word>(address, data)" in ares_rsp
    assert "dmem.write<Word>(address, data)" in ares_rsp

    gopher_cpu = (GOPHER / "src/device/cpu_instructions.rs").read_text()
    gopher_sd = function_body(gopher_cpu, "pub fn sd(device: &mut device::Device, opcode: u32)")
    gopher_writes = gopher_sd.count("device::memory::data_write")
    gopher_second = "phys_address + 4" in gopher_sd
    # This exact pin models the architectural doubleword as two Word writes.
    assert gopher_writes == 2, gopher_sd
    assert gopher_second, gopher_sd

    gopher_memory = (GOPHER / "src/device/memory.rs").read_text()
    assert "rsp_interface::write_mem" in gopher_memory
    gopher_rsp = (GOPHER / "src/device/rsp_interface.rs").read_text()
    assert "pub fn write_mem" in gopher_rsp

    result = {
        "ares_revision": ARES_REV,
        "ares_sd_dual_calls": ares_sd.count("write<Dual>"),
        "ares_rcp_dual_writeword_calls": dual_marker.count("writeWord("),
        "ares_rcp_dual_second_word": "address + 4" in dual_marker,
        "gopher_revision": GOPHER_REV,
        "gopher_sd_data_write_calls": gopher_writes,
        "gopher_sd_second_address": gopher_second,
        "gopher_sp_map_to_rsp_write_mem": "rsp_interface::write_mem" in gopher_memory,
    }
    encoded = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    print(encoded.decode().strip())
    print("crosscheck_sha256=" + digest)
    print("PASS: exact-pin integer SD sink-width disagreement is structurally guarded")


if __name__ == "__main__":
    main()
