#!/usr/bin/env python3
"""Independent lane model for VR4300 SB/SH executable-byte effects.

This models architectural guest-byte effects and the pinned-ares reverse-endian
physical-address transform.  It intentionally does not import emulator code.
"""
from __future__ import annotations
import hashlib, json, random

DATA = 0x11223344


def guest_bytes(op: str, endian: str) -> bytes:
    if op == "SB":
        return bytes([DATA & 0xff])
    if op == "SH":
        return (DATA & 0xffff).to_bytes(2, endian)
    raise ValueError(op)


def backing_start(op: str, endian: str, guest_offset: int) -> int:
    if endian == "big":
        return guest_offset
    if op == "SB":
        return guest_offset ^ 7
    if op == "SH":
        return guest_offset ^ 6
    raise ValueError(op)


def apply_guest(before: bytes, op: str, endian: str, offset: int) -> bytes:
    out = bytearray(before)
    payload = guest_bytes(op, endian)
    out[offset:offset + len(payload)] = payload
    return bytes(out)


def self_test() -> dict:
    rng = random.Random(0x53425348)
    cases = 0
    for _ in range(100_000):
        op = rng.choice(("SB", "SH"))
        endian = rng.choice(("big", "little"))
        offset = rng.randrange(0, 16 if op == "SB" else 15)
        if op == "SH":
            offset &= ~1
        before = bytes(rng.randrange(256) for _ in range(24))
        after = apply_guest(before, op, endian, offset)
        payload = guest_bytes(op, endian)
        assert after[offset:offset + len(payload)] == payload
        assert after[:offset] == before[:offset]
        assert after[offset + len(payload):] == before[offset + len(payload):]
        p = backing_start(op, endian, offset)
        if endian == "big": assert p == offset
        elif op == "SB": assert p == (offset ^ 7)
        else: assert p == (offset ^ 6)
        cases += 1
    report = {
        "cases": cases,
        "data": f"0x{DATA:08x}",
        "sb": list(guest_bytes("SB", "big")),
        "sh_big": list(guest_bytes("SH", "big")),
        "sh_little": list(guest_bytes("SH", "little")),
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["sha256"] = hashlib.sha256(encoded).hexdigest()
    return report


if __name__ == "__main__":
    print(json.dumps(self_test(), sort_keys=True))
