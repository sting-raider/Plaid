# MTC0 EntryHi ASID is a translation-context mutation

Date: 2026-10-09

Status: **IN PROGRESS** pending exact-pinned executable matrix.

Canonical Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.
Primary reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Question

Can Plaid reconstruct TLB-visible executable lifetimes from installed-entry generations alone, or can guest `MTC0 EntryHi` change which already-installed non-global mapping supplies a later instruction fetch without changing a single TLB entry?

## Falsifiable hypothesis

An interpreted `MTC0 EntryHi` can change the active ASID consumed by non-global TLB matching. Consequently the same mapped virtual PC may resolve to a different physical executable backing after an EntryHi write even if all installed entries are byte-for-byte unchanged. Global mappings must ignore this ASID change. A repeated same-value EntryHi write is still an ordered context write even though snapshot-diff observes no state delta.

## Exact pinned source basis

At the pinned ares revision, `CPU::MTC0` calls `setControlRegister(rd, rt.u64)`. Control register 10 writes `scc.tlb.addressSpaceID`, EntryHi VPN bits, and region. Separately, `TLB::load` rejects a non-global entry when `entry.addressSpaceID != self.scc.tlb.addressSpaceID` before selecting its physical address. Installed-entry mutation and synchronization occur in `TLBWI`/`TLBWR`; the EntryHi setter itself does not write `tlb.entry[]`.

This source relation is only the hypothesis basis. The branch contains an executable matrix that must pass before a result is claimed.

## Experiment design

`experiments/mtc0-entryhi-asid/driver.cpp` installs three non-global mappings for VA `0x4000`:

- ASID `0x11` -> PA `0x1000`, instruction `ORI t1,zero,0x1111`;
- ASID `0x22` -> PA `0x3000`, instruction `ORI t1,zero,0x2222`;
- ASID `0x33` -> PA `0x5000`, the same instruction bytes as ASID `0x11`.

It also installs one global VA `0x8000` mapping to PA `0x7000`. Each context transition executes real opcode `0x40885000` (`MTC0 t0,EntryHi`) in the pinned interpreter with recompilers disabled. A semantic serialization of all installed TLB entries is compared after every context write.

The matrix tests different-backing switches, equal-payload/different-backing identity, an identical repeated EntryHi write, global-ASID independence, and an unmatched-ASID miss. `model.py` stress-tests a reducer that retains a VA->PA resolution until an installed-entry mutation occurs.

## Limits

This lane excludes TLBWI/TLBWR generation identity, PageMask geometry, cacheable I-cache synonyms, TLBR semantics, save/restore/reset epochs, overlapping-entry hardware corner cases, privilege-mode reachability, and whole-ROM closure. It will not promote pinned-emulator behavior into hardware truth.
