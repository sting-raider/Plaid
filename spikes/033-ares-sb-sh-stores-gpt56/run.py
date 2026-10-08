#!/usr/bin/env python3
"""Build exact pinned ares and check VR4300 SB/SH executable mutation semantics."""
from __future__ import annotations
from pathlib import Path
import hashlib, importlib.util, json, subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / "target/ares-sb-sh-store-gpt56-spike"

spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

mspec = importlib.util.spec_from_file_location("sb_sh_model", HERE / "model.py")
model = importlib.util.module_from_spec(mspec)
mspec.loader.exec_module(model)

def invoke(exe, mode, op, endian, offset):
    args = [str(exe), mode, op, endian, str(offset)]
    raw = subprocess.check_output(args, text=True, timeout=20)
    again = subprocess.check_output(args, text=True, timeout=20)
    assert raw == again, (mode, op, endian, offset)
    return json.loads(raw)

def expected_raw(before, op, endian, offset):
    data = bytearray(before)
    s = model.sink(op, endian, offset)
    if s is None:
        return list(data)
    pos, width = s
    data[pos:pos+width] = model.payload(op)
    return list(data)

def main():
    exe = mod.build(HERE / "driver.cpp", OUTPUT)
    results = []

    for endian in ("big", "little"):
        for op in ("SB", "SH"):
            for offset in range(8):
                for mode in ("uncached", "cached", "tlbmiss"):
                    state = invoke(exe, mode, op, endian, offset)
                    results.append(state)
                    assert bool(state["context_little"]) == (endian == "little"), state
                    before = state["before_raw"]
                    assert before == list(model.BEFORE) + list(range(0x20, 0x28)), state

                    aligned = op == "SB" or offset % 2 == 0
                    if mode == "tlbmiss":
                        assert state["after_raw"] == before, state
                        assert state["dirty"] == 0, state
                        assert state["exception"] == (3 if aligned else 5), state
                        continue

                    if not aligned:
                        assert state["exception"] == 5, state
                        assert state["badva"] == (0xffffffff80002000 + offset if mode == "cached"
                                                   else 0xffffffffa0002000 + offset), state
                        assert state["after_raw"] == before, state
                        assert state["dirty"] == 0, state
                        continue

                    assert state["exception"] == 0, state
                    expected_value = model.SB_VALUE if op == "SB" else model.SH_VALUE
                    assert state["readback"] == expected_value, state
                    if mode == "uncached":
                        assert state["after_raw"] == expected_raw(before, op, endian, offset), state
                        assert state["dirty"] == 0, state
                        assert state["alias_after"] == expected_value, state
                    else:
                        assert state["after_raw"] == before, state
                        assert state["alias_after"] == state["alias_before"], state
                        assert state["dirty"] == model.dirty_mask(op, endian, offset), state

        for op in ("SB", "SH"):
            state = invoke(exe, "construct", op, endian, 0)
            results.append(state)
            assert state["exception"] == 0, state
            assert state["dirty"] == 0, state
            assert state["constructed"] == 0x11223344, state
            expected = bytearray(state["before_raw"])
            raw_start = 8 ^ (4 if endian == "little" else 0)
            expected[raw_start:raw_start+4] = bytes.fromhex("11223344")
            assert state["after_raw"] == list(expected), state

    encoded = (json.dumps(results, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    print(f"PASS: {len(results)} repeated pinned-ares SB/SH cases")
    print(f"results_sha256={digest}")

if __name__ == "__main__":
    import os
    if os.name == 'nt':
        script = subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script],check=True)
    else:
        main()
