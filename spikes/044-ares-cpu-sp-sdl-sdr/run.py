#!/usr/bin/env python3
"""Build exact pinned ares and validate decoded CPU SD/SDL/SDR -> SP storage effects."""
from __future__ import annotations
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REF = ROOT / ".refs/ares"
OUTPUT = ROOT / "target/ares-cpu-sp-sdl-sdr"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
EXPECTED_SOURCE_HASHES = {
    "ipu": "495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152",
    "memory": "55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74",
    "rcp": "54089251052dbffddf7ae77819c3a3bb494cf7269ae874a3015a23907370a69c",
    "rsp_io": "60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860",
}

spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
mspec = importlib.util.spec_from_file_location("sdl_sdr_model", HERE / "model.py")
model = importlib.util.module_from_spec(mspec); sys.modules[mspec.name] = model; mspec.loader.exec_module(model)


def guard_sources() -> dict[str, str]:
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == ARES_REV
    paths = {
        "ipu": REF / "ares/n64/cpu/interpreter-ipu.cpp",
        "memory": REF / "ares/n64/cpu/memory.cpp",
        "rcp": REF / "ares/n64/memory/io.hpp",
        "rsp_io": REF / "ares/n64/rsp/io.cpp",
    }
    hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()}
    assert hashes == EXPECTED_SOURCE_HASHES, hashes
    ipu = paths["ipu"].read_text()
    assert "auto CPU::SDL(cr64& rt, cr64& rs, s16 imm) -> void" in ipu
    assert "auto CPU::SDR(cr64& rt, cr64& rs, s16 imm) -> void" in ipu
    assert "auto CPU::SD(cr64& rt, cr64& rs, s16 imm) -> void" in ipu
    memory = paths["memory"].read_text()
    assert "if(context.littleEndian()) paddr = reverseEndianPaddr<Size>(paddr);" in memory
    rcp = paths["rcp"].read_text()
    assert "if constexpr(Size == Dual)" in rcp
    assert "((T*)this)->writeWord(address, data >> 32, thread);" in rcp
    assert "writeWord(address, data << 24" in rcp and "writeWord(address, data << 16" in rcp
    rsp_io = paths["rsp_io"].read_text()
    assert "imem.write<Word>(address, data)" in rsp_io
    assert "dmem.write<Word>(address, data)" in rsp_io
    return hashes


def invoke(exe: Path, kind: str, endian: str, bank: str, offset: int) -> dict:
    args = [str(exe), kind, endian, bank, str(offset)]
    first = subprocess.check_output(args, text=True, timeout=20)
    second = subprocess.check_output(args, text=True, timeout=20)
    assert first == second, (kind, endian, bank, offset)
    return json.loads(first)


def validate_common(state: dict, initial: bytes, other_initial: bytes, expected: bytes, events: list[dict]) -> None:
    assert state["cause"] == 0 and state["exl"] == 0, state
    assert bytes(state["before"]) == initial, state
    assert bytes(state["after"]) == expected, (state, events)
    assert bytes(state["other_before"]) == other_initial, state
    assert bytes(state["other_after"]) == other_initial, state
    state["model_events"] = events
    state["changed"] = model.changed(initial, expected)


def main() -> None:
    hashes = guard_sources()
    model.main()
    exe = mod.build(HERE / "driver.cpp", OUTPUT)
    initial = bytes(range(0xa0, 0xb8))
    other_initial = bytes(range(0x50, 0x68))
    results: list[dict] = []
    dual_single_cases = two_word_single_cases = repeated_sink_cases = 0

    for bank in ("dmem", "imem"):
        for endian in ("big", "little"):
            for instr in ("SDL", "SDR"):
                for offset in range(8):
                    state = invoke(exe, instr, endian, bank, offset)
                    expected, events = model.execute(initial, instr, endian, offset, bank=bank)
                    validate_common(state, initial, other_initial, expected, events)
                    sink_words = [e["sink_word_delta"] for e in events]
                    if any(e["size"] == model.DUAL for e in events):
                        dual_single_cases += 1
                        assert len(state["changed"]) == 4, state
                    if len(set(sink_words)) == 2:
                        two_word_single_cases += 1
                        assert len(state["changed"]) == 8, state
                    if len(sink_words) != len(set(sink_words)):
                        repeated_sink_cases += 1
                    results.append(state)

    assert dual_single_cases == 8
    assert two_word_single_cases == 24
    assert repeated_sink_cases == 16

    sd_controls = 0
    for bank in ("dmem", "imem"):
        for endian in ("big", "little"):
            state = invoke(exe, "SD", endian, bank, 0)
            expected, events = model.execute(initial, "SD", endian, 0, bank=bank)
            validate_common(state, initial, other_initial, expected, events)
            assert len(state["changed"]) == 4, state
            assert len(events) == 1 and events[0]["size"] == model.DUAL
            sd_controls += 1
            results.append(state)
    assert sd_controls == 4

    pair_lengths: set[int] = set()
    pair_cases = 0
    for bank in ("dmem", "imem"):
        for endian in ("big", "little"):
            for start in range(8):
                state = invoke(exe, "PAIR", endian, bank, start)
                expected, events = model.execute_pair(initial, endian, start, bank=bank)
                validate_common(state, initial, other_initial, expected, events)
                pair_lengths.add(len(state["changed"]))
                pair_cases += 1
                results.append(state)
    assert pair_cases == 32
    assert pair_lengths == {4, 8, 12}, pair_lengths

    assert len(results) == 100
    encoded = (json.dumps(results, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()

    # Stable discriminating receipts for humans and future source guards.
    def pick(kind: str, endian: str, bank: str, offset: int) -> dict:
        return next(r for r in results if r["kind"] == kind and r["endian"] == endian and r["bank"] == bank and r["offset"] == offset)
    dual = pick("SDL", "big", "imem", 0)
    widened = pick("SDL", "big", "imem", 1)
    overwrite = pick("SDR", "big", "imem", 2)
    sd = pick("SD", "big", "imem", 0)

    print("PASS: 100 exact-pinned-ares decoded SD/SDL/SDR -> SP cases, each repeated twice")
    print(f"dual_single_four_byte_cases={dual_single_cases}/8")
    print(f"two_word_single_cases={two_word_single_cases}/24")
    print(f"repeated_same_sink_cases={repeated_sink_cases}/16")
    print("pair_changed_byte_counts=" + ",".join(map(str, sorted(pair_lengths))))
    print("aligned_sd_changed_bytes=4")
    print("counterexample_big_sdl0_imem=" + bytes(dual["after"][:8]).hex())
    print("counterexample_big_sdl1_imem=" + bytes(widened["after"][:8]).hex())
    print("counterexample_big_sdr2_imem=" + bytes(overwrite["after"][:8]).hex())
    print("counterexample_big_sd_imem=" + bytes(sd["after"][:8]).hex())
    print("repeat_deterministic=true")
    print("results_sha256=" + digest)
    for key in sorted(hashes): print(f"source_{key}_sha256={hashes[key]}")

if __name__ == "__main__":
    main()
