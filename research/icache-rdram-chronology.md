# I-cache/RDRAM chronology join

2026-10-08. Result: **PARTIAL**.

Plaid base `3cf45dc323cbcd9e6463ccc781d3de093a433097`; pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Question

Can Plaid turn the separately observed completed I-cache fill and successful identity-mapped RDRAM burst into a trustworthy bounded byte-origin witness, rather than merely noting that their addresses or payloads happen to agree?

The falsifiable hypothesis was: for the pinned controlled identity-mapped path, a fill can be causally paired with exactly one synchronous successful 32-byte I-cache RDRAM read, and a later cached fetch may inherit that origin only while the selected cache line's complete resident tuple remains the one produced by that witnessed fill.

## Pinned-source finding

The relevant call chain is synchronous: `InstructionCache::Line::fill` calls `CPU::busReadBurst<ICache>`; `Bus::readBurst` selects `VR4300_ICACHE`; `MI::readRdramBurst` delegates normal RDRAM to `RDRAM::Writable::readBurst`; the successful identity path fills the caller's eight-word buffer; control then returns to the fill routine. The existing spike-016 RDRAM observer is inserted only at the successful identity return path, while the spike-012 fill observer is inserted immediately after the `busReadBurst` call. In the interpreter, `fetch` completes before `instructionPrologue` exposes the fetched word to the debugger.

Thus a shared observer ordinal can establish an ordering witness without an extra guest read. It must not infer backing from the fill address or bytes alone: RDRAM register/freeze paths can complete the outer burst call without the identity-RDRAM callback, and nonidentity translation/degradation takes a separate path.

## Adversarial result

`spikes/018-ares-fill-rdram-chronology/chronology.py` implements only the proposed verifier rule, not an emulator. A fill receives a backing witness iff the immediately prior event is an eligible identity 32-byte I-cache RDRAM read at the exact computed burst address with the exact eight returned words. Resident lineage is then retained only while the cache slot still has the fill-derived tag and all eight words.

The model replay of the spike-015/016 fixture yields fetch-origin IDs `[1, none, 2, none, 3, 3, 4, 4, none]`. The two `none` cached cases are the deliberate store-tag counterexamples: resident bytes from one fill are retagged to another physical page without any new backing read. A miss invalidation preserves an unchanged resident witness; hit invalidation breaks it until refill. Explicit CACHE fill creates a new witnessed resident tuple. A later backing-memory mutation/writeback does not rewrite the historical origin of still-resident cache bytes. Uncached execution is outside this I-cache witness.

Ten deterministic tests also reject equal bytes from the wrong address, nonidentity reads, an intervening event, tag mutation without fill, reset/restore, payload mismatch, a fill with no eligible backing read, and wrong requestor/width. Local command:

`python3 spikes/018-ares-fill-rdram-chronology/test_chronology.py`

Result: 10/10 pass. Python byte-compilation passes. This is consistent with the earlier executed spike-016 fact that its four eligible RDRAM read payloads exactly equal its four fill payloads, while adding the missing fail-closed chronology semantics in a standalone verifier.

## Candidate integration rule

If the primary integrator runs the follow-up reference experiment, the safe research rule is:

1. Put one monotonic observer ordinal across backing transactions, fill completions, CACHE-operation completions, resets/restores and fetch observations.
2. Create an I-cache fill-origin witness only from the immediately nested/preceding eligible backing transaction, checking requestor, width, exact burst address and complete returned payload.
3. Associate the witness with the resident cache slot, fill-derived tag and all eight words. Do not use only cache slot, tag, current physical address or payload equality.
4. After a CACHE operation, retain the witness only when the complete post-operation resident tuple is unchanged, unless a nested fill has already installed a new witnessed tuple.
5. Treat backing writes/copies as changes to backing history, not retroactive changes to bytes already resident in I-cache. Their effect matters at a later refill or uncached fetch.
6. Clear/unknown lineage across reset/restore until those mechanisms have their own witness. Keep translated/degraded/failed RDRAM paths unknown until their actual backing policy is instrumented.
7. Keep uncached execution and non-RDRAM/SP/PIF/ROM fetch sources on separate provenance paths.

## Why not VALIDATED

This session could inspect the exact pinned source and execute the project-owned deterministic verifier, but the available runtime had no network checkout of the full pinned ares tree. I therefore did not build a fresh reference binary with a shared ordinal callback. Existing spikes 012-017 provide the underlying executed fill/CACHE/RDRAM facts and neutrality goldens, but they recorded those streams separately. Promoting this join to runtime fact before observing the shared chronology would be an unjustified upgrade from source reasoning plus compatible observations to measured causal identity.

## Remaining gap

A small disposable reference patch should add the shared ordinal and rerun the existing spike-015/016 fixture plus spike-017 failure/remap boundaries. It must preserve all prior CPU/COP0/timing/RAM/cache checkpoints and prove that unsupported paths create no witness. Even success would remain bounded: ordinary CPU/PI/SP copies, general executable stores, translated/degraded backing identity, reset/save-state restore, decompression/relocation, other devices and complete executable lifetimes remain separate obligations.

Recommendation: **PRIMARY-INTEGRATOR-REVIEW** for the next reference-execution spike; do not yet create production image generations or closure facts from this model.
