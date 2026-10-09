#!/usr/bin/env python3
"""Build exact pinned ares and execute guest-programmed WatchLo cases."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-watch-exception-roots"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
START_PC = 0xFFFFFFFFA0000000
ACCESS_PC = START_PC + 0x14
NORMAL_END_PC = START_PC + 0x18
EPC_SENTINEL = 0x123456789ABCDEF0
CAUSE_SENTINEL = 13
INITIAL_DATA = 0x11223344
STORE_DATA = 0x55667788


def load_oracle_helper():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector(bev: int) -> int:
    return (0xFFFFFFFFBFC00200 if bev else 0xFFFFFFFF80000000) + 0x180


def case(name: str, kind: str, bev: int, exl: int, watchlo: int, offset: int, hardware: str):
    return (name, kind, bev, exl, watchlo, offset, hardware)


def cases():
    return [
        case("load_match_bev0", "load", 0, 0, 0x1002, 0, "watch"),
        case("load_match_bev1", "load", 1, 0, 0x1002, 0, "watch"),
        case("load_match_lane4", "load", 0, 0, 0x1002, 4, "watch"),
        case("load_nonmatch_next_block", "load", 0, 0, 0x1002, 8, "normal"),
        case("load_write_only", "load", 0, 0, 0x1001, 0, "normal"),
        case("load_disabled", "load", 0, 0, 0x1000, 0, "normal"),
        case("store_match_bev0", "store", 0, 0, 0x1001, 0, "watch"),
        case("store_match_bev1", "store", 1, 0, 0x1001, 0, "watch"),
        case("store_match_lane4", "store", 0, 0, 0x1001, 4, "watch"),
        case("store_nonmatch_next_block", "store", 0, 0, 0x1001, 8, "normal"),
        case("store_read_only", "store", 0, 0, 0x1002, 0, "normal"),
        case("store_disabled", "store", 0, 0, 0x1000, 0, "normal"),
        case("load_match_exl1", "load", 0, 1, 0x1002, 0, "postponed"),
        case("store_match_exl1", "store", 0, 1, 0x1001, 0, "postponed"),
    ]


def check_register_write(c, state):
    name, kind, bev, exl, watchlo, offset, hardware = c
    assert state["name"] == name and state["kind"] == kind
    assert state["bev"] == bev and state["initial_exl"] == exl
    assert state["watchlo_requested"] == watchlo and state["offset"] == offset
    assert state["watch_write"] == (watchlo & 1), (c, state)
    assert state["watch_read"] == ((watchlo >> 1) & 1), (c, state)
    assert state["watch_base"] == (watchlo & 0xFFFFFFF8), (c, state)


def classify_ares(state) -> str:
    if state["cause"] == 23:
        return "watch"
    return "normal"


def check_current_ares_behavior(c, state):
    # Exact-pin source audit predicts no Watch trigger implementation. These
    # assertions make that claim executable and falsifiable.
    name, kind, bev, exl, watchlo, offset, hardware = c
    assert classify_ares(state) == "normal", (c, state)
    assert state["pc"] == NORMAL_END_PC, (c, state)
    assert state["cause"] == CAUSE_SENTINEL, (c, state)
    assert state["bd"] == 1, (c, state)
    assert state["epc"] == EPC_SENTINEL, (c, state)
    assert state["final_exl"] == exl, (c, state)
    if kind == "load":
        assert state["s1"] == INITIAL_DATA, (c, state)
        assert state["final_data"] == INITIAL_DATA, (c, state)
    else:
        assert state["final_data"] == STORE_DATA, (c, state)


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares; fetch exact refs first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if revision != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {revision} != {ARES_REV}")

    oracle = load_oracle_helper()
    exe = oracle.build(HERE / "driver.cpp", OUTPUT)
    results = []
    for c in cases():
        name, kind, bev, exl, watchlo, offset, hardware = c
        args = [str(exe), name, kind, str(bev), str(exl), hex(watchlo), hex(offset)]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (c, first, second)
        state = json.loads(first)
        check_register_write(c, state)
        check_current_ares_behavior(c, state)
        ares = classify_ares(state)
        row = {
            "hardware_manual_expected": hardware,
            "ares_observed": ares,
            "hardware_vector_if_immediate_watch": vector(bev),
            "hardware_epc_if_immediate_watch": ACCESS_PC,
            **state,
        }
        results.append(row)
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))

    watch_expected = [r for r in results if r["hardware_manual_expected"] == "watch"]
    disagreements = [r for r in watch_expected if r["ares_observed"] != "watch"]
    postponed = [r for r in results if r["hardware_manual_expected"] == "postponed"]
    assert watch_expected and len(disagreements) == len(watch_expected)
    assert all(r["ares_observed"] == "normal" for r in postponed)

    payload = {
        "plaid_base": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
        "ares_revision": ARES_REV,
        "vr4300_manual": "U10504EJ7V0UM00 7th ed. section 6.4.17",
        "case_count": len(results),
        "hardware_immediate_watch_cases": len(watch_expected),
        "ares_watch_cases": sum(r["ares_observed"] == "watch" for r in results),
        "hardware_ares_immediate_watch_disagreements": len(disagreements),
        "hardware_postponed_cases": len(postponed),
        "results": results,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
    print(f"RESULT_SHA256 {digest}")
    print(
        "PASS: guest MTC0 programmed WatchLo in all cases; exact pinned ares "
        f"took 0/{len(watch_expected)} manual-expected immediate Watch exceptions "
        f"while {len(results) - len(watch_expected) - len(postponed)} normal controls retired; "
        "the hardware/reference disagreement is preserved"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
