#!/usr/bin/env python3
"""Execute the exact pinned ares maskable-interrupt root/gating matrix."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-interrupt-roots"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
START_PC = 0xFFFFFFFFA0000000
EPC_SENTINEL = 0x123456789ABCDEF0
CAUSE_SENTINEL = 13
EXECUTED_S0 = 0x1234


def load_oracle_helper():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector(bev: int) -> int:
    base = 0xFFFFFFFFBFC00200 if bev else 0xFFFFFFFF80000000
    return base + 0x180


def case(name: str, bev: int, ie: int, exl: int, erl: int, ip: int, im: int):
    return (name, bev, ie, exl, erl, ip, im)


def cases():
    out = []
    # Every Cause.IP bit is independently eligible when its matching Status.IM bit
    # is enabled. This tests the common root without assuming a particular device.
    for bev in (0, 1):
        for bit in range(8):
            out.append(case(f"ip{bit}_matched_bev{bev}", bev, 1, 0, 0, 1 << bit, 1 << bit))

        out.extend([
            case(f"multi_matched_bev{bev}", bev, 1, 0, 0, 0xA5, 0x24),
            case(f"masked_bev{bev}", bev, 1, 0, 0, 0x04, 0x08),
            case(f"disjoint_multi_bev{bev}", bev, 1, 0, 0, 0x55, 0xAA),
            case(f"ie0_bev{bev}", bev, 0, 0, 0, 0x04, 0x04),
            case(f"exl1_bev{bev}", bev, 1, 1, 0, 0x04, 0x04),
            case(f"erl1_bev{bev}", bev, 1, 0, 1, 0x04, 0x04),
            case(f"no_pending_bev{bev}", bev, 1, 0, 0, 0x00, 0xFF),
            case(f"zero_mask_bev{bev}", bev, 1, 0, 0, 0xFF, 0x00),
        ])
    return out


def should_take(c) -> bool:
    _, _bev, ie, exl, erl, ip, im = c
    return bool(ip & im) and bool(ie) and not exl and not erl


def check(c, state):
    name, bev, ie, exl, erl, ip, im = c
    assert state["name"] == name, (c, state)
    assert (state["bev"], state["ie"], state["initial_exl"], state["initial_erl"]) == (bev, ie, exl, erl), (c, state)
    assert (state["ip"], state["im"]) == (ip, im), (c, state)

    if should_take(c):
        assert state["pc"] == vector(bev), (c, state)
        assert state["s0"] == 0, (c, state)  # interrupted instruction did not execute
        assert state["cause"] == 0, (c, state)
        assert state["bd"] == 0, (c, state)
        assert state["epc"] == START_PC, (c, state)
        assert state["final_exl"] == 1 and state["final_erl"] == 0, (c, state)
    else:
        assert state["pc"] == START_PC + 4, (c, state)
        assert state["s0"] == EXECUTED_S0, (c, state)  # ordinary instruction retired
        assert state["cause"] == CAUSE_SENTINEL, (c, state)
        assert state["bd"] == 1, (c, state)  # sentinel was not overwritten by entry
        assert state["epc"] == EPC_SENTINEL, (c, state)
        assert state["final_exl"] == exl and state["final_erl"] == erl, (c, state)

    # Requested pending bits are not themselves consumed by architectural entry.
    assert state["final_ip"] & ip == ip, (c, state)


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
    for c in cases():
        args = [str(exe), c[0], *map(str, c[1:5]), hex(c[5]), hex(c[6])]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (c, first, second)
        state = json.loads(first)
        check(c, state)
        results.append({"taken": should_take(c), **state})
        print(json.dumps(results[-1], sort_keys=True, separators=(",", ":")))

    taken = sum(1 for row in results if row["taken"])
    suppressed = len(results) - taken
    payload = {
        "plaid_base": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
        "ares_revision": ARES_REV,
        "gopher64_source_revision": GOPHER_REV,
        "case_count": len(results),
        "taken_count": taken,
        "suppressed_count": suppressed,
        "results": results,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
    print(f"RESULT_SHA256 {digest}")
    print(f"PASS: {len(results)} exact-reference cases ({taken} taken, {suppressed} suppressed) obey the mask/IE/EXL/ERL interrupt-root truth table and repeat byte-identically")
    return 0


if __name__ == "__main__":
    sys.exit(main())
