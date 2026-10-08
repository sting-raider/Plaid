# ares dirty D-cache eviction lineage

Date: 2026-10-08

Result: **VALIDATED** for the bounded exact-pinned-ares identity-RDRAM scope below.

Integration recommendation: **ADOPT** the lineage invariant. A production Plaid provenance system must preserve versioned per-byte D-cache residency through ordinary replacement and join the outgoing resident generation to the completed backing writeback. Do not interpret the D-cache dirty mask as the physical backing write span.

## Question

Can a cached CPU-store byte-origin witness survive an ordinary D-cache index-conflict eviction strongly enough to identify the exact bytes subsequently written to backing RDRAM? What identity must be retained so replacement cannot attach the writeback to stale backing state or to the newly filled line that reuses the same cache slot?

The dangerous simplifications tested here were:

1. current RDRAM contents identify the origin/value being written back;
2. cache slot/index alone identifies the resident line across a replacement;
3. the D-cache dirty mask describes the bytes physically written to backing memory.

All three are false in the bounded fixture.

## Reference revision and source map

Pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Relevant exact-pin source behavior:

### `ares/n64/cpu/dcache.cpp`

- `DataCache::line(vaddr)` selects `lines[vaddr >> 4 & 0x1ff]`.
- `Line::hit(paddr)` compares the resident physical tag (ignoring the validity bit) with the requested physical tag.
- `Line::write<Size>` updates resident bytes/halves/words and ORs only the addressed byte lanes into `dirty`.
- `DataCache::read` and `DataCache::write` handle a miss by first calling `line.writeBack()` when the outgoing line is valid and dirty, then calling `line.fill(paddr)`.
- `Line::writeBack()` computes the outgoing physical tag from the resident `tagKey` and calls `busWriteBurst<DCache>(tag | index, words)` for the complete line. It does not pass or filter by the dirty mask.
- `Line::fill()` clears `dirty`, replaces `tagKey`, and fills the same resident slot with `busReadBurst<DCache>`.

Thus the outgoing line exists only before the replacement fill retags/reuses the slot.

### `ares/n64/rdram/rdram.hpp`

For identity-mapped RDRAM, `Writable::writeBurst<DCache>` writes four 32-bit words at offsets `0x00`, `0x04`, `0x08`, and `0x0c`, then updates hidden RAM. The research callback is inserted only in a generated copy and fires after those completed backing updates. The exact pinned checkout remains clean.

The ordinary scalar RDRAM observer similarly fires after `Memory::Writable::write<Size>` and the hidden-RAM update for successful identity-mapped writes.

## Deterministic fixture

Durable experiment: `spikes/036-ares-dcache-eviction-lineage/`.

All bytes are synthetic. CPU and RSP recompilers are disabled. RDRAM is forced into the controlled identity mapping.

Physical cache lines:

- source `0x1000`: first word `0x11223344`;
- destination `0x2000`: `aabbccdd 01020304 11223344 55667788`;
- conflict `0x4000`: `cafebabe 0badf00d 89abcdef 13579bdf`.

Destination `0x2000` and conflict `0x4000` select the same D-cache slot in pinned ares because their KSEG0 virtual addresses differ by `0x2000`, preserving `(vaddr >> 4) & 0x1ff == 0`.

Guest sequence:

1. cached `LW` from source `0x1000`;
2. cached `SW` of that value to destination word 0;
3. uncached KSEG1-alias `SW 0xdeadbeef` to destination word 0;
4. uncached KSEG1-alias `SW 0xfeedface` to destination word 1;
5. cached `LW` from conflict `0x4000`, forcing the dirty destination victim to write back before the conflict line fills the same slot.

After step 2 the destination resident line is:

```text
11223344 01020304 11223344 55667788
```

and the dirty mask is only `0x000f`, representing bytes 0..3.

After steps 3 and 4 but before eviction, backing RDRAM is deliberately different in both a dirty and a nominally clean word:

```text
deadbeef feedface 11223344 55667788
```

The clean resident word at `0x2004` still contains its older fill-origin value `0x01020304` and has no dirty bit.

