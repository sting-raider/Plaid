# ares TLBP/TLBR mapping-state effects

Status: IN PROGRESS

Canonical Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Pinned independent comparison: Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

## Hypothesis

For the exact pinned ares interpreter, `TLBP` and `TLBR` are observational with respect to translation-visible TLB mappings. `TLBP` changes CP0 Index probe state; `TLBR` copies one selected TLB entry into staged CP0 TLB fields. Neither should create a mapping generation, clear translation caches, or change subsequent translation results. Those CP0 effects still belong in ordered architectural state.

## Source-derived baseline

Pinned ares `CPU::TLBP()` initializes Index to probe-failure state, scans `tlb.entry[]`, and on the first match updates only `scc.index`. Pinned `CPU::TLBR()` rejects an out-of-range Index and otherwise assigns `scc.tlb = tlb.entry[scc.index.tlbEntry]`. Neither function contains the `devirtualizeCache = {}`, TLB-entry replacement/synchronization, or `debugger.tlbWrite()` path used by TLB writes.

Pinned Gopher64 independently separates `tlb::read()` and `tlb::probe()` from `tlb_unmap()`/`tlb_map()`: read copies the chosen entry into CP0 PageMask/EntryHi/EntryLo registers, while probe writes COP0 Index.

These source observations are not the final result. The exact-reference executable matrix in `experiments/tlbp-tlbr-effects/` is intended to falsify them with cached-translation state already populated and adversarial equal mappings/staged values.

## Scope and non-claims

This lane does not solve TLBWI/TLBWR mutation generations, save/restore/reset epochs, PageMask geometry, cacheable I-cache provenance, overlapping-entry hardware behavior, whole-ROM reachability, or whether emulator consensus equals hardware truth. Probe-miss Index payload beyond the failure bit is not promoted to an architectural invariant.
