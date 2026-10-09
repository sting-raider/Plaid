#!/usr/bin/env python3
"""Adversarial root-generation reducer for cached/uncached exception vectors.

This intentionally models generations rather than values.  A cached root fetch is
bound to the resident I-cache generation, while an uncached root fetch observes
the current backing generation.  Equal payloads therefore remain distinct writer
histories.
"""
from __future__ import annotations

import hashlib
import json

CACHED_GENERAL = 0xFFFFFFFF80000180
UNCACHED_BOOT_GENERAL = 0xFFFFFFFFBFC00380


def replay(events: list[dict]) -> list[dict]:
    backing: dict[int, dict | None] = {}
    resident: dict[int, dict] = {}
    next_backing_generation = 0
    out: list[dict] = []

    for ordinal, event in enumerate(events):
        kind = event["kind"]
        va = event.get("va")
        if kind == "backing_write":
            next_backing_generation += 1
            backing[va] = {
                "generation": next_backing_generation,
                "payload": event["payload"],
                "event": ordinal,
            }
        elif kind == "fill":
            source = backing.get(va)
            if source is None:
                raise AssertionError("fill without a known backing generation")
            resident[va] = {
                "resident_generation": event["resident_generation"],
                "backing_generation": source["generation"],
                "payload": source["payload"],
                "fill_event": ordinal,
            }
        elif kind == "invalidate":
            resident.pop(va, None)
        elif kind == "root_fetch":
            policy = event["policy"]
            current = backing.get(va)
            naive = None if current is None else {
                "generation": current["generation"],
                "payload": current["payload"],
            }
            if policy == "cached":
                line = resident.get(va)
                strict = None if line is None else {
                    "origin": "resident",
                    "generation": line["backing_generation"],
                    "resident_generation": line["resident_generation"],
                    "payload": line["payload"],
                }
            elif policy == "uncached":
                strict = None if current is None else {
                    "origin": "backing",
                    "generation": current["generation"],
                    "payload": current["payload"],
                }
            else:
                raise AssertionError(f"unknown cache policy {policy}")
            out.append({
                "event": ordinal,
                "va": f"0x{va:016x}",
                "policy": policy,
                "strict": strict,
                "naive_current_backing": naive,
            })
        else:
            raise AssertionError(f"unknown event kind {kind}")
    return out


def main() -> None:
    histories = {
        "stale_changed": [
            {"kind": "backing_write", "va": CACHED_GENERAL, "payload": "old"},
            {"kind": "fill", "va": CACHED_GENERAL, "resident_generation": "r1"},
            {"kind": "backing_write", "va": CACHED_GENERAL, "payload": "new"},
            {"kind": "root_fetch", "va": CACHED_GENERAL, "policy": "cached"},
        ],
        "post_write_refill": [
            {"kind": "backing_write", "va": CACHED_GENERAL, "payload": "old"},
            {"kind": "fill", "va": CACHED_GENERAL, "resident_generation": "r1"},
            {"kind": "backing_write", "va": CACHED_GENERAL, "payload": "new"},
            {"kind": "invalidate", "va": CACHED_GENERAL},
            {"kind": "fill", "va": CACHED_GENERAL, "resident_generation": "r2"},
            {"kind": "root_fetch", "va": CACHED_GENERAL, "policy": "cached"},
        ],
        "refill_before_write": [
            {"kind": "backing_write", "va": CACHED_GENERAL, "payload": "old"},
            {"kind": "fill", "va": CACHED_GENERAL, "resident_generation": "r1"},
            {"kind": "invalidate", "va": CACHED_GENERAL},
            {"kind": "fill", "va": CACHED_GENERAL, "resident_generation": "r2"},
            {"kind": "backing_write", "va": CACHED_GENERAL, "payload": "new"},
            {"kind": "root_fetch", "va": CACHED_GENERAL, "policy": "cached"},
        ],
        "same_value_replacement": [
            {"kind": "backing_write", "va": CACHED_GENERAL, "payload": "same"},
            {"kind": "fill", "va": CACHED_GENERAL, "resident_generation": "r1"},
            {"kind": "backing_write", "va": CACHED_GENERAL, "payload": "same"},
            {"kind": "root_fetch", "va": CACHED_GENERAL, "policy": "cached"},
        ],
        "uncached_bev_control": [
            {"kind": "backing_write", "va": UNCACHED_BOOT_GENERAL, "payload": "boot-old"},
            {"kind": "backing_write", "va": UNCACHED_BOOT_GENERAL, "payload": "boot-new"},
            {"kind": "root_fetch", "va": UNCACHED_BOOT_GENERAL, "policy": "uncached"},
        ],
        "missing_resident": [
            {"kind": "backing_write", "va": CACHED_GENERAL, "payload": "known"},
            {"kind": "root_fetch", "va": CACHED_GENERAL, "policy": "cached"},
        ],
    }

    results = {name: replay(events)[-1] for name, events in histories.items()}

    # Changed backing after a fill must not steal the cached root's generation.
    assert results["stale_changed"]["strict"]["generation"] == 1
    assert results["stale_changed"]["naive_current_backing"]["generation"] == 2
    # A refill after the write moves residency to the new backing generation.
    assert results["post_write_refill"]["strict"]["generation"] == 2
    # A refill before the write remains stale despite having a newer resident ID.
    assert results["refill_before_write"]["strict"]["generation"] == 1
    assert results["refill_before_write"]["strict"]["resident_generation"] == "r2"
    # Same bytes are still a different backing generation and a naive value-based
    # join silently substitutes provenance.
    same = results["same_value_replacement"]
    assert same["strict"]["payload"] == same["naive_current_backing"]["payload"] == "same"
    assert same["strict"]["generation"] == 1 and same["naive_current_backing"]["generation"] == 2
    # BEV=1 general exception address is in the uncached boot segment; no resident
    # generation is needed for this model control.
    assert results["uncached_bev_control"]["strict"]["origin"] == "backing"
    assert results["uncached_bev_control"]["strict"]["generation"] == 2
    # Current RAM at a cached vector is not enough to manufacture a root identity.
    assert results["missing_resident"]["strict"] is None
    assert results["missing_resident"]["naive_current_backing"] is not None

    report = {
        "schema": "plaid.exception-root-generation.model.v1",
        "history_count": len(histories),
        "results": results,
        "naive_failures": [
            "stale_changed",
            "refill_before_write",
            "same_value_replacement",
            "missing_resident",
        ],
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    print(canonical)
    print("REPORT_SHA256=" + digest)
    print("PASS: cached exception roots require resident-generation evidence; 4 vector/current-backing forgeries rejected")


if __name__ == "__main__":
    main()
