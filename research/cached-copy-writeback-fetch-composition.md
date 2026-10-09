# Cached CPU copy -> D-cache writeback -> uncached executable fetch composition

Date: 2026-10-10

Result: **VALIDATED for the bounded composition contract below**

Integration recommendation: **ADOPT the evidence-shape invariant**, not this research branch wholesale. A future production certificate for a cached CPU copy that becomes executable backing must preserve the complete causal chain through register generation, versioned per-byte D-cache residency, the exact completed full-line writeback generation, and the exact later fetch backing read. Missing seams remain UNKNOWN/OPEN.

## Question

Plaid already had three independently validated exact-pinned-ares primitives:

1. a cached CPU load/store copy can preserve bytes in D-cache after source backing has changed, so current RAM/value equality cannot recover the copy's source;
2. an outgoing dirty D-cache resident generation can be joined to the exact later identity-RDRAM full-line writeback, including nominally clean lanes, before the same slot is retagged/reused;
3. a direct uncached identity-RDRAM instruction fetch can be joined to the exact successful ordinary backing read inside its fetch boundary.

The remaining uncertainty was whether those contracts can be composed into one defensible executable-byte ancestry proof without losing causal identity at the seams.

The bounded hypothesis was:

> A cached executable copy reaches a later uncached fetch only if the certificate carries the exact source read/register generation into the cached store, the outgoing D-cache resident identity and per-byte origins into the completed writeback, and the exact completed backing read into the fetch. Current backing bytes, dirty-mask width, cache-slot identity, or equal payloads are never substitutes for those generations.

This investigation deliberately attacks composition rather than re-testing the three underlying emulator primitives.

## Canonical base and exact prior receipts

Plaid base at claim time:

```text
211176e7a489fecf8331d02915ee982cd279cb62
```

Exact ares pin from `refs.lock.toml`:

```text
9408cb43d4948fc3ea6e152a307a34348df3fe04
```

The branch-only workflow independently fetches the prior branches and verifies the exact note blobs before executing the composition model.

### Cached CPU-copy input

Branch/head:

```text
research/cpu-copy-rdram-gpt56sol
9760f94fbfb9389b107ae58239db6817f8a7a964
```

Durable note/blob:

```text
research/ares-cpu-copy-provenance.md
dd525733e5c574d36dd5e52d5ef6b55bcaf03f5b
```

Recorded exact-pin run/artifact:

```text
Actions 37798119815
artifact 11559372938
```

The validated counterexample establishes that a cached source load may retain `0x11223344` after an uncached alias has changed source backing to `0x55667788`, and that the destination backing mutation occurs later through D-cache writeback rather than at the cached store itself.

### Dirty D-cache eviction input

Branch/head:

```text
research/dcache-eviction-lineage-gpt56sol
2f701615d77630f1b9407f2f1a2032894114a4e7
```

Executable semantic head:

```text
c7441f49160fe64cea83ed7cf36e37a07543880d
```

Durable note/blob:

```text
research/ares-dcache-eviction-lineage.md
3192ea9b1d89bc9579f8380f766cdfa0f73c5024
```

Recorded exact-reference receipt:

```text
Actions 37850302734
canonical evidence SHA-256 79d0b886342701801f6441516fe15189422d21811b681a7f86dfe7d1f13c2cd3
```

That experiment established an outgoing destination line:

```text
11223344 01020304 11223344 55667788
```

with dirty mask only `0x000f`, while backing had been poisoned to begin:

```text
deadbeef feedface ...
```

The actual eviction wrote the complete 16-byte resident line. In particular, the nominally clean word at `0x2004` overwrote backing `feedface` with resident/fill-origin `01020304`. The outgoing line used slot 0/tag `0x2001`; only after its writeback did the same slot become tag `0x4001` for the conflicting line.

### Direct uncached fetch input

Branch/head:

```text
research/ares-rdram-uncached-fetch-gpt56sol
77a268281fa330e6d117523c2e342abbdad7639e
```

Executable semantic head:

```text
08fc4f5a0f563e2501751d93e67ed9d9f6809a7b
```

Durable note/blob:

```text
research/rdram-uncached-fetch-provenance.md
633fff4c2711ae4d7f3bbaf1d1c23c854d6252f7
```

Recorded exact-reference receipt:

```text
Actions 37801666243
results SHA-256 9580733c7af1b3ced1f5c38594e2e6fd123f79ba85b900d8d2205dcb5dd9c684
```

