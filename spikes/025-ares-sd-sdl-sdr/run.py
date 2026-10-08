#!/usr/bin/env python3
"""Exhaust SD/SDL/SDR byte effects against the exact pinned ares CPU core."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-sd-sdl-sdr"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
MUPEN_REV = "ba95bab92a76744753bfe61470823a4937850ab0"
PAYLOAD = 0x1122334455667788
INITIAL = bytes(range(0xA0, 0xA0 + 24))
DATA_VADDR = 0xFFFFFFFFA0000100
CODE_VADDR = 0xFFFFFFFFA0000000


def load_oracle_helper():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload_bytes(little: int) -> bytes:
    return PAYLOAD.to_bytes(8, "little" if little else "big")


def expected_direct(kind: str, offset: int, little: int) -> tuple[bytes, int, int, int]:
    out = bytearray(INITIAL)
    payload = payload_bytes(little)
    if kind == "sdl":
        out[offset:8] = payload[: 8 - offset]
        return bytes(out), 0, 0, CODE_VADDR + 4
    if kind == "sdr":
        out[: offset + 1] = payload[7 - offset :]
        return bytes(out), 0, 0, CODE_VADDR + 4
    if kind == "pair":
        out[offset : offset + 8] = payload
        return bytes(out), 0, 0, CODE_VADDR + 8
    if kind == "sd" and offset == 0:
        out[:8] = payload
        return bytes(out), 0, 0, CODE_VADDR + 4
    if kind == "sd":
        return bytes(out), 5, DATA_VADDR + offset, 0xFFFFFFFF80000180
    raise AssertionError(kind)


def physical_from_guest(guest: bytes, little: int) -> bytes:
    out = bytearray(len(guest))
    for i, value in enumerate(guest):
        out[i ^ (7 if little else 0)] = value
    return bytes(out)


def changed(before: bytes, after: bytes) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(before, after)) if a != b]


def expected_changed(kind: str, offset: int, address_kind: str) -> list[int]:
    if address_kind == "tlb":
        return []
    if kind == "sdl":
        return list(range(offset, 8))
    if kind == "sdr":
        return list(range(0, offset + 1))
    if kind == "pair":
        return list(range(offset, offset + 8))
    if kind == "sd" and offset == 0:
        return list(range(8))
    return []


def cases():
    out = []
    for little in (0, 1):
        for kind in ("sdl", "sdr", "sd", "pair"):
            for offset in range(8):
                out.append((kind, offset, little, "direct"))
        for kind in ("sdl", "sdr"):
            for offset in range(8):
                out.append((kind, offset, little, "tlb"))
        out.append(("sd", 0, little, "tlb"))
    return out


def check(case, state):
    kind, offset, little, address_kind = case
    before = bytes(state["before"])
    after = bytes(state["after"])
    physical_before = bytes(state["physical_before"])
    physical_after = bytes(state["physical_after"])
    assert before == INITIAL, (case, before.hex())
    assert physical_before == physical_from_guest(INITIAL, little), (case, physical_before.hex())
    assert physical_after == physical_from_guest(after, little), (case, physical_after.hex(), after.hex())
    assert state["kind"] == kind and state["offset"] == offset and state["little"] == little
    assert state["address_kind"] == address_kind
    assert changed(before, after) == expected_changed(kind, offset, address_kind), (case, changed(before, after), after.hex())

    if address_kind == "tlb":
        assert after == INITIAL, (case, after.hex())
        assert state["cause"] == 3 and state["exl"] == 1, (case, state)
        assert state["epc"] == CODE_VADDR and state["pc"] == 0xFFFFFFFF80000080, (case, state)
        return

    expected, cause, badva, pc = expected_direct(kind, offset, little)
    assert after == expected, (case, after.hex(), expected.hex())
    assert state["cause"] == cause and state["pc"] == pc, (case, state)
    if cause:
        assert state["exl"] == 1 and state["epc"] == CODE_VADDR and state["badva"] == badva, (case, state)
    else:
        assert state["exl"] == 0, (case, state)


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares; fetch the pinned refs first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if revision != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {revision} != {ARES_REV}")

    oracle = load_oracle_helper()
    exe = oracle.build(HERE / "driver.cpp", OUTPUT)
    results = []
    for case in cases():
        args = [str(exe), *map(str, case)]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (case, first, second)
        state = json.loads(first)
        check(case, state)
        results.append(state)

    result = {
        "ares_revision": ARES_REV,
        "mupen_source_revision": MUPEN_REV,
        "payload": f"0x{PAYLOAD:016x}",
        "case_count": len(results),
        "results": results,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(result, indent=2) + "\n").encode()
    result_path = OUTPUT / "results.json"
    result_path.write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    print(f"PASS: {len(results)} SD/SDL/SDR cases match byte-precise expectations and repeat byte-identically")
    print(f"results_sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
