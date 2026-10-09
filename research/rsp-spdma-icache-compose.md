# RSP producer -> reverse SP DMA -> cached CPU fetch composition

Status: **VALIDATED for the bounded causal composition contract**, 2026-10-10. This is not a new hardware-timing claim or a new emulator primitive.

Canonical Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/rsp-spdma-icache-compose-gpt56sol`

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Primary exact-pin CI receipt: Actions run `38003940061`, job `114068295463`, **SUCCESS**, research head `7ff5a6f66a54936cc3c7ce551531cc77a39a1fc7`. Evidence artifact `rsp-spdma-icache-compose-evidence`, ID `11650840250`, ZIP SHA-256 `ed60b9cad4ef2a16fb622b2ddccaa2d8ffc66ad0b75820ab186971e39ffb01b6`.

## Question

Can independently established RSP writer provenance, reverse SP-DMA RDRAM effects, and I-cache resident provenance be composed into a defensible **cached** CPU instruction origin without substituting equal bytes, current RAM, a matching tag, or a matching historical line tuple for causal identity?

Two earlier results meet at this seam. `research/rsp-dmem-spdma-rdram-fetch.md` validated decoded RSP DMEM writer generations through reverse SP DMA into a later **uncached** CPU fetch. `research/icache-rdram-chronology.md` plus the later shared cache chronology established that an eligible identity-RDRAM fill captures backing into a distinct resident line, and later backing mutation does not retroactively rewrite those resident bytes.

## Result

The composition is sound only if at least four identities remain distinct:

1. per-byte source writer generation in RSP DMEM;
2. the reverse-SP-DMA RDRAM destination/storage generation;
3. the exact backing generations consumed by the I-cache fill; and
4. the resident-cache generation/lifetime selected by the fetch.

A single generic "code generation" or equal payload is insufficient. In particular:

- an equal RSP rewrite followed by equal reverse DMA changes current RDRAM generation but **does not** change an already-resident cache line;
- an equal CPU/RDRAM overwrite after fill likewise changes backing generation but not a stale resident hit;
- invalidation/refill switches lineage to whatever backing generation the new fill actually consumed;
- an equal overwrite **before** fill wins at that fill;
- restoration of an equal tag/data tuple without a witnessed fill cannot resurrect the historical fill identity and remains `UNKNOWN`.

## Evidence composed

The reverse-DMA side comes from exact-pin branch `research/rsp-dmem-spdma-rdram-fetch-gpt56sol`, whose primary executed receipt was Actions run `37916462499`. It measured decoded RSP primitive DMEM sinks, successful `SP_DMA` RDRAM effects, equal writer generations, partial-byte roots and later equal CPU overwrite behavior. Its uncached terminal fetch is not reused as cache evidence here.

The cache side comes from the previously executed fill/CACHE/RDRAM fixtures and shared chronology. Exact pinned ares routes cached interpreter fetches through `InstructionCache::fetch`; a miss calls `Line::fill`, and `Line::fill` synchronously calls `busReadBurst<ICache>` before the word is returned from resident storage. The burst requestor is `VR4300_ICACHE`, and MI delegates the normal range to RDRAM burst backing.

The new `source_guard.py` checks the exact ares revision plus those implementation seams. CI recorded these guarded SHA-256 values:

- `ares/n64/rsp/dma.cpp`: `b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6`
- `ares/n64/cpu/cpu.hpp`: `6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27`
- `ares/n64/cpu/memory.cpp`: `55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74`
- `ares/n64/memory/bus.hpp`: `1cbe65b06ab32c10134912b45b33100dfec4b1703104fadb304dcf03b343b295`
- `ares/n64/mi/bus.hpp`: `f59d20c5d7d8d0ef53032af320f1c96b9343971bb513668b749ca6cda8c4d372`

That source agreement is a reference-contract guard, not hardware truth.

## Deterministic composition fixture

`experiments/rsp-spdma-icache-compose/model.py` builds a 24-event history with separate byte storage generations, ultimate roots and cache resident generations. An independent strict replay checks each claimed generation rather than choosing an equal-valued predecessor.

The observed root transitions are:

- fetch 5: RSP writer generation 1;
- equal RSP generation 2 + reverse DMA replaces current RDRAM, but stale cached fetch 8 still roots in **RSP generation 1**;
- invalidation/refill makes fetch 11 root in **RSP generation 2**;
- equal CPU RDRAM overwrite after that fill leaves stale fetch 13 rooted in **RSP generation 2**;
- refill makes fetch 16 root in the CPU writer;
- RSP generation 3 + reverse DMA followed by an equal CPU overwrite **before** fill makes fetch 22 root in that CPU writer;
- restore of an identical cache tuple without a causal fill witness makes fetch 24 `UNKNOWN`.

Two deliberately unsound policies are therefore falsified by the same history. Attributing a cached hit from **current RDRAM** is wrong at fetches 8, 13 and 24. Attributing a restored tuple from the latest historical fill with equal tag/data incorrectly produces the old CPU root at fetch 24 instead of `UNKNOWN`.

## Adversarial replay

The strict verifier rejects all seven tested corruptions:

- older equal RSP generation substituted into the later DMA;
- older equal RDRAM generation substituted into the later fill;
- later equal DMA sink deleted;
- equal backing overwrite inserted before fill while obsolete fill claims are retained;
- fill moved to the wrong physical line;
- resident generation forged on a hit;
- duplicate event ordinal.

These attacks are aimed at causal generation identity and ordering, not merely payload correctness.

## Reproducibility

The exact-pin CI checkout, source guard, Python byte-compilation, two independent model executions, byte-for-byte `cmp`, and artifact upload all passed.

- model stdout SHA-256: `0e44da1f703fff536c3bb4e593bfe8b654d5eb96afdff61d0a33d77811f70c6d`
- canonical trace SHA-256: `6a9e0bea95160957ff404b1fabaec599c90399778068134ae57a1ed59d29435d`
- internal report-payload SHA-256: `82a5137174bef25a914010c8e3d4cdca4be5f5871f2fb47c1b894e37d0027b1a`

Reproduce with:

```bash
python3 -m py_compile \
  experiments/rsp-spdma-icache-compose/model.py \
  experiments/rsp-spdma-icache-compose/source_guard.py
