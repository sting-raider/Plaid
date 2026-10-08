#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Deterministic source-contract stress model for pinned ares TLB::load semantics.

This is supporting evidence only. Exact-reference execution lives in run.py.
"""
from dataclasses import dataclass
import hashlib
import random

MASK40 = (1 << 40) - 1


@dataclass
class Entry:
    page_mask: int = 0
    virtual_address: int = 0
    asid: int = 0
    region: int = 0
    global0: bool = False
    global1: bool = False
    valid0: bool = True
    valid1: bool = True
    cache0: int = 2
    cache1: int = 2
    physical0: int = 0
    physical1: int = 0

    def synchronize(self):
        # Mirrors the exact pinned ares Entry::synchronize mask equations.
        self.page_mask &= 0b101010101010 << 13
        self.page_mask |= self.page_mask >> 1
        globals_ = self.global0 and self.global1
        address_mask_hi = (~(self.page_mask | 0x1fff)) & MASK40
        address_mask_lo = (self.page_mask | 0x1fff) >> 1
        address_select = address_mask_lo + 1
        self.physical0 &= 0xffffffff
        self.physical1 &= 0xffffffff
        self.virtual_address &= address_mask_hi
        self.global0 = self.global1 = globals_
        return address_mask_hi, address_mask_lo, address_select, globals_


def load(entry, vaddr, current_asid):
    mask_hi, mask_lo, select, globals_ = entry.synchronize()
    vaddr &= (1 << 64) - 1
    v40 = vaddr & MASK40
    if not globals_ and entry.asid != current_asid:
        return None
    if (v40 & mask_hi) != entry.virtual_address:
        return None
    if ((vaddr >> 62) & 3) != entry.region:
        return None
    lo = 1 if v40 & select else 0
    valid = entry.valid1 if lo else entry.valid0
    if not valid:
        return ("invalid",)
    physical = (entry.physical1 if lo else entry.physical0) + (v40 & mask_lo)
    cca = entry.cache1 if lo else entry.cache0
    return {"cache": cca != 2, "paddr": physical, "vaddr": vaddr, "cca": cca}


def main():
    observed = {}
    for cca in range(8):
        access = load(Entry(virtual_address=0x4000, asid=7, cache0=cca, physical0=0x1000), 0x4000, 7)
        observed[cca] = access["cache"]
    assert observed == {cca: cca != 2 for cca in range(8)}

    first = load(Entry(virtual_address=0x4000, asid=7, cache0=2, physical0=0x1000), 0x4000, 7)
    alias = load(Entry(virtual_address=0x8000, asid=7, cache0=2, physical0=0x1000), 0x8000, 7)
    assert first["paddr"] == alias["paddr"] and first["vaddr"] != alias["vaddr"]
    assert not first["cache"] and not alias["cache"]

    assert load(Entry(virtual_address=0x4000, asid=1, cache0=2, physical0=0x1000), 0x4000, 99) is None
    global_entry = Entry(virtual_address=0x4000, asid=1, global0=True, global1=True,
                         cache0=2, physical0=0x1000)
    assert load(global_entry, 0x4000, 99)["paddr"] == 0x1000
    invalid = Entry(virtual_address=0x4000, asid=7, valid0=False, cache0=2, physical0=0x1000)
    assert load(invalid, 0x4000, 7) == ("invalid",)
    assert (0x7000 ^ 4) == 0x7004

    rng = random.Random(0x504C414944)
    accepted = uncached = 0
    digest = hashlib.sha256()
    for index in range(100_000):
        va = (rng.randrange(0, 1 << 27) << 13) & MASK40
        pa = (rng.randrange(0, 1 << 20) << 12) & 0xffffffff
        cca = rng.randrange(8)
        asid = rng.randrange(256)
        current = rng.randrange(256)
        global_ = bool(rng.randrange(2))
        valid = bool(rng.randrange(2))
        entry = Entry(virtual_address=va, asid=asid, global0=global_, global1=global_,
                      valid0=valid, valid1=True, cache0=cca, cache1=cca,
                      physical0=pa, physical1=(pa + 0x1000) & 0xffffffff)
        access = load(entry, va, current)
        if access is None or access == ("invalid",):
            outcome = "none" if access is None else "invalid"
        else:
            accepted += 1
            if not access["cache"]:
                uncached += 1
                assert cca == 2
            else:
                assert cca != 2
            outcome = f"{access['paddr']:x}:{int(access['cache'])}:{access['vaddr']:x}"
        digest.update(f"{index}:{va:x}:{pa:x}:{cca}:{asid}:{current}:{int(global_)}:{int(valid)}:{outcome}\n".encode())

    expected_digest = "e9890debc340c0ef26016f757cf2e50ff8fd26344ef2a4342bceb597d02976af"
    assert accepted == 25096
    assert uncached == 3143
    assert digest.hexdigest() == expected_digest
    print(f"PASS cases=100000 accepted={accepted} uncached={uncached} sha256={expected_digest}")


if __name__ == "__main__":
    main()
