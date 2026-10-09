#!/usr/bin/env python3
"""Exhaustively falsify value-only Cause/IP ownership assumptions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "target/ares-sw-interrupt-producer/model.json"


def guest_cause_write(initial_ip: int, raw_value: int) -> int:
    """VR4300 Cause software write: replace IP0/IP1, preserve producer IP2..IP7."""
    return (initial_ip & 0xFC) | ((raw_value >> 8) & 0x03)


def eligible(ip: int, im: int, ie: int, exl: int, erl: int) -> bool:
    return bool(ip & im) and bool(ie) and not exl and not erl


def main() -> int:
    ownership_cases = 0
    same_value_cases = 0
    for initial_ip in range(256):
        # Exercise every low 16-bit Cause payload, including all attempted writes
        # to hardware-pending positions and large numbers of equal-payload decoys.
        for raw in range(1 << 16):
            final_ip = guest_cause_write(initial_ip, raw)
            assert final_ip & 0xFC == initial_ip & 0xFC
            assert final_ip & 0x03 == (raw >> 8) & 0x03
            ownership_cases += 1
            if final_ip == initial_ip:
                same_value_cases += 1

    gate_cases = 0
    taken_cases = 0
    for ip in range(256):
        for im in range(256):
            for ie in (0, 1):
                for exl in (0, 1):
                    for erl in (0, 1):
                        take = eligible(ip, im, ie, exl, erl)
                        gate_cases += 1
                        taken_cases += int(take)
                        if ie == 0 or exl or erl or not (ip & im):
                            assert not take
                        else:
                            assert take

    payload = {
        "ownership_cases": ownership_cases,
        "same_value_cases": same_value_cases,
        "gate_cases": gate_cases,
        "taken_cases": taken_cases,
        "writable_pending_mask": 0x03,
        "preserved_pending_mask": 0xFC,
        "raw_cause_writable_bits": 0x300,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(json.dumps(payload, sort_keys=True))
    print(f"MODEL_SHA256 {digest}")
    print("PASS: exhaustive Cause-write ownership and interrupt-gate model")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
