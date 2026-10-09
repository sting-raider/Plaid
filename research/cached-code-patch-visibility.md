# Cached CPU code-patch visibility across D-cache and I-cache

Date: 2026-10-09

Result: **VALIDATED** for the bounded exact-pinned-ares cached KSEG0 / identity-RDRAM fixture below.

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Branch: `research/cached-code-patch-visibility-sol`

Durable artifacts:

- `experiments/cached_code_patch_visibility.py`
- `spikes/043-ares-cached-code-patch-visibility/driver.cpp`
- `spikes/043-ares-cached-code-patch-visibility/run.py`
- branch-only workflow `.github/workflows/research-cached-code-patch-visibility.yml`

## Question

When the CPU patches executable bytes through a cacheable address, what is the
minimum causal history required before Plaid may say that a later cached
instruction fetch sees the patch?

The dangerous shortcuts were:

1. `cached store completed => patched code is fetch-visible`;
2. `D-cache writeback completed => patched code is fetch-visible`;
3. `an I-cache invalidate/refill happened sometime => the patch is visible`;
4. matching old/new instruction payloads are enough to infer which mutation a
   fetch came from.

The hypothesis was that all four are unsound. A cached fetch must remain bound to
its actual resident I-cache generation. For this bounded path the positive chain
is:

```text
cached CPU store
-> D-cache resident generation/revision
-> completed D-cache writeback
-> new backing generation
-> later I-cache backing read/fill from that generation
-> I-cache resident generation
-> cached instruction fetch from that resident generation
```

An invalidate is one way to force the later fill; an explicit I-cache fill can
also replace residency. The causal fill after the relevant backing generation is
the important fact, not the mere existence of an invalidate opcode.

## Exact pinned source basis

The exact pinned ares files were source-guarded by Git object hash before the
fixture built:

| File | Git blob | Relevant behavior |
| --- | --- | --- |
| `ares/n64/cpu/memory.cpp` | `f362ef67ab41ccf57330bbedd6f614e07a61dd17` | cacheable CPU writes route to `dcache.write`; cacheable instruction fetches route independently to `icache.fetch` |
| `ares/n64/cpu/dcache.cpp` | `4de28e0ad9566d31f47210a997c22fa994785d26` | cached stores mutate resident D-cache bytes/dirty state; writeback emits resident words to the bus |
| `ares/n64/cpu/cpu.hpp` | `b51000d99e1e8818ad04a8c747a8170b0e98fae8` | a valid I-cache hit returns resident words without rereading backing; a miss fills from `busReadBurst<ICache>` |
| `ares/n64/cpu/interpreter-ipu.cpp` | `938ccbd0af1f127439d9859c1fd6be2bbd5222a3` | guest CACHE `0x19` performs D-cache hit writeback; CACHE `0x10` performs I-cache hit invalidate |
| `ares/n64/rdram/rdram.hpp` | `c718ec2e9b2a78610353562cbc81dd973b278ee2` | identity-RDRAM burst writes update backing words and burst reads return backing words |

The headless builder checks that `.refs/ares` is exactly the pinned revision and
clean before compiling. No CPU/cache/RDRAM instrumentation is used by this
fixture. The standard project headless build only generates the existing Vulkan
UI guard required by the oracle harness; the cache and RDRAM files above remain
exact pinned sources.

## Executed reference fixture

`spikes/043-ares-cached-code-patch-visibility/driver.cpp` uses only synthetic
words. Recompilers are disabled and RDRAM is forced into the controlled identity
mapping used by prior cache research.

Physical target `0x2000` initially contains:

```text
0x24020001   ADDIU v0,zero,1
```

Physical helper code at `0x3000` is deliberately at a different I-cache index and
contains:

```text
0xae080000   SW    t0,0(s0)
0xbe190000   CACHE 0x19,0(s0)   # D-cache hit write back
0xbe100000   CACHE 0x10,0(s0)   # I-cache hit invalidate
```

`t0` holds the replacement instruction:

```text
0x24020002   ADDIU v0,zero,2
```

The fixture performs these checkpoints:

1. execute the target once, filling I-cache with the old instruction; `v0 = 1`;
2. execute the cacheable `SW` patch; D-cache now contains the new instruction and
   is dirty, while RDRAM and the already resident I-cache line remain old;
3. execute the target again; `v0 = 1`;
4. execute guest D-cache hit writeback; RDRAM now contains the new instruction,
   while the valid I-cache line still contains the old instruction;
5. execute the target again; `v0 = 1`;
6. execute guest I-cache hit invalidate;
7. execute the target again; the miss/refill reads new backing and `v0 = 2`.

GitHub Actions run `37915456717`, job `113770409601`, checked out exact ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, passed all source guards, compiled
the exact-reference headless oracle, and completed the fixture successfully.
`run.py` executes the oracle twice and requires byte-identical stdout.

Canonical executed evidence:

```text
EVIDENCE_SHA256=82b49fedf25c18e8fdae926557f6812f6a7b8f0d965c6270da6a43d083376ec7
EVIDENCE_JSON={"after_refill_fetch":2,"after_store_fetch":1,"after_writeback_fetch":1,"backing_word":604110850,"dcache_dirty":0,"dcache_hits":0,"dcache_misses":1,"dcache_word":604110850,"dcache_writebacks":1,"exception":0,"icache_hits":4,"icache_misses":3,"icache_word":604110850}
```

`604110850 == 0x24020002`. Thus the final backing, D-cache word and refilled
I-cache word are all the new instruction. The two earlier fetch checkpoints still
execute the old instruction, including the fetch *after* completed D-cache
writeback.

This directly rejects both `store => visible` and `writeback => visible` for the
bounded pinned-reference path.

