#!/usr/bin/env python3
"""Build exact pinned ares and validate CPU SWL/SWR -> RSP IMEM effects."""
from __future__ import annotations
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REF = ROOT / ".refs/ares"
OUTPUT = ROOT / "target/ares-cpu-sp-partial-word"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
EXPECTED_SOURCE_HASHES = {
    "ipu": "495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152",
    "memory": "55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74",
    "rcp": "54089251052dbffddf7ae77819c3a3bb494cf7269ae874a3015a23907370a69c",
    "rsp_io": "60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860",
    "writable": "29d6d71b9b92e095f34bd1809c5d3f8afb74cb16857e1f597854165d70d9df06",
}

spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mspec = importlib.util.spec_from_file_location("partial_model", HERE / "model.py")
model = importlib.util.module_from_spec(mspec); mspec.loader.exec_module(model)


def guard_sources() -> dict[str, str]:
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == ARES_REV
    paths = {
        "ipu": REF / "ares/n64/cpu/interpreter-ipu.cpp",
        "memory": REF / "ares/n64/cpu/memory.cpp",
        "rcp": REF / "ares/n64/memory/io.hpp",
        "rsp_io": REF / "ares/n64/rsp/io.cpp",
        "writable": REF / "ares/n64/memory/msb/writable.hpp",
    }
    hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()}
    assert hashes == EXPECTED_SOURCE_HASHES, hashes
    ipu = paths["ipu"].read_text()
    assert "auto CPU::SWL(cr64& rt, cr64& rs, s16 imm) -> void" in ipu
    assert "auto CPU::SWR(cr64& rt, cr64& rs, s16 imm) -> void" in ipu
    rcp = paths["rcp"].read_text()
    assert "writeWord(address, data << 24" in rcp
    assert "writeWord(address, data << 16" in rcp
    assert "writeWord(address, data <<  0" in rcp
    rspio = paths["rsp_io"].read_text()
    assert "imem.write<Word>(address, data)" in rspio
    return hashes


def invoke(exe: Path, op: str, endian: str, offset: int) -> dict:
    args = [str(exe), op, endian, str(offset)]
    first = subprocess.check_output(args, text=True, timeout=20)
    second = subprocess.check_output(args, text=True, timeout=20)
    assert first == second, (op, endian, offset)
    return json.loads(first)


def main() -> None:
    hashes = guard_sources()
    exe = mod.build(HERE / "driver.cpp", OUTPUT)
    initial = bytes(range(0xa0, 0xb0))
    results: list[dict] = []
    widened = 0
    two_subwrite = 0

    for endian in ("big", "little"):
        for op in ("SWL", "SWR"):
            for offset in range(8):
                state = invoke(exe, op, endian, offset)
                assert bytes(state["before"]) == initial
                assert state["exception"] == 0, state
                assert not state["sysad_frozen"], state
                expected, events = model.execute(initial, op, endian, offset)
                assert bytes(state["after"]) == expected, (state, events)
                changed = [i for i,(a,b) in enumerate(zip(state["before"], state["after"])) if a != b]
                assert len(changed) == 4, (state, events, changed)
                assert changed == list(range(events[-1]["sink_word_delta"], events[-1]["sink_word_delta"] + 4)), (state, events, changed)
                if len(events) == 2:
                    two_subwrite += 1
                    assert events[0]["sink_word_delta"] == events[1]["sink_word_delta"]
                    assert events[0]["sink_value"] != events[1]["sink_value"]
                widened += 1
                state["model_events"] = events
                results.append(state)

    assert widened == 32
    assert two_subwrite == 8

    pair_bad_for_normal_partial_semantics = 0
    for endian in ("big", "little"):
        for offset in range(4):
            state = invoke(exe, "PAIR", endian, offset)
            assert bytes(state["before"]) == initial
            assert state["exception"] == 0, state
            expected, events = model.execute_pair(initial, endian, offset)
            assert bytes(state["after"]) == expected, (state, events)
            # A conventional SWL/SWR pair to normal memory preserves bytes outside
            # the intended four-byte guest span. The SP widening path demonstrably
            # replaces complete word sinks; use changed-lane extent as the direct counterexample.
            changed = [i for i,(a,b) in enumerate(zip(state["before"], state["after"])) if a != b]
            if len(changed) > 4:
                pair_bad_for_normal_partial_semantics += 1
            state["model_events"] = events
            state["changed"] = changed
            results.append(state)

    # At least one exact pair must expose collateral full-word replacement;
    # the complete matrix is retained rather than baking in a stronger claim pre-run.
    assert pair_bad_for_normal_partial_semantics > 0, pair_bad_for_normal_partial_semantics

    encoded = (json.dumps(results, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    print("PASS: 40 repeated exact-pinned-ares SWL/SWR/SP-IMEM cases")
    print("single_full_word_sink_cases=32/32")
    print("two_subwrite_same_word_cases=8/8")
    print(f"pair_collateral_cases={pair_bad_for_normal_partial_semantics}/8")
    print("results_sha256=" + digest)
    for state in results:
        print("CASE " + json.dumps({k:state[k] for k in ("op","endian","offset","after") if k in state}, separators=(",",":")))
    for key in sorted(hashes): print(f"source_{key}_sha256={hashes[key]}")

if __name__ == "__main__":
    import os
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script], check=True)
    else:
        main()
