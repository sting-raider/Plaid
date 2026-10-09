#!/usr/bin/env python3
"""Independent minimal models for the exact pinned ares/Gopher64 I-cache index rules."""
from __future__ import annotations
import hashlib
import json

VA_A = 0x4000
VA_B = 0x5000
VA_C = 0x8000
PA_A = 0x1000
PA_B = 0x3000
OLD = 0x34091111
NEW = 0x34092222


def ares_index(vaddr: int, _paddr: int) -> int:
    return (vaddr >> 5) & 0x1FF


def gopher_index(_vaddr: int, paddr: int) -> int:
    return (paddr >> 5) & 0x1FF


def ptag(paddr: int) -> int:
    return paddr & ~0xFFF


class Cache:
    def __init__(self, index_fn):
        self.index_fn = index_fn
        self.lines: dict[int, tuple[int, int]] = {}
        self.misses = 0

    def fetch(self, vaddr: int, paddr: int, backing: dict[int, int]) -> int:
        idx = self.index_fn(vaddr, paddr)
        line = self.lines.get(idx)
        if line is None or line[0] != ptag(paddr):
            self.misses += 1
            self.lines[idx] = (ptag(paddr), backing[paddr])
        return self.lines[idx][1]

    def invalidate(self, vaddr: int, paddr: int) -> None:
        self.lines.pop(self.index_fn(vaddr, paddr), None)


def exercise(index_fn):
    backing = {PA_A: OLD, PA_B: NEW}
    cache = Cache(index_fn)
    first_a = cache.fetch(VA_A, PA_A, backing)
    first_c = cache.fetch(VA_C, PA_A, backing)
    first_b = cache.fetch(VA_B, PA_A, backing)
    after_initial_misses = cache.misses
    backing[PA_A] = NEW
    stale_a = cache.fetch(VA_A, PA_A, backing)
    stale_b = cache.fetch(VA_B, PA_A, backing)
    cache.invalidate(VA_A, PA_A)
    fresh_a = cache.fetch(VA_A, PA_A, backing)
    after_a_refill = cache.misses
    b_after_a_refill = cache.fetch(VA_B, PA_A, backing)
    # Equal-payload remap: same VA, new PA/page tag, same word bytes.
    before_remap = cache.misses
    equal_remap = cache.fetch(VA_A, PA_B, backing)
    return {
        "indices": [index_fn(VA_A, PA_A), index_fn(VA_B, PA_A), index_fn(VA_C, PA_A)],
        "first": [first_a, first_b, first_c],
        "initial_misses": after_initial_misses,
        "stale": [stale_a, stale_b],
        "fresh_a": fresh_a,
        "b_after_a_refill": b_after_a_refill,
        "misses_after_a_refill": after_a_refill,
        "equal_remap": equal_remap,
        "equal_remap_missed": cache.misses == before_remap + 1,
    }


def main() -> None:
    ares = exercise(ares_index)
    gopher = exercise(gopher_index)

    assert ares["indices"] == [0, 128, 0]
    assert ares["initial_misses"] == 2
    assert ares["stale"] == [OLD, OLD]
    assert ares["fresh_a"] == NEW
    assert ares["b_after_a_refill"] == OLD  # distinct virtual-color resident generation
    assert ares["equal_remap_missed"]

    assert gopher["indices"] == [128, 128, 128]
    assert gopher["initial_misses"] == 1
    assert gopher["stale"] == [OLD, OLD]
    assert gopher["fresh_a"] == NEW
    assert gopher["b_after_a_refill"] == NEW  # physical index collapses the synonym
    assert gopher["equal_remap_missed"]

    report = {
        "ares_pin_model": ares,
        "gopher_pin_model": gopher,
        "counterexample": {
            "same_physical_backing_after_one_color_refill": {
                "ares_va_b": ares["b_after_a_refill"],
                "gopher_va_b": gopher["b_after_a_refill"],
            },
            "conclusion": "the two pinned references disagree on virtual-synonym residency; do not promote either indexing rule to hardware truth",
        },
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    print(canonical)
    print("MODEL_SHA256=" + digest)
    print("PASS: ares virtual-color model admits divergent same-PA residents; pinned Gopher64 physical-index model does not")


if __name__ == "__main__":
    main()
