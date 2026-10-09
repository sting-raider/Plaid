# PageMask + I-cache remap composition

This bounded worker experiment composes previously validated Plaid research instead of re-proving the individual primitives.

Inputs:

- large PageMask TLB translation: the selected EntryLo half and physical offset follow normalized PageMask geometry, not fixed bit 12 / low 12 bits;
- TLBWI/TLBWR mapping operations: legal same-value writes are still ordered operation generations;
- cacheable TLB executable lifetime: current mapping/backing does not identify bytes fetched from a resident I-cache line, and a TLB rewrite alone is not a resident lifetime end;
- ASID/context research: mapping reachability can change independently of installed-entry identity.

The exact-pinned ares fixture exercises a 16 KiB mapping where bit 12 deliberately selects the wrong half under a naive 4 KiB model, same-value TLBWI, backing mutation under a resident hit, equal-payload remap to a different physical tag, remap-away/back without an intervening fetch, temporary ASID unreachability, a same-VA 16 KiB -> 64 KiB geometry change, and a 64 KiB odd-half control with an equal-valued fixed-4K decoy.

`model.py` independently tracks five identities which must not be collapsed: mapping-operation generation, translation-context generation, translated physical address, backing-writer generation, and cache-resident generation. It deliberately forges each dimension and rejects fixed-4K reconstruction/current-backing/value-equality shortcuts. A deterministic 50,000-case large-page sweep measures how often fixed-4K reconstruction chooses a different half/address/tag.

Reproduce with exact refs checked out under `.refs/`:

```sh
python3 -m py_compile experiments/pagemask-icache-remap/{source_guard.py,model.py,run.py}
python3 experiments/pagemask-icache-remap/source_guard.py
python3 experiments/pagemask-icache-remap/model.py
python3 experiments/pagemask-icache-remap/run.py
sha256sum target/pagemask-icache-remap/results.json
```

This is a provenance/lifetime composition test, not a claim that pinned ares cache indexing is hardware truth. Pinned Gopher64 uses physical rather than ares-style virtual cache indexing, and that disagreement is preserved by the source guard.