python3 experiments/rsp-spdma-icache-compose/source_guard.py --ares .refs/ares
python3 experiments/rsp-spdma-icache-compose/model.py > /tmp/rsp-cache-1.json
python3 experiments/rsp-spdma-icache-compose/model.py > /tmp/rsp-cache-2.json
cmp /tmp/rsp-cache-1.json /tmp/rsp-cache-2.json
sha256sum /tmp/rsp-cache-1.json
```

## Closed-world impact

This removes one higher-order uncertainty: Plaid can compose an already-known RSP producer through reverse SP DMA into a **cacheable** CPU fetch, but only by preserving source writer, destination storage, fill and resident generations separately or with an equivalent causal representation. Current RAM, PC/physical address, tag equality, payload equality, or an equal historical line tuple cannot substitute for those identities.

This matters directly to a future CLOSED certificate. A solver that re-attributes cached execution from current RDRAM silently assigns the wrong producer after equal reloads/writes. A solver that matches historical cache tuples can resurrect dead provenance after restore. Both policies are concrete false-proof patterns now covered by executable deterministic counterexamples.

## Remaining gaps / non-claims

This does **not** prove new emulator/hardware timing, arbitrary SP-DMA count/skip/wrap/overlap, TLB/translated/degraded backing, D-cache-delayed writeback combinations, actual save-state restoration provenance, RSP IMEM reverse-DMA sources, complete mutation sensing, exception roots, executable-lifetime completeness, or whole-ROM closure.

Production recommendation: adopt the identity-separation/replay invariant and bind it to Plaid's ordered backing/cache history. Do not promote this standalone model wholesale into ProgramMap.
