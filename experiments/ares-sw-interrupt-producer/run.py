#!/usr/bin/env python3
"""Execute exact pinned ares guest-MTC0 software-interrupt producer cases."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-sw-interrupt-producer"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
MUPEN_REV = "ba95bab92a76744753bfe61470823a4937850ab0"
PLAID_BASE = "211176e7a489fecf8331d02915ee982cd279cb62"
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
    return (0xFFFFFFFFBFC00200 if bev else 0xFFFFFFFF80000000) + 0x180


def expected_after_write(initial_ip: int, raw_value: int) -> int:
    return (initial_ip & 0xFC) | ((raw_value >> 8) & 0x03)


def c(name, *, bev=0, ie=1, exl=0, erl=0, initial_ip=0, initial_im=0,
      write_value=0, final_im=None):
    if final_im is None:
        final_im = initial_im
    return {
        "name": name, "bev": bev, "ie": ie, "exl": exl, "erl": erl,
        "initial_ip": initial_ip, "initial_im": initial_im,
        "write_value": write_value, "final_im": final_im,
    }


def cases():
    out = []
    for bev in (0, 1):
        out += [
            c(f"set_ip0_bev{bev}", bev=bev, initial_im=0x01, write_value=0x0100),
            c(f"set_ip1_bev{bev}", bev=bev, initial_im=0x02, write_value=0x0200),
            c(f"set_both_bev{bev}", bev=bev, initial_im=0x03, write_value=0x0300),
        ]
    out += [
        c("attempt_hardware_ip_only", initial_im=0xFC, write_value=0xFC00),
        c("mixed_sw0_hardware_attempt", initial_im=0x05, write_value=0xFD00),
        c("masked_ip0", initial_im=0x00, write_value=0x0100),
        c("disjoint_ip0", initial_im=0x02, write_value=0x0100),
        c("ie0_ip0", ie=0, initial_im=0x01, write_value=0x0100),
        c("exl1_ip0", exl=1, initial_im=0x01, write_value=0x0100),
        c("erl1_ip0", erl=1, initial_im=0x01, write_value=0x0100),
        c("clear_ip0_before_enable", initial_ip=0x01, initial_im=0x00, write_value=0x0000, final_im=0x01),
        c("clear_ip1_before_enable", initial_ip=0x02, initial_im=0x00, write_value=0x0000, final_im=0x02),
        c("same_value_set_ip0", initial_ip=0x01, initial_im=0x00, write_value=0x0100, final_im=0x01),
        c("same_value_clear", initial_ip=0x00, initial_im=0x00, write_value=0x0000, final_im=0x01),
        c("preserve_ip2_against_zero", initial_ip=0x04, initial_im=0x00, write_value=0x0000, final_im=0x04),
        c("preserve_ip7_against_hw_write", initial_ip=0x80, initial_im=0x00, write_value=0xFC00, final_im=0x80),
        c("replace_sw_preserve_ip2", initial_ip=0x05, initial_im=0x00, write_value=0x0200, final_im=0x06),
        c("replace_sw_preserve_ip2_take_sw1", initial_ip=0x05, initial_im=0x00, write_value=0x0200, final_im=0x02),
    ]
    return out


def should_take(case, final_ip):
    return bool(final_ip & case["final_im"]) and bool(case["ie"]) and not case["exl"] and not case["erl"]


def check(case, state):
    for key in ("name", "bev", "ie", "initial_exl", "initial_erl", "initial_ip", "initial_im", "write_value", "final_im"):
        expected_key = {"initial_exl": "exl", "initial_erl": "erl"}.get(key, key)
        assert state[key] == case[expected_key], (case, state, key)

    expected_ip = expected_after_write(case["initial_ip"], case["write_value"])
    assert state["first_pc"] == START_PC + 4, (case, state)
    assert state["first_ip"] == expected_ip, (case, state)
    assert state["first_cause"] == CAUSE_SENTINEL, (case, state)
    assert state["first_bd"] == 1, (case, state)
    assert state["first_epc"] == EPC_SENTINEL, (case, state)

    take = should_take(case, expected_ip)
    if take:
        assert state["pc"] == vector(case["bev"]), (case, state)
        assert state["s0"] == 0, (case, state)
        assert state["cause"] == 0, (case, state)
        assert state["bd"] == 0, (case, state)
        assert state["epc"] == START_PC + 4, (case, state)
        assert state["final_exl"] == 1, (case, state)
        assert state["final_erl"] == case["erl"], (case, state)
    else:
        assert state["pc"] == START_PC + 8, (case, state)
        assert state["s0"] == EXECUTED_S0, (case, state)
        assert state["cause"] == CAUSE_SENTINEL, (case, state)
        assert state["bd"] == 1, (case, state)
        assert state["epc"] == EPC_SENTINEL, (case, state)
        assert state["final_exl"] == case["exl"], (case, state)
        assert state["final_erl"] == case["erl"], (case, state)
    assert state["final_ip"] == expected_ip, (case, state)
    return take


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares; fetch exact pinned refs first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if revision != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {revision} != {ARES_REV}")

    oracle = load_oracle_helper()
    exe = oracle.build(HERE / "driver.cpp", OUTPUT)
    results = []
    for case in cases():
        args = [
            str(exe), case["name"], str(case["bev"]), str(case["ie"]),
            str(case["exl"]), str(case["erl"]), hex(case["initial_ip"]),
            hex(case["initial_im"]), hex(case["write_value"]), hex(case["final_im"]),
        ]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (case, first, second)
        state = json.loads(first)
        taken = check(case, state)
        row = {"taken": taken, **state}
        results.append(row)
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))

    payload = {
        "plaid_base": PLAID_BASE,
        "ares_revision": ARES_REV,
        "gopher64_source_revision": GOPHER_REV,
        "mupen64plus_source_revision": MUPEN_REV,
        "case_count": len(results),
        "taken_count": sum(row["taken"] for row in results),
        "suppressed_count": sum(not row["taken"] for row in results),
        "results": results,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
    print(f"RESULT_SHA256 {digest}")
    print(f"PASS: {len(results)} guest-MTC0 cases repeat byte-identically and preserve software/hardware IP ownership")
    return 0


if __name__ == "__main__":
    sys.exit(main())