## Exact-reference result

Final executable-code workflow run: GitHub Actions `37850302734`, job `113561267987`, source commit `c7441f49160fe64cea83ed7cf36e37a07543880d`. The workflow checked out exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, syntax-checked the Python tools, executed the deterministic model, built the exact pinned ares headless oracle, and ran the baseline/instrumented comparisons.

Deterministic model report SHA-256:

```text
c86c0560a5509330befa3fd2317b5dd101c7009eb3b141b368add0a30dd25fb3
```

Exact-reference canonical evidence SHA-256:

```text
79d0b886342701801f6441516fe15189422d21811b681a7f86dfe7d1f13c2cd3
```

Observed relevant chronology:

| Ordinal | Event | Physical address | Payload / first four words |
| ---: | --- | ---: | --- |
| 2 | D-cache burst fill | `0x1000` | first word `11223344` |
| 3 | D-cache burst fill | `0x2000` | `aabbccdd 01020304 11223344 55667788` |
| 4 | uncached scalar write | `0x2000` | `deadbeef` |
| 5 | uncached scalar write | `0x2004` | `feedface` |
| 6 | D-cache burst writeback | `0x2000` | `11223344 01020304 11223344 55667788` |
| 7 | D-cache burst fill | `0x4000` | `cafebabe 0badf00d 89abcdef 13579bdf` |

Immediately before conflict eviction:

- outgoing resident tag key: `0x2001`;
- outgoing slot index: `0`;
- dirty mask: `0x000f`;
- outgoing resident words: `11223344 01020304 11223344 55667788`;
- backing words: `deadbeef feedface 11223344 55667788`.

Immediately after the conflict access:

- destination backing words: `11223344 01020304 11223344 55667788`;
- the clean backing word `feedface` was overwritten by the stale resident fill-origin word `01020304` even though its dirty lanes were clear;
- the same cache slot now contains the conflict line;
- incoming tag key: `0x4001`;
- incoming words: `cafebabe 0badf00d 89abcdef 13579bdf`;
- D-cache writeback count: `1`;
- D-cache miss count: `3`;
- exception code: `0`.

Final deterministic state hashes from the strengthened run:

```text
RAM     44be5934b4149a705622a1bfcae877d3ffc49a263ead1f4944cf283f219b1833
hidden  b47778a9069b98968e1023108ae4b23c36729e5de4c9a0228995019b75e0e1f6
D-cache 7e7c9b8b7b17541ab967cf2e5d7e1eb9f856a08069993f29e0f78a4e5cf49ece
```

The runner also requires, by assertion:

- unmodified-reference baseline == generated observer build with callbacks disabled == observer-enabled build for all recorded facts and final CPU/cache/RAM state;
- two observer-enabled traced executions are byte-identical;
- the completed RDRAM transaction chronology and payloads exactly match the expected sequence above.

The workflow completed successfully, so every assertion held.

## What was falsified

### Current backing is not outgoing origin

Before eviction, destination backing starts `deadbeef feedface`, while the outgoing cache line starts `11223344 01020304`. The completed writeback uses the resident line, not current backing.

Any witness that consults RAM at eviction time to reconstruct what the cache will write is unsound.

### Slot/index alone is not lineage identity

The outgoing destination and incoming conflict line both use slot index `0`. Their physical tag keys differ (`0x2001` versus `0x4001`), and after replacement the slot contains the conflict payload rather than the bytes that were just written back.

Any delayed join that observes the slot after fill can attribute the completed destination writeback to the wrong resident generation.

### Dirty mask is not the physical writeback span

The dirty mask is only `0x000f`, but pinned ares performs a 16-byte D-cache burst writeback. More strongly, word 1 at `0x2004` had no dirty bit yet the writeback changed backing from `feedface` to `01020304`.

Therefore a provenance or executable-mutation sensor that emits backing effects only for dirty lanes will miss real backing writes in this modeled behavior.

## Minimum lineage obligation for Plaid

