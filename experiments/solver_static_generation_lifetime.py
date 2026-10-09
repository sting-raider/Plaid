#!/usr/bin/env python3
"""Adversarial model for generation identity versus lifecycle evidence.

Two causal histories intentionally collapse to the same generation-bearing static
projection once transition events are removed. The point is negative: generation
numbers alone cannot reconstruct whether a runtime transition occurred.
"""

from __future__ import annotations

import hashlib
import json


def stable(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def projection(history: dict) -> dict:
    return {
        "rom": history["rom"],
        "images": history["images"],
        "entries": history["entries"],
        "blocks": history["blocks"],
    }


COMMON = {
    "rom": "a" * 64,
    "images": [
        {"image": "same-content", "generation": 0, "pc": "80000000", "words": ["08000000", "00000000"]},
        {"image": "same-content", "generation": 9, "pc": "80000000", "words": ["08000000", "00000000"]},
    ],
    "entries": [
        {"image": "same-content", "generation": 0, "pc": "80000000"},
        {"image": "same-content", "generation": 9, "pc": "80000000"},
    ],
    "blocks": [
        {"image": "same-content", "generation": 0, "pc": "80000000", "size": 8},
        {"image": "same-content", "generation": 9, "pc": "80000000", "size": 8},
    ],
}

independent = {
    **COMMON,
    "history": [
        {"kind": "declared_static_snapshot", "generation": 0},
        {"kind": "declared_static_snapshot", "generation": 9},
    ],
}

temporal_reload = {
    **COMMON,
    "history": [
        {"kind": "install", "generation": 0},
        {"kind": "execute", "generation": 0},
        {"kind": "same_value_reload", "from_generation": 0, "to_generation": 9},
        {"kind": "execute", "generation": 9},
    ],
}

p_independent = projection(independent)
p_temporal = projection(temporal_reload)
assert p_independent == p_temporal
assert independent["history"] != temporal_reload["history"]

# Same-value reload is still a causal transition; payload equality must not erase it.
assert independent["images"][0]["words"] == temporal_reload["images"][1]["words"]

digest = hashlib.sha256(stable(p_independent)).hexdigest()
print(
    json.dumps(
        {
            "projection_equal": True,
            "causal_histories_equal": False,
            "same_value_reload": True,
            "projection_sha256": digest,
            "conclusion": "generation labels cannot recover deleted lifecycle evidence",
        },
        sort_keys=True,
    )
)
