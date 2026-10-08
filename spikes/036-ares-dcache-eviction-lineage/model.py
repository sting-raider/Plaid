"""Deterministic byte-lineage model for a dirty D-cache victim eviction.

This is independent of ares. It models only the provenance obligation that the
exact-reference fixture is intended to test: an outgoing 16-byte resident line
contains a mixture of fill-origin and later store-origin bytes, while backing may
have been changed through uncached aliases and the cache slot is immediately
reused for a different physical tag after eviction.
"""
from __future__ import annotations

import hashlib
import json

DEST_FILL = bytes.fromhex("aabbccdd010203041122334455667788")
SOURCE_WORD = bytes.fromhex("11223344")
DECOY_DIRTY_LANE = bytes.fromhex("deadbeef")
DECOY_CLEAN_LANE = bytes.fromhex("feedface")
CONFLICT_FILL = bytes.fromhex("cafebabe0badf00d89abcdef13579bdf")
DIRTY_MASK = 0x000F


def build_report() -> dict:
    resident = bytearray(DEST_FILL)
    resident_origins = [f"dest_fill:{i}" for i in range(16)]

    # Cached SW changes only resident bytes 0..3 and marks those lanes dirty.
    resident[:4] = SOURCE_WORD
    resident_origins[:4] = [f"source_load:{i}" for i in range(4)]

    # Uncached aliases mutate both a dirty word and a nominally clean word in
    # backing after the cached store. Neither may replace resident-line lineage.
    backing = bytearray(DEST_FILL)
    backing[:4] = DECOY_DIRTY_LANE
    backing[4:8] = DECOY_CLEAN_LANE
    backing_before = bytes(backing)

    outgoing = bytes(resident)
    outgoing_origins = resident_origins[:]

    # Conflict miss writes the full outgoing line, including bytes not marked
    # dirty, then reuses the same slot for a different physical tag/line.
    backing[:] = outgoing
    slot_after_replacement = CONFLICT_FILL

    dirty_bytes = sum(1 for lane in range(16) if DIRTY_MASK >> lane & 1)

    return {
        "pre_eviction": {
            "resident_hex": outgoing.hex(),
            "backing_hex": backing_before.hex(),
            "dirty_mask": DIRTY_MASK,
            "resident_origins": outgoing_origins,
        },
        "writeback_hex": outgoing.hex(),
        "writeback_origins": outgoing_origins,
        "backing_after_hex": backing.hex(),
        "slot_after_replacement_hex": slot_after_replacement.hex(),
        "counterexamples": {
            "current_backing_wrong": backing_before != outgoing,
            "clean_lane_backing_change_is_overwritten": backing_before[4:8] != outgoing[4:8] and backing[4:8] == outgoing[4:8],
            "post_replacement_slot_wrong": slot_after_replacement != outgoing,
            "dirty_mask_does_not_describe_full_write_width": dirty_bytes != 16,
        },
    }


def main() -> None:
    report = build_report()
    assert report["pre_eviction"]["dirty_mask"] == 0x000F
    assert report["pre_eviction"]["backing_hex"] == "deadbeeffeedface1122334455667788"
    assert report["writeback_hex"] == "11223344010203041122334455667788"
    assert report["backing_after_hex"] == report["writeback_hex"]
    assert all(report["counterexamples"].values())
    assert report["writeback_origins"][:4] == [f"source_load:{i}" for i in range(4)]
    assert report["writeback_origins"][4:] == [f"dest_fill:{i}" for i in range(4, 16)]

    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    print("REPORT_SHA256", digest)
    print(canonical)


if __name__ == "__main__":
    main()
