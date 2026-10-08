# Spike 034: ares D-cache writeback lineage

Result status while running: **PARTIAL / experimental**.

This spike tests one bounded question at exact pinned ares revision
`9408cb43d4948fc3ea6e152a307a34348df3fe04`: can a cached VR4300 word-store
mutation be carried through a specific resident D-cache line generation to the
exact later identity-RDRAM burst writeback, without inferring provenance from
address/value equality alone?

The headless fixture disables both recompilers and uses controlled identity RDRAM.
Generated instrumentation does not add fields to ares objects. It observes:

- successful D-cache fills after their backing burst returns;
- completed cache-resident writes and dirty masks;
- entry/exit of `DataCache::Line::writeBack()`;
- matching-line invalidation via `setValid(false)`;
- completed eligible identity-RDRAM burst reads/writes.

All event families share one capture ordinal. Baseline, generated-observer-disabled,
observer-enabled, and repeat observer-enabled runs must preserve the same guest/
emulator state; repeat traces must be byte-identical.

Four adversarial guest phases are executed:

1. cached `SW` followed by `CACHE 0x19` hit writeback;
2. cached `SW` followed by a same-index/different-tag load that forces dirty eviction;
3. clean same-index replacement where A and B deliberately have identical payloads;
4. cached `SW`, then `CACHE 0x11` hit invalidate, then replacement. The dirty
   mutation must be dropped without any RDRAM writeback certificate.

`run.py` also consumes the measured shared-ordinal trace with a fail-closed line
version verifier. A certificate requires a joined successful backing fill, the
same resident generation, the observed cache mutation, `writeback_begin`, an
exact nested RDRAM burst write with matching address/payload, and
`writeback_end`. Invalidation or replacement retires resident lineage.

`model.py` independently stresses that contract with fixed counterexamples and
seeded histories, including same-payload wrong-generation writes.

## Reproduce

Populate `.refs/ares` at the pinned revision, then run:

```sh
python3 spikes/034-ares-dcache-writeback-lineage/model.py
python3 spikes/034-ares-dcache-writeback-lineage/run.py
```

The runner writes ignored build/results under
`target/ares-dcache-writeback-lineage-spike/` and prints exact source, trace, and
result SHA-256 hashes. No ROM or firmware asset is committed.

## Scope limits

This is deliberately not a global N64 cache proof. It does not cover arbitrary
TLB/cacheability histories, reverse-endian modes, partial/64-bit store families,
reset/save-state epochs, external DMA coherence, RSP caches, non-identity RDRAM,
or complete executable-universe closure. It establishes only the controlled
cached-store to actual backing-write join needed to avoid treating resident
D-cache mutation as immediate or inevitable RDRAM mutation.
