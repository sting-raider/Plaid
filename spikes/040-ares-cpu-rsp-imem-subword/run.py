#!/usr/bin/env python3
"""Build exact pinned ares and check CPU SB/SH -> RSP IMEM sink effects."""
from __future__ import annotations
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REF = ROOT / ".refs/ares"
OUTPUT = ROOT / "target/ares-cpu-rsp-imem-subword"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mspec = importlib.util.spec_from_file_location("subword_model", HERE / "model.py")
model = importlib.util.module_from_spec(mspec)
mspec.loader.exec_module(model)


def guard_sources() -> dict[str, str]:
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == ARES_REV
    paths = {
        "ipu": REF / "ares/n64/cpu/interpreter-ipu.cpp",
        "memory": REF / "ares/n64/cpu/memory.cpp",
        "rcp": REF / "ares/n64/memory/io.hpp",
        "rsp_io": REF / "ares/n64/rsp/io.cpp",
        "writable": REF / "ares/n64/memory/msb/writable.hpp",
    }
    text = {k: p.read_text() for k, p in paths.items()}
    assert "auto CPU::SB(cr64& rt, cr64& rs, s16 imm) -> void {\n  write<Byte>(rs.u64 + imm, rt.u32);\n}" in text["ipu"]
    assert "auto CPU::SH(cr64& rt, cr64& rs, s16 imm) -> void {\n  write<Half>(rs.u64 + imm, rt.u32);\n}" in text["ipu"]
    assert "if constexpr(Size == Byte) return paddr ^ 7;" in text["memory"]
    assert "if constexpr(Size == Half) return paddr ^ 6;" in text["memory"]
    assert "if(context.littleEndian()) paddr = reverseEndianPaddr<Size>(paddr);" in text["memory"]
    assert "case 0: return ((T*)this)->writeWord(address, data << 24, thread);" in text["rcp"]
    assert "case 3: return ((T*)this)->writeWord(address, data <<  0, thread);" in text["rcp"]
    assert "case 0: return ((T*)this)->writeWord(address, data << 16, thread);" in text["rcp"]
    assert "if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);" in text["rsp_io"]
    assert "if constexpr(Size == Word) *(u32*)&data[address & maskWord] = bswap32(value);" in text["writable"]
    return {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()}


def invoke(exe: Path, op: str, endian: str, offset: int) -> dict:
    args = [str(exe), op, endian, str(offset)]
    first = subprocess.check_output(args, text=True, timeout=20)
    second = subprocess.check_output(args, text=True, timeout=20)
    assert first == second, (op, endian, offset)
    return json.loads(first)


def main() -> None:
    hashes = guard_sources()
    exe = mod.build(HERE / "driver.cpp", OUTPUT)
    initial = bytes(range(0xA0, 0xB0))
    results = []
    widened = 0

    for endian in ("big", "little"):
        for op in ("SB", "SH"):
            for offset in range(8):
                state = invoke(exe, op, endian, offset)
                results.append(state)
                assert bytes(state["before"]) == initial
                fault = op == "SH" and offset & 1
                if fault:
                    assert state["exception"] == 5, state
                    assert state["badva"] == 0xFFFFFFFFA4001000 + offset, state
                    assert state["after"] == state["before"], state
                    assert not state["sysad_frozen"], state
                    continue

                assert state["exception"] == 0, state
                assert not state["sysad_frozen"], state
                expected = model.apply(initial, op, endian, offset)
                assert bytes(state["after"]) == expected, state
                changed = [i for i, (a, b) in enumerate(zip(state["before"], state["after"])) if a != b]
                word_base, _ = model.sink_word(op, endian, offset)
                assert changed == list(range(word_base, word_base + 4)), state
                if len(changed) > model.size_of(op): widened += 1

    # Every successful nominal subword store replaces four observable IMEM bytes.
    assert widened == 24, widened  # 16 SB + 8 aligned SH

    encoded = (json.dumps(results, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    print("PASS: 32 repeated exact-pinned-ares SB/SH -> RSP IMEM cases")
    print("successful_widened_cases=24/24")
    print("results_sha256=" + digest)
    for key in sorted(hashes):
        print(f"source_{key}_sha256={hashes[key]}")


if __name__ == "__main__":
    import os
    if os.name == 'nt':
        script = subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script],check=True)
    else:
        main()
