#!/usr/bin/env python3
"""Source-derived model for pinned-ares CPU SCD -> RCP SP-memory sinks."""
from __future__ import annotations
import hashlib
import json

INITIAL_HI = 0x11223344
INITIAL_LO = 0xFFFFFFF0
INITIAL64 = (INITIAL_HI << 32) | INITIAL_LO
DELTA = 0x20
CHANGED64 = (INITIAL64 + DELTA) & 0xFFFFFFFFFFFFFFFF


def rcp_dual_write(value: int) -> list[dict[str, int]]:
    """Exact pinned-ares Memory::RCP::write<Dual> normalization."""
    return [{"offset": 0, "value": (value >> 32) & 0xFFFFFFFF}]


def apply_sp(initial_hi: int, initial_lo: int, value: int) -> tuple[int, int]:
    effects = rcp_dual_write(value)
    hi, lo = initial_hi, initial_lo
    for effect in effects:
        if effect["offset"] == 0:
            hi = effect["value"]
        elif effect["offset"] == 4:
            lo = effect["value"]
        else:
            raise AssertionError(effect)
    return hi, lo


def report() -> dict:
    changed_hi, changed_lo = apply_sp(INITIAL_HI, INITIAL_LO, CHANGED64)
    same_hi, same_lo = apply_sp(INITIAL_HI, INITIAL_LO, INITIAL64)
    return {
        "initial64": INITIAL64,
        "changed_source64": CHANGED64,
        "changed_sink_words": [changed_hi, changed_lo],
        "same_sink_words": [same_hi, same_lo],
        "dual_effect_count": len(rcp_dual_write(CHANGED64)),
        "full_64bit_store_materialized": ((changed_hi << 32) | changed_lo) == CHANGED64,
    }


def self_test() -> dict:
    doc = report()
    assert CHANGED64 == 0x1122334500000010
    assert rcp_dual_write(CHANGED64) == [{"offset": 0, "value": 0x11223345}]
    assert doc["changed_sink_words"] == [0x11223345, INITIAL_LO]
    assert doc["same_sink_words"] == [INITIAL_HI, INITIAL_LO]
    assert doc["dual_effect_count"] == 1
    assert doc["full_64bit_store_materialized"] is False
    encoded = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    return {**doc, "model_sha256": hashlib.sha256(encoded).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(self_test(), sort_keys=True))
