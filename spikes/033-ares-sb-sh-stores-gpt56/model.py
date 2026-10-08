#!/usr/bin/env python3
"""Independent byte-effect model for VR4300 SB/SH executable mutations."""
from __future__ import annotations
import hashlib, json

SB_VALUE = 0x81
SH_VALUE = 0x92A3
BEFORE = bytes(range(0x10, 0x20))

def sink(op: str, endian: str, offset: int):
    if op == "SB":
        width = 1
        if not 0 <= offset < 8:
            raise ValueError(offset)
    elif op == "SH":
        width = 2
        if not 0 <= offset < 8:
            raise ValueError(offset)
        if offset & 1:
            return None
    else:
        raise ValueError(op)
    physical = offset
    if endian == "little":
        physical ^= 7 if width == 1 else 6
    elif endian != "big":
        raise ValueError(endian)
    return physical, width

def payload(op: str) -> bytes:
    if op == "SB":
        return bytes([SB_VALUE])
    if op == "SH":
        return SH_VALUE.to_bytes(2, "big")
    raise ValueError(op)

def apply(before: bytes, op: str, endian: str, offset: int) -> bytes:
    s = sink(op, endian, offset)
    if s is None:
        return before
    paddr, width = s
    out = bytearray(before)
    out[paddr:paddr+width] = payload(op)
    return bytes(out)

def dirty_mask(op: str, endian: str, offset: int) -> int:
    s = sink(op, endian, offset)
    if s is None:
        return 0
    paddr, width = s
    return ((1 << width) - 1) << paddr

def construct_word_with_sb(endian: str, word: int) -> bytes:
    out = bytearray(BEFORE)
    target = 8
    raw_start = target ^ (4 if endian == "little" else 0)
    desired = word.to_bytes(4, "big")
    for raw_off, value in enumerate(desired):
        raw = raw_start + raw_off
        guest = raw ^ (7 if endian == "little" else 0)
        out[guest ^ (7 if endian == "little" else 0)] = value
    return bytes(out)

def construct_word_with_sh(endian: str, word: int) -> bytes:
    out = bytearray(BEFORE)
    target = 8
    raw_start = target ^ (4 if endian == "little" else 0)
    desired = word.to_bytes(4, "big")
    for raw_off in (0, 2):
        raw = raw_start + raw_off
        guest = raw ^ (6 if endian == "little" else 0)
        p = guest ^ (6 if endian == "little" else 0)
        out[p:p+2] = desired[raw_off:raw_off+2]
    return bytes(out)

def main():
    rows = []
    for endian in ("big", "little"):
        for op in ("SB", "SH"):
            for offset in range(8):
                s = sink(op, endian, offset)
                after = apply(BEFORE, op, endian, offset)
                changed = [i for i, (a,b) in enumerate(zip(BEFORE, after)) if a != b]
                expected = [] if s is None else list(range(s[0], s[0] + s[1]))
                assert changed == expected, (endian, op, offset, changed, expected)
                if s is not None:
                    assert dirty_mask(op, endian, offset) == sum(1 << i for i in expected)
                rows.append({
                    "endian": endian, "op": op, "offset": offset,
                    "sink": s, "changed": changed, "dirty": dirty_mask(op,endian,offset)
                })
    target = 0x11223344
    for endian in ("big","little"):
        sb = construct_word_with_sb(endian,target)
        sh = construct_word_with_sh(endian,target)
        raw_start = 8 ^ (4 if endian=="little" else 0)
        assert sb[raw_start:raw_start+4] == target.to_bytes(4,"big")
        assert sh[raw_start:raw_start+4] == target.to_bytes(4,"big")
    encoded = (json.dumps(rows, sort_keys=True, separators=(",",":"))+"\n").encode()
    digest=hashlib.sha256(encoded).hexdigest()
    print(f"PASS: {len(rows)} SB/SH lane cases + two construction families")
    print(f"model_sha256={digest}")

if __name__ == "__main__":
    main()