That experiment established the fetch-side rule: for the bounded identity-RDRAM primitive, an uncached fetch needs exactly one qualifying successful four-byte backing read inside the explicit fetch boundary with matching post-endian physical address and value. Equal-valued traffic outside the boundary is not provenance.

## Executable composition model

Durable verifier:

```text
experiments/cached_copy_writeback_fetch.py
```

It tracks each backing/cache byte as:

```text
(value, causal-chain)
```

and separately tracks:

- cache slot;
- resident physical tag;
- residency generation;
- per-byte resident lineage;
- dirty mask;
- register generation and exact source physical address;
- completed writeback generation and full span;
- fetch begin/read/end context.

This is intentionally stricter than a payload-flow model. Equal values never merge generations.

### Canonical composed chronology

The model adds an equal-valued source decoy and then composes the validated seams:

1. fill equal-payload decoy line at `0x1100`;
2. fill real source line at `0x1000`;
3. cached load exact source `0x1000` into `t0`;
4. replace source backing through an alias with `0x55667788`;
5. fill destination line at `0x2000`;
6. cached-store the retained `t0=0x11223344` into destination word 0;
7. poison destination backing word 0 with `deadbeef`;
8. poison nominally clean destination backing word 1 with `feedface`;
9. evict/write back the complete outgoing 16-byte destination resident generation, dirty mask still only `0x000f`;
10. reuse the same cache slot for conflict tag `0x4001`;
11-13. uncached fetch destination word 0 through one exact backing read;
14-16. uncached fetch nominally clean word 1 through one exact backing read;
17. write the **same numeric word** `0x11223344` to destination word 0 as a new backing mutation generation;
18-20. uncached-fetch the same numeric word again through a new exact backing read.

The model's positive ancestry checks are deliberately stronger than value equality.

### Copied executable word

All four fetched bytes at destination word 0 must include this causal shape:

```text
initial source byte
  -> source D-cache fill generation
  -> exact t0 load/register generation
  -> destination cached-store generation
  -> outgoing destination resident generation
  -> completed full-line writeback generation
  -> exact fetch backing-read generation
```

The later source alias patch must **not** appear in this ancestry even though it changes current source backing before destination writeback.

### Nominally clean executable word

The fetch from destination word 1 must root in the older destination fill bytes, then the full-line writeback, then the exact fetch read. The `feedface` backing poison is overwritten by the clean resident bytes and must not remain in the ancestry merely because the dirty mask excludes that lane.

This directly composes the surprising but validated writeback-width result: dirty metadata is not the physical write span in the tested ares behavior.

### Same-value later mutation

After the writeback, the model performs a new backing write of the same numeric `0x11223344` value. The later fetch must root in that new writer generation. It is rejected if its ancestry is forged back to the older D-cache writeback simply because the bits match.

## Adversarial attempts to falsify the composition

The verifier mutates the canonical history/certificate and requires each forgery to fail closed.

| Adversary | Required rejection |
| --- | --- |
| equal-payload source at `0x1100` substituted for real load source | exact load source identity drift |
| dirty mask `0x000f` treated as a four-byte physical writeback | writeback must be full 16-byte resident line |
| conflicting tag reuses the slot before outgoing writeback | outgoing slot+tag resident identity no longer matches |
| completed writeback removed | later fetched backing does not contain certified resident output |
| exact backing read removed from a fetch | fetch lacks exactly one qualifying read |
| equal/nearby backing read attached to wrong address | fetch backing address mismatch |
| same-value post-writeback patch ignored and ancestry retained from old writeback | generation substitution rejected despite equal bits |

The current canonical report records all seven rejections.

## Reproducibility receipt

Branch-only workflow:

```text
.github/workflows/research-cached-copy-writeback-fetch.yml
```

First green semantic run:

```text
Actions run 38001891467
job 114061667032
head 6c008468d2d8b5cd9aee6dab8e7709e652406a54
```

The job:

1. fetches the exact three prior research branches;
2. verifies all three note blob IDs listed above;
3. verifies the exact ares pin in `refs.lock.toml`;
4. syntax-checks the composition verifier;
5. executes it twice;
6. requires byte-identical stdout;
7. requires the canonical report digest and PASS marker;
8. uploads the receipt.

Canonical composition report:

```text
REPORT_SHA256=6c74ec8c9340b0f0e1b8414c6206b1e374fb0de39639368e81c28c60e02606b8
```

Uploaded artifact:

```text
artifact 11649232291
ZIP SHA-256 1524dc1c369ab36e3842fbe1e503e0a0fe5e2f6932e7c761ef9c1b42701e242f
```

## What this composes and what it challenges

This result composes:

- cached CPU copy/source-residency evidence from `research/cpu-copy-rdram-gpt56sol`;
- per-byte outgoing D-cache resident -> completed full-line writeback evidence from `research/dcache-eviction-lineage-gpt56sol`;
- exact backing read -> uncached instruction fetch evidence from `research/ares-rdram-uncached-fetch-gpt56sol`.

It challenges four tempting shortcuts:

1. **Current RAM is not provenance.** Source backing may change after the cached load and before the destination writeback.
2. **Dirty lanes are not necessarily backing-write width.** A clean resident byte can still replace a newer backing byte during a full-line writeback in the validated pinned-ares behavior.
3. **Cache slot is not resident identity.** The same slot is reused under a different physical tag after writeback.
4. **Equal payload is not generation identity.** A same-value post-writeback patch becomes the causal origin for the next fetch.

## Minimum production evidence implied by this composition

For this class of cached-copy executable provenance, a production evidence model needs at least:

1. **Source read identity**: exact successful source operation/backing identity and ordered register definition generation.
2. **Register/dataflow identity**: the store must consume that exact register generation, not merely an equal value.
3. **D-cache resident identity**: cache engine, slot/index, physical tag/backing line, and a residency generation which changes on fill/replacement/invalidation/reset/restore-like identity changes.
4. **Per-byte resident lineage**: each byte retains its own value and origin generation. A line may contain copied bytes and untouched fill bytes simultaneously.
5. **Dirty mask as metadata only**: it describes local stored lanes but cannot be assumed to describe the completed backing-write width.
6. **Outgoing writeback identity**: exact chronology, resident generation, physical base/span, complete payload, and successful backing transaction, joined before slot reuse destroys the outgoing identity.
7. **Backing mutation generations**: later writes, including same-value writes, replace affected backing ancestry.
8. **Fetch context**: explicit fetch attempt/begin-end identity plus the exact successful backing read supplying that fetch.

No single hash or current-value comparison can replace those causal joins.

## Closed-world impact

This composition closes one **shape** of proof obligation, not a ROM scope.

For an executable word produced by a cached CPU copy and later fetched uncached from identity RDRAM, Plaid can only defend ultimate origin if every seam above is witnessed. If source dataflow, resident generation, per-byte lineage, completed writeback, later mutation history, or fetch backing read is missing, ultimate executable provenance is UNKNOWN and the relevant closed-world result must remain OPEN.

The complete backing mutation span matters for executable discovery: a dirty eviction can write executable bytes outside the instruction's original dirty lanes when resident clean bytes overwrite newer aliased backing state. A mutation census based only on dirty bytes would therefore be incomplete for the validated pinned-ares behavior.

## Scope and remaining gaps

This is an **evidence-composition validation**, not a new emulator/hardware semantics experiment. The exact semantic primitives were already executed independently against pinned ares; the 20-event chronology in this model is synthetic and deliberately combines those contracts with adversarial decoys. No claim is made that this exact combined chronology was run in one ares process.

Still open:

- one combined interpreted reference fixture exercising the complete chain end-to-end in a single run;
- TLB/remapped/degraded RDRAM and reverse-endian copy paths;
- cached **instruction** consumption and I-cache residency/staleness after backing writeback;
- byte/half/merge/64-bit/COP1/LLSC copy/store families in this exact composed path;
- arbitrary transforms, decompression and relocation;
- cross-block/general register dataflow and copy discovery completeness;
- reset/save/restore/debugger epoch interactions;
- RSP/RCP/DMA writers and aliases in the same lifetime;
- exhaustive executable mutation accounting and whole-ROM closure.

Those gaps remain separate obligations. This result must not be stretched into a claim that a value-equal writeback or final RAM snapshot establishes executable ancestry.

## Reproduction

On this branch:

```sh
python3 -m py_compile experiments/cached_copy_writeback_fetch.py
python3 experiments/cached_copy_writeback_fetch.py
```

Expected final lines:

```text
REPORT_SHA256=6c74ec8c9340b0f0e1b8414c6206b1e374fb0de39639368e81c28c60e02606b8
PASS: cached-copy lineage survives resident D-cache -> full-line writeback -> exact uncached fetch without value-equality shortcuts
```
