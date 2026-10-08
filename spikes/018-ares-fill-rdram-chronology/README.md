# Spike 018: I-cache fill / RDRAM chronology join

Result: **PARTIAL**

Plaid base: `3cf45dc323cbcd9e6463ccc781d3de093a433097`

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

## Hypothesis

For the pinned ares controlled identity-mapped RDRAM scope, a completed instruction-cache fill can receive a bounded byte-origin witness only when one successful 32-byte `VR4300_ICACHE` RDRAM read is causally nested immediately before that fill and has the exact expected burst address and returned eight words. A later cached fetch may inherit that witness only while the selected resident cache tuple still has the witnessed tag and eight words.

The adversarial alternative is that matching bytes, a matching cache slot, the current physical address, or the most recent fill are sufficient by themselves. They are not.

## Exact source path

At the pinned ares revision:

1. `ares/n64/cpu/cpu.hpp`, `CPU::InstructionCache::Line::fill` sets the tag/valid state and synchronously calls `cpu.busReadBurst<ICache>(tag | index, words)`.
2. `ares/n64/cpu/memory.cpp`, `CPU::busReadBurst` synchronously delegates to `Bus::readBurst`.
3. `ares/n64/memory/bus.hpp`, `Bus::readBurst<ICache>` routes RDRAM addresses to `MI::readRdramBurst` with requestor `VR4300_ICACHE`.
4. `ares/n64/mi/bus.hpp`, `MI::readRdramBurst` routes normal RDRAM to `rdram.ram.readBurst`.
5. `ares/n64/rdram/rdram.hpp`, the successful identity path writes the eight returned words into the same caller buffer. Nonidentity translation/degradation and failed/out-of-bounds paths return through different branches.
6. Plaid spike 016's generated research observer is at the successful identity-RDRAM return point. Spike 012's fill observer is immediately after the `busReadBurst` call. Therefore, for that instrumentation scope, a successful identity backing callback occurs synchronously before the corresponding fill callback.
7. `ares/n64/cpu/cpu.cpp`, the interpreter calls `fetch(access)` before `instructionPrologue`, so the existing debugger fetch observation occurs after any miss refill has completed.

This source ordering is stronger than payload equality, but this spike does not claim a new runtime observation of a shared ordinal. The existing spike 016 independently established four identity-mapped RDRAM reads whose complete payloads equal the four fill payloads in the spike-015 fixture.

## Join rule tested here

`chronology.py` is a project-owned fail-closed verifier model. It assigns a fill witness only when the immediately preceding observed event is:

- an identity-mapped RDRAM read;
- requested by I-cache;
- exactly 32 bytes / eight words;
- at `(fill.physical & ~0xfff) | fill.index`; and
- byte-for-byte equal to the completed fill payload.

The live resident witness is keyed by cache slot plus the exact fill-derived tag and all eight resident words. A cached fetch inherits the witness only if tag, physical page, resident words, selected lane and fetched word all agree.

A CACHE operation preserves an existing witness only when its post-operation resident tuple is unchanged. This is deliberate: store-tag and invalidation can change tag/valid state without reading backing memory; explicit CACHE fill creates a new nested fill witness before the operation-completion callback. Reset/restore clears all resident lineage unless a separate restore witness is supplied. A backing RDRAM write does **not** retroactively change the origin of bytes already resident in I-cache.

## Controlled sequence

The model replays the relevant spike-015/016 sequence:

- miss page `0x0000` -> RDRAM read -> fill 1 -> known fetch;
- CACHE store-tag retags fill-1 bytes as page `0x4000` -> fetch is **unknown**, despite matching slot/resident bytes;
- invalidate -> real page-`0x4000` read/fill 2 -> known fetch;
- CACHE store-tag retags fill-2 bytes as page `0x0000` -> fetch is **unknown**;
- hit invalidate -> real page-`0x0000` read/fill 3 -> known fetch;
- miss invalidate leaves fill 3 resident -> known fetch remains fill 3;
- explicit CACHE fill page `0x4000` -> read/fill 4 -> known fetch;
- backing RAM mutates while the cache remains unchanged, then hit writeback restores backing -> cached fetch remains fill 4;
- uncached fetch has no I-cache-fill origin.

Expected cached/uncached fetch origin IDs are:

`[1, null, 2, null, 3, 3, 4, 4, null]`

For the synthetic unified chronology the successful read/fill ordinal pairs are:

`(1,2), (7,8), (13,14), (18,19)`.

These ordinals are model ordinals, not a claim about prior raw ares trace numbering.

## Adversarial tests

Run:

```sh
python3 spikes/018-ares-fill-rdram-chronology/test_chronology.py
```

The ten deterministic tests cover:

- the complete controlled stale-tag/invalidation/fill/writeback sequence;
- a completed fill with no eligible backing-read witness;
- equal payload from the wrong backing address;
- byte-equal nonidentity RDRAM reads;
- an intervening observed event between read and fill;
- tag mutation without a fill;
- backing write while resident bytes remain unchanged;
- reset/restore;
- read/fill payload mismatch; and
- wrong requestor or burst width.

Local result on 2026-10-08: **10/10 pass**. `python3 -m py_compile chronology.py test_chronology.py` also passes.

SHA-256:

- `chronology.py`: `67e324b5bbce2b963c4cb9fefdc10117b6640c8557878a3fc229c93f26f16f57`
- `test_chronology.py`: `5e6d42c84416e357f19e1790f3e5624fb192a8cf1305904d3fc621c983fb7a7b`

## Conclusion

**PARTIAL.** The pinned source and already-validated spike-016 observations support a precise causal join design for successful identity-mapped RDRAM fills, and the fail-closed model rejects the important stale-tag/equal-byte counterexamples. However, this session did not compile and execute a new pinned ares binary carrying one shared monotonic ordinal across RDRAM-read, fill, CACHE-operation and fetch callbacks. The runtime chronology itself therefore remains to be independently measured before production adoption.

## Required next experiment

Extend the disposable ares observer only, not Plaid production code, with one shared monotonic event ordinal. Re-run the spike-015/016 fixture and require every witnessed fill to have the exact runtime sequence `eligible RDRAM read -> fill`, with later fetch association governed by the post-CACHE resident tuple. Compare the complete CPU/COP0/timing/RAM/cache state and the prior projection hashes against the existing goldens. Also include the spike-017 remap/degradation/failure cases and assert they never receive an identity backing witness.

This still would not prove general executable lifetimes, ordinary CPU stores/copies, PI/SP/PIF provenance, translated RDRAM origin, reset/restore semantics, or whole-ROM closure.
