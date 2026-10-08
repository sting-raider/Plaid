"""Deterministic byte-lineage model for a dirty D-cache victim eviction.

This is independent of ares.  It models only the provenance obligation that the
exact-reference fixture is intended to test: an outgoing 16-byte resident line
contains a mixture of fill-origin and later store-origin bytes, while backing may
have been changed through an uncached alias and the cache slot is immediately
reused for a different physical tag after eviction.
"""
from __future__ import annotations

import hashlib
import json

DEST_FILL = bytes.fromhex("aabbccdd010203041122334455667788")
SOURCE_WORD = bytes.fromhex("11223344")
DECOY_BACKING = bytes.fromhex("deadbeef")
CONFLICT_FILL = bytes.fromhex("cafebabe0badf00d89abcdef13579bdf")
DIRTY_MASK = 0x000F


def build_report() -> dict:
    resident = bytearray(DEST_FILL)
    resident_origins = [f"dest_fill:{i}" for i in range(16)]

    # Cached SW changes only resident bytes 0..3 and marks those lanes dirty.
    resident[:4] = SOURCE_WORD
    resident_origins[:4] = [f"source_load:{i}" for i in range(4)]

    # An uncached alias changes current backing after the cached store.  This is
    # deliberately a decoy: it must not replace the resident-line lineage.
    backing = bytearray(DEST_FILL)
    backing[:4] = DECOY_BACKING

    outgoing = bytes(resident)
    outgoing_origins = resident_origins[:]

    # Conflict miss writes the full outgoing line, then reuses the same slot for
    # a different physical tag/line.
    backing[:] = outgoing
    slot_after_replacement = CONFLICT_FILL

    wrong_current_backing = DECOY_BACKING + DEST_FILL[4:]
    dirty_bytes = sum(1 for lane in range(16) if DIRTY_MASK >> lane & 1)

    return {
        "pre_eviction": {
            "resident_hex": outgoing.hex(),
            "backing_hex": (DECOY_BACKING + DEST_FILL[4:]).hex(),
            "dirty_mask": DIRTY_MASK,
            "resident_origins": outgoing_origins,
        },
        "writeback_hex": outgoing.hex(),
        "writeback_origins": outgoing_origins,
        "backing_after_hex": backing.hex(),
        "slot_after_replacement_hex": slot_after_replacement.hex(),
        "counterexamples": {
            "current_backing_wrong": wrong_current_backing != outgoing,
            "post_replacement_slot_wrong": slot_after_replacement != outgoing,
            "dirty_mask_does_not_describe_full_write_width": dirty_bytes != 16,
        },
    }


def main() -> None:
    report = build_report()
    assert report["pre_eviction"]["dirty_mask"] == 0x000F
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
