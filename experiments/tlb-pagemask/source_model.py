#!/usr/bin/env python3
"""Independent model for the exact pinned-ares PageMask-derived TLB geometry."""
from __future__ import annotations

import hashlib
import json
import random

MASK40 = (1 << 40) - 1
ARES_PAIR_BITS = 0b101010101010 << 13


def normalize_page_mask(raw: int) -> int:
    value = raw & ARES_PAIR_BITS
    return value | (value >> 1)


def geometry(raw: int) -> dict[str, int]:
    page_mask = normalize_page_mask(raw)
    pair_mask = page_mask | 0x1FFF
    address_mask_hi = (~pair_mask) & MASK40
    address_mask_lo = pair_mask >> 1
    address_select = address_mask_lo + 1
    return {
        "page_mask": page_mask,
        "address_mask_hi": address_mask_hi,
        "address_mask_lo": address_mask_lo,
        "address_select": address_select,
        "page_size": address_select,
        "pair_size": address_select * 2,
    }


def translate(vaddr: int, raw_mask: int, pbase0: int, pbase1: int) -> tuple[int, int]:
    g = geometry(raw_mask)
    lo = 1 if vaddr & g["address_select"] else 0
    paddr = (pbase1 if lo else pbase0) + (vaddr & g["address_mask_lo"])
    return lo, paddr


def fixed_4k_guess(vaddr: int, pbase0: int, pbase1: int) -> tuple[int, int]:
    lo = 1 if vaddr & 0x1000 else 0
    return lo, (pbase1 if lo else pbase0) + (vaddr & 0xFFF)


def main() -> None:
    # These readback-normalization examples are also present in pinned n64-systemtest.
    normalization = [
        (0, 0),
        (0b11 << 13, 0b11 << 13),
        (0b1111 << 13, 0b1111 << 13),
        (0b1 << 13, 0),
        (0b111 << 13, 0b11 << 13),
        (0b10 << 13, 0b11 << 13),
        (0b1000 << 13, 0b1100 << 13),
    ]
    for raw, expected in normalization:
        assert normalize_page_mask(raw) == expected, (raw, normalize_page_mask(raw), expected)

    assert geometry(0)["address_select"] == 0x1000
    assert geometry(0b11 << 13)["address_select"] == 0x4000
    assert geometry(0b1111 << 13)["address_select"] == 0x10000

    cases = [
        # label, mask, vaddr, pbase0, pbase1, expected lo, expected paddr
        ("4k_control", 0, 0x00004000, 0x001000, 0x002000, 0, 0x001000),
        ("16k_even_bit12_one", 0b11 << 13, 0x00021000, 0x010000, 0x020000, 0, 0x011000),
        ("16k_odd_bit12_zero", 0b11 << 13, 0x0002C000, 0x030000, 0x040000, 1, 0x040000),
        ("64k_even_bit12_one", 0b1111 << 13, 0x00045000, 0x050000, 0x070000, 0, 0x055000),
        ("64k_odd_bit12_zero", 0b1111 << 13, 0x00070000, 0x080000, 0x0A0000, 1, 0x0A0000),
        ("16k_global_odd", 0b11 << 13, 0x00084000, 0x0C0000, 0x0D0000, 1, 0x0D0000),
    ]
    rows = []
    for label, mask, vaddr, p0, p1, expected_lo, expected_paddr in cases:
        actual_lo, actual_paddr = translate(vaddr, mask, p0, p1)
        naive_lo, naive_paddr = fixed_4k_guess(vaddr, p0, p1)
        assert (actual_lo, actual_paddr) == (expected_lo, expected_paddr), label
        if mask == 0:
            assert (naive_lo, naive_paddr) == (actual_lo, actual_paddr)
        else:
            assert (naive_lo, naive_paddr) != (actual_lo, actual_paddr), label
        rows.append({
            "label": label,
            "mask": mask,
            "vaddr": vaddr,
            "actual_lo": actual_lo,
            "actual_paddr": actual_paddr,
            "fixed4k_lo": naive_lo,
            "fixed4k_paddr": naive_paddr,
        })

    rng = random.Random(0x504C414944)
    mismatches = 0
    total = 0
    for mask in (0b11 << 13, 0b1111 << 13, 0b111111 << 13, 0b11111111 << 13):
        g = geometry(mask)
        pair_base = 0x200000
        p0, p1 = 0x100000, 0x500000
        for _ in range(25000):
            offset = rng.randrange(g["pair_size"])
            vaddr = pair_base + offset
            actual = translate(vaddr, mask, p0, p1)
            guessed = fixed_4k_guess(vaddr, p0, p1)
            mismatches += actual != guessed
            total += 1
    assert total == 100000
    assert mismatches > 90000, mismatches

    result = {
        "normalization": normalization,
        "geometry": {
            "4k": geometry(0),
            "16k": geometry(0b11 << 13),
            "64k": geometry(0b1111 << 13),
        },
        "cases": rows,
        "fuzz_total": total,
        "fixed4k_mismatches": mismatches,
    }
    packed = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    print("MODEL_JSON=" + packed.decode())
    print("MODEL_SHA256=" + hashlib.sha256(packed).hexdigest())
    print(f"PASS source model: fixed-4KiB reconstruction mismatched {mismatches}/{total} large-page samples")


if __name__ == "__main__":
    main()