## Adversarial provenance reducer

`experiments/cached_code_patch_visibility.py` is deliberately not an emulator. It
is a finite history generator plus an independent replay verifier for the source-
established contracts above.

Seven deterministic histories cover:

- cached store with stale I-cache;
- completed D-cache writeback with stale I-cache;
- writeback followed by invalidate/refill and a visible patch;
- invalidate/refill **before** writeback, followed by writeback while the newly
  filled I-cache line remains stale;
- a partial two-byte patch with mixed per-byte origin;
- a same-value patch whose payload does not reveal the new provenance revision;
- an equal-payload mutation in another word that must not steal origin.

Six measured-history forgeries are rejected by independent replay: wrong fetch
resident generation, wrong D-cache revision, forged fill payload, same-value
origin theft, whole-word origin theft from a partial patch, and stale backing
generation on a fill read.

The workflow runs the reducer twice. Both reports are byte-identical:

```text
{"event_counts":{"equal_payload_decoy":11,"partial_patch":12,"refill_before_writeback_stays_stale":12,"same_value_patch":12,"store_not_visible":6,"writeback_still_stale":8,"writeback_then_refill_visible":11},"forgery_rejections":6,"result":"PASS","sha256":"f03685aaf4ca8df04e69462c94c854c9a433e11670e8156a528c4c1452614cde"}
```

The exact locally tested reducer file had SHA-256
`6877d5ea16c1fa2d887fca366c0c4353f801f1ef629e4c57325c7dfd6def0efe`
and Git blob `5077717bb1bf6884b12f5378045009824b5acc7c`; the committed blob matches.

The pre-writeback-refill case is the important adversarial ordering result. An
invalidate is not itself a patch-visibility witness. If the refill happens while
backing is still old, a later D-cache writeback changes backing but does not
retroactively change that valid resident I-cache line.

## Corroborating pinned system-test source

The separately pinned `n64-systemtest` revision
`196f5421173220eb2f63a7a99c64795dc0ea0698` contains
`IcacheUncachedPatchStallsUntilInvalidate` in
`src/tests/cop0/icache_functional.rs`. That test intentionally executes an
I-cache-resident instruction, patches backing through an uncached alias, expects
the old instruction until `ICACHE_HIT_INVALIDATE`, and expects the new one after
the following fetch.

This is useful independent test intent, but this worker did **not** execute that
suite on physical hardware. It is corroborating source evidence, not a hardware
truth claim.

## Plaid consequence

Executable mutation and executable visibility need separate states.

For a cached CPU patch, the mutation census should record the successful D-cache
resident mutation immediately. That event proves the CPU changed a cache-resident
byte generation; it does **not** prove either backing RDRAM or instruction fetch
visibility changed.

A later completed D-cache writeback can establish a new backing-byte generation
and export exact resident byte origins. It still does **not** replace a valid
older I-cache resident generation.

For each cached instruction fetch, provenance should therefore be attached to the
actual I-cache resident generation used by that fetch. Promoting a cached patch
into that generation requires an actual later fill/backing-read witness whose
causal backing state already contains the patch. Payload equality cannot replace
that chain, including for same-value writes.

A production certificate should retain at least:

1. physical backing identity and backing generation/revision;
2. D-cache slot/tag plus resident generation and per-byte mutation revision;
3. completed D-cache writeback identity and exported per-byte origins;
4. I-cache slot/tag plus resident generation and per-byte fill origin;
5. actual cache lifecycle events that replace/invalidate/refill resident identity;
6. fetch-to-resident-generation identity;
7. ordered chronology sufficient to prove that the eligible I-cache fill read the
   post-writeback backing generation rather than an earlier one.

This composes the existing D-cache writeback-lineage and I-cache fill-lineage
research into one executed self-modifying-code visibility counterexample.

## Reproduction

With `.refs/ares` at the exact pinned revision:

```sh
python3 -m py_compile \
  experiments/cached_code_patch_visibility.py \
  spikes/043-ares-cached-code-patch-visibility/run.py
python3 experiments/cached_code_patch_visibility.py
python3 experiments/cached_code_patch_visibility.py
python3 spikes/043-ares-cached-code-patch-visibility/run.py
```

The branch-only workflow reproduces the same commands from a fresh exact ares
checkout.

## Limitations / what this does not prove

This result is intentionally bounded and must not be inflated into a closed-world
claim.

It does **not** establish:

- a physical N64-wide invariant merely because pinned ares behaves this way;
- hardware execution of the corroborating n64-systemtest case;
- translated/TLB, reverse-endian, degraded/nonidentity-RDRAM or alias behavior;
- all CPU mutation opcodes or partial-store variants in one exact-reference
  visibility fixture;
- COP1/LL/SC-specific patch paths;
- all guest CACHE variants, index/tag manipulation, reset, NMI or save-state
  restore composition;
- DMA/RSP/PI/SP writers racing either cache;
- decompression, relocation or general overlay lifetime closure;
- an exhaustive executable mutation census or whole-ROM closed-world proof.

The exact fixture also uses one aligned word patch and an explicit D-cache hit
writeback followed later by I-cache hit invalidation. Explicit I-cache fill after
writeback should be treated as another resident-generation transition, not as a
reason to hard-code `invalidate` as the only legal positive path.

## Recommendation

**ADOPT** the bounded invariant: cached executable mutation, backing mutation and
cached instruction-fetch visibility are three distinct provenance transitions.
Do not mark patched code fetch-visible at cached-store time or D-cache-writeback
time. Bind each fetch to the actual resident I-cache generation and require a
causal post-mutation backing-to-fill chain before attributing that resident
instruction byte to the patch.
