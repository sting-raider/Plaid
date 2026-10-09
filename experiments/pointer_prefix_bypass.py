#!/usr/bin/env python3
"""Deterministic reducer for pointer-table guarded-prefix reachability facts.

This does not model MIPS execution. The Rust regression is the executable proof.
It freezes the address/image/generation classification used by the conservative
certificate guard so the exact adversarial matrix has a stable digest.
"""

import hashlib
import json

BLOCK_START = 0x8000000C
SITE = 0x80000020
IMAGE = "prefix-bypass"
GENERATION = 0

CASES = [
    {"kind": "entry", "pc": pc, "image": IMAGE, "generation": GENERATION, "bypass": True}
    for pc in (0x80000010, 0x80000014, 0x80000018, 0x8000001C, 0x80000020)
] + [
    {"kind": "direct", "pc": 0x80000014, "image": IMAGE, "generation": GENERATION, "bypass": True},
    {"kind": "candidate", "pc": 0x80000014, "image": IMAGE, "generation": GENERATION, "bypass": True},
    {"kind": "observed", "pc": 0x80000014, "image": IMAGE, "generation": GENERATION, "bypass": True},
    {"kind": "entry", "pc": 0x8000000C, "image": IMAGE, "generation": GENERATION, "bypass": False},
    {"kind": "entry", "pc": 0x80000040, "image": IMAGE, "generation": GENERATION, "bypass": False},
    {"kind": "entry", "pc": 0x80000014, "image": IMAGE, "generation": 1, "bypass": False},
    {"kind": "entry", "pc": 0x80000014, "image": "other-image", "generation": GENERATION, "bypass": False},
]


def bypasses_guard(case: dict[str, object]) -> bool:
    return (
        case["image"] == IMAGE
        and case["generation"] == GENERATION
        and BLOCK_START < int(case["pc"]) <= SITE
    )


for case in CASES:
    actual = bypasses_guard(case)
    assert actual == case["bypass"], (case, actual)

payload = json.dumps(CASES, sort_keys=True, separators=(",", ":")).encode()
print(
    json.dumps(
        {
            "block_start": f"0x{BLOCK_START:08x}",
            "site": f"0x{SITE:08x}",
            "cases": len(CASES),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        sort_keys=True,
    )
)