For cached executable provenance in this scope, the safe identity is not merely `(physical address)` or `(cache slot)`. A future production implementation should retain at least:

1. cache engine and slot/index;
2. resident physical backing line/tag;
3. a residency generation/epoch that changes on fill, replacement, invalidation, reset/restore, or any operation that changes resident identity;
4. current per-byte resident values;
5. current per-byte origin witness/version, seeded from the completed fill transaction and replaced on successful cached stores/copies;
6. dirty mask as metadata about which lanes were locally stored, **not** as the backing write width;
7. the completed outgoing writeback transaction identity: ordinal/chronology, physical line base, full width, full payload, and requestor;
8. an atomic/synchronous join from the outgoing resident generation to that completed backing transaction before `fill()` destroys the old resident identity.

The per-byte requirement matters because this fixture's outgoing line is mixed-origin: bytes 0..3 derive from the earlier source load/cached store, while bytes 4..15 retain destination-fill origin. The full backing write transaction re-establishes all sixteen bytes from that mixed resident lineage.

Even if a backing byte happens to compare equal before and after the write, its provenance should not be reconstructed from equality alone. The completed transaction still sourced the written byte from the outgoing cache line.

## Consequence for executable mutation discovery

A dirty cache eviction is itself a backing-write source that can affect executable bytes outside the dirty mask when aliases or other agents have changed backing under a resident line. Thus Plaid cannot soundly build an executable-write census by expanding only the instruction's original cached-store byte lanes at eventual eviction.

For a completed dirty writeback in this scope, the backing transaction is full-line and its byte origins come from the outgoing resident generation. Any executable span overlapping that physical line must reason about the complete writeback payload/provenance, including nominally clean resident bytes.

This also reinforces the earlier CPU-copy result: cached provenance is a historical cache-line property, not a function of current RAM contents or register equality.

## Reproduction

From this research branch with `.refs/ares` exactly at the pinned revision:

```sh
python3 -m py_compile \
  spikes/036-ares-dcache-eviction-lineage/model.py \
  spikes/036-ares-dcache-eviction-lineage/run.py
python3 spikes/036-ares-dcache-eviction-lineage/model.py
python3 spikes/036-ares-dcache-eviction-lineage/run.py
```

Expected final runner line:

```text
PASS: dirty victim writes its full pre-replacement mixed-origin line, overwriting an externally changed clean lane, before the slot is reused
```

The branch-only workflow `.github/workflows/research-dcache-eviction-lineage.yml` reproduces the exact-pin build on GitHub Actions.

## Limitations / remaining unknowns

This result is intentionally bounded. It does **not** establish an N64-wide hardware invariant merely because pinned ares behaves this way.

Still outside this experiment:

- independent physical-hardware confirmation or a second cache-accurate oracle;
- nonidentity/remapped/degraded RDRAM behavior and failed burst writes;
- TLB aliases and reverse-endian modes;
- byte/half/dual/merge stores and LL/SC-specific lineage;
- guest `CACHE` variants beyond the earlier explicit-writeback research;
- reset, serialization/restore, and cache-error paths;
- I-cache interaction and self-modifying-code visibility after the D-cache backing write;
- RSP and other RCP/DMA writers;
- general cross-block value/dataflow needed to prove a copied byte's earlier source;
- production ProgramMap integration and exhaustive closed-world proof.

Those gaps should remain fail-closed rather than being filled with value equality or model confidence.

## Primary integration reproduction (2026-10-09)

Retained original fixture from `2f70161`. Primary WSL reproduction matches
model SHA-256
`c86c0560a5509330befa3fd2317b5dd101c7009eb3b141b368add0a30dd25fb3`
and actual canonical evidence SHA-256
`79d0b886342701801f6441516fe15189422d21811b681a7f86dfe7d1f13c2cd3`.
Uninstrumented/disabled/enabled reported state agrees and the enabled stream
repeats exactly. A dirty victim writes all 16 outgoing bytes before replacement,
including the clean resident lane changed externally in backing. This remains
bounded actual-reference evidence, not a generalized resident lineage verifier.
