#!/usr/bin/env python3
"""Build exact pinned ares and verify SB/SH executable-byte mutation semantics."""
from __future__ import annotations
from pathlib import Path
import hashlib, importlib.util, json, subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / "target/ares-sb-sh-store-spike"

spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mspec = importlib.util.spec_from_file_location("sb_sh_model", HERE / "model.py")
model = importlib.util.module_from_spec(mspec); mspec.loader.exec_module(model)


def invoke(exe: Path, mode: str, op: str, endian: str, offset: int) -> dict:
    argv = [str(exe), mode, op, endian, str(offset)]
    raw = subprocess.check_output(argv, text=True, timeout=20)
    again = subprocess.check_output(argv, text=True, timeout=20)
    assert raw == again, (mode, op, endian, offset)
    return json.loads(raw)


def expected_guest(before: list[int], op: str, endian: str, offset: int) -> list[int]:
    return list(model.apply_guest(bytes(before), op, endian, offset))


def changed(before: list[int], after: list[int]) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(before, after)) if a != b]


def main() -> None:
    exe = mod.build(HERE / "driver.cpp", OUTPUT)
    results: list[dict] = []
    successful = 0
    faulted = 0

    for endian in ("big", "little"):
        for op in ("SB", "SH"):
            for offset in range(8):
                aligned = op == "SB" or offset % 2 == 0
                for mode in ("uncached", "cached", "tlbmiss"):
                    state = invoke(exe, mode, op, endian, offset)
                    results.append(state)
                    assert bool(state["context_little"]) == (endian == "little"), state

                    if mode == "tlbmiss":
                        expected_exception = 5 if op == "SH" and not aligned else 3
                        assert state["exception"] == expected_exception, state
                        assert state["badva"] == 0x2000 + offset, state
                        assert state["after_raw"] == state["before_raw"], state
                        assert state["dirty"] == 0, state
                        faulted += 1
                        continue

                    before = state["before_guest"]
                    if not aligned:
                        assert state["exception"] == 5, state
                        assert state["badva"] == (0xffffffff80002000 if mode == "cached" else 0xffffffffa0002000) + offset, state
                        assert state["after_raw"] == state["before_raw"], state
                        assert state["dirty"] == 0, state
                        faulted += 1
                        continue

                    assert state["exception"] == 0, state
                    expected = expected_guest(before, op, endian, offset)
                    assert state["after_guest"] == expected, state
                    physical = model.backing_start(op, endian, offset)
                    width = 1 if op == "SB" else 2
                    expected_dirty = ((1 << width) - 1) << physical

                    if mode == "uncached":
                        assert state["alias_after"] == expected, state
                        assert state["dirty"] == 0, state
                        assert changed(state["before_raw"], state["after_raw"]) == list(range(physical, physical + width)), state
                        if op == "SB":
                            assert state["after_raw"][physical] == (model.DATA & 0xff), state
                        else:
                            assert state["after_raw"][physical:physical + 2] == [0x33, 0x44], state
                    else:
                        assert state["alias_after"] == before, state
                        assert state["after_raw"] == state["before_raw"], state
                        assert state["dirty"] == expected_dirty, (state, expected_dirty)
                    successful += 1

    # Explicitly prove every logical instruction-byte lane is writable by SB,
    # and both aligned halfwords of a 32-bit instruction word are writable by SH.
    for endian in ("big", "little"):
        sb_lanes = {model.backing_start("SB", endian, off) & 3 for off in range(4)}
        assert sb_lanes == {0, 1, 2, 3}, (endian, sb_lanes)
        sh_pairs = [{model.backing_start("SH", endian, off) & 3,
                     (model.backing_start("SH", endian, off) + 1) & 3} for off in (0, 2)]
        assert set().union(*sh_pairs) == {0, 1, 2, 3}, (endian, sh_pairs)

    encoded = (json.dumps(results, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    print(f"PASS: {len(results)} repeated pinned-ares SB/SH cases ({successful} successes, {faulted} faults)")
    print(f"results_sha256={digest}")


if __name__ == "__main__":
    import os
    if os.name == 'nt':
        script = subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script],check=True)
    else:
        main()
