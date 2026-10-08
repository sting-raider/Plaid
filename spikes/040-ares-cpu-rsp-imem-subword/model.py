#!/usr/bin/env python3
"""Independent source-derived model for pinned-ares CPU SB/SH -> RSP IMEM.

The key distinction is between the nominal CPU store width and the concrete
RSP::writeWord sink effect reached through Memory::RCP::write<Byte/Half>.
"""
from __future__ import annotations
import hashlib
import json
import random

DATA = 0x1122334455667788
XOR = {1: 7, 2: 6}


def size_of(op: str) -> int:
    return 1 if op == "SB" else 2 if op == "SH" else (_ for _ in ()).throw(ValueError(op))


def transformed_offset(op: str, endian: str, guest_offset: int) -> int:
    size = size_of(op)
    return guest_offset if endian == "big" else guest_offset ^ XOR[size]


def sink_word(op: str, endian: str, guest_offset: int, value: int = DATA):
    size = size_of(op)
    if size == 2 and guest_offset & 1:
        return None
    p = transformed_offset(op, endian, guest_offset)
    lane = p & 3
    low = value & ((1 << (8 * size)) - 1)
    if size == 1:
        shift = (3 - lane) * 8
    else:
        assert lane in (0, 2)
        shift = 16 if lane == 0 else 0
    return p & ~3, (low << shift).to_bytes(4, "big")


def apply(before: bytes, op: str, endian: str, guest_offset: int, value: int = DATA) -> bytes:
    result = sink_word(op, endian, guest_offset, value)
    if result is None:
        return before
    word_base, payload = result
    out = bytearray(before)
    out[word_base:word_base + 4] = payload
    return bytes(out)


def main() -> None:
    initial = bytes(range(0xA0, 0xB0))
    report = []
    for endian in ("big", "little"):
        for op in ("SB", "SH"):
            for off in range(8):
                after = apply(initial, op, endian, off)
                fault = op == "SH" and off & 1
                if fault:
                    assert after == initial
                    changed = []
                else:
                    word_base, payload = sink_word(op, endian, off)
                    assert after[word_base:word_base + 4] == payload
                    changed = [i for i, (a, b) in enumerate(zip(initial, after)) if a != b]
                    # Distinct nonzero sentinels and zero-filled unused lanes make
                    # all four overwritten bytes observably different.
                    assert changed == list(range(word_base, word_base + 4))
                report.append({
                    "endian": endian, "op": op, "offset": off, "fault": fault,
                    "after": list(after), "changed": changed,
                })

    rng = random.Random(0x5348494D454D)
    for _ in range(100_000):
        op = rng.choice(("SB", "SH"))
        endian = rng.choice(("big", "little"))
        off = rng.randrange(8)
        if op == "SH": off &= ~1
        before = bytes(rng.randrange(1, 256) for _ in range(16))
        value = rng.getrandbits(64)
        after = apply(before, op, endian, off, value)
        word_base, payload = sink_word(op, endian, off, value)
        assert after[word_base:word_base + 4] == payload
        assert after[:word_base] == before[:word_base]
        assert after[word_base + 4:] == before[word_base + 4:]

    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    print("PASS: 32 exhaustive lane/fault cases + 100000 randomized sink cases")
    print("model_sha256=" + hashlib.sha256(encoded).hexdigest())


if __name__ == "__main__":
    main()
