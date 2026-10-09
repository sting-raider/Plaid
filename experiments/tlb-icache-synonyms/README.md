# Cacheable TLB I-cache synonyms and remaps

Status: research worker experiment. No production files are changed.

## Question

Can a provenance/closure model collapse cacheable executable residency by only
physical backing, only virtual PC, or only the current TLB mapping, or can
cacheable TLB synonyms/remaps produce distinct resident executable generations?

## Falsifiable hypothesis

At exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`,
the interpreter selects one of 512 I-cache slots from virtual address bits while
the selected line is hit-tested against a physical 4-KiB tag. Therefore two
cacheable virtual synonyms for the same physical instruction line can occupy two
different resident slots, and invalidating/refilling only one slot can leave the
other synonym executing an older generation. Rewriting a TLB entry should not
itself end a resident lifetime; a remap away and back with no intervening fetch
should be able to expose the old line again. Conversely, fetching through a
same-VA remap to a different physical tag should force a miss/refill even if the
instruction payload is identical.

The independent pinned Gopher64 source is deliberately compared rather than
assumed equivalent. Its cache fetch path indexes from physical address, so a
reference disagreement is an expected falsifier of any N64-wide indexing claim.

## Cases

`driver.cpp` executes uninstrumented exact pinned ares with CPU/RSP recompilers
disabled and identity RDRAM:

1. VA `0x4000` and VA `0x5000` map to the same PA `0x1000`, but select ares
   I-cache indices 0 and 128.
2. VA `0x8000` maps to the same PA and shares ares index 0 with VA `0x4000`, a
   same-slot alias control.
3. After both distinct colors are resident, backing is changed from
   `ori t1,zero,0x1111` to `ori t1,zero,0x2222`; both synonyms remain stale.
4. Only the VA `0x4000` slot is invalidated/refilled. It executes `0x2222` while
   VA `0x5000` still executes `0x1111` from the same physical backing.
5. After the second color is invalidated/refilled both execute `0x2222`.
6. PA `0x1000` backing is changed again to `0x4444`; VA `0x4000` is TLBWI-remapped
   away and then back with no intervening fetch. The resident tag/valid state
   survives and the restored mapping executes stale `0x2222` with no new miss.
7. TLBWI remaps VA `0x4000` to PA `0x3000` containing identical resident
   `0x2222` instruction bytes. TLBWI itself still preserves the old cache slot,
   but the subsequent physical-tag mismatch causes a miss/refill despite equal
   payload values.
8. A second remap to PA `0x5000` with `0x3333` makes the new generation visible
   after another miss/refill.

`model.py` independently implements only the source-derived index/tag rules for
the two pinned references and constructs the one-color-refill counterexample.
It is not used to decide the exact ares execution result.

## Reproduce

Prepare the pinned reference checkouts from `refs.lock.toml`, then run:

```bash
python3 experiments/tlb-icache-synonyms/source_guard.py
python3 experiments/tlb-icache-synonyms/model.py
python3 experiments/tlb-icache-synonyms/run.py
```

The branch workflow `.github/workflows/research-tlb-icache-synonyms.yml` performs
the same exact-pin build and execution on Ubuntu.

## Scope

This experiment characterizes the exact pinned emulator implementations. It is
not a physical VR4300 cache-indexing measurement, a general TLB mapping-history
certificate, or an exhaustive executable-reachability proof. The independent
reference disagreement is specifically why the resulting Plaid obligation must
fail closed instead of declaring one emulator's synonym policy to be hardware
truth.
