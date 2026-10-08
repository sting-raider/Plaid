# Instruction-cache reset and restore provenance boundary

2026-10-08. Plaid base `3cf45dc323cbcd9e6463ccc781d3de093a433097`; pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Result: **PARTIAL**.

## Falsifiable hypothesis

A reset ends all prior instruction-cache fill lineage, while a savestate restore can recreate valid resident cache bytes without any contemporaneous RDRAM read or cache-fill event. Consequently a post-restore fetch cannot inherit a pre-restore fill solely from slot/tag/index/payload equality.

## Exact upstream evidence

At the pinned revision, `CPU::InstructionCache::power(bool)` loops over all 512 I-cache lines, writes `tagKey = 0`, restores the fixed index and zeroes all eight words. `CPU::power(bool)` calls that routine directly. This is a destructive cache-state boundary and does not call `Line::fill()`.

`CPU::serialize(serializer&)` serializes every I-cache line's `tagKey`, `index`, and `words`. nall's serializer uses one function for writing and reading; the `serializer(const u8*, u32)` constructor enters read mode and the integral reader overwrites target fields from serialized bytes. A cache line is therefore restorable as resident state rather than reconstructed by a bus read.

For N64 full savestates, `System::unserialize()` validates the snapshot and, when the stored synchronize flag is true, calls `power(false)` before deserializing the entire system. The subsequent component order includes RDRAM and then CPU. Thus reset can clear the I-cache and the same restore operation can immediately install serialized valid tags/words, with no completed post-reset fill.

## Counterexample

Spike 018's executable contract model intentionally creates two historical fills with identical slot/tag/index/payload. A snapshot is taken after fill 1, then equal-payload fill 2 becomes the observer's latest fill. Reset clears the line. Restoring the snapshot recreates the fill-1 resident tuple but emits no fill. The tuple/payload matching rule used by the current research fill helper returns fill 2, a causally false association across the reset/restore boundary. Changing backing RAM afterward additionally demonstrates that current backing contents need not equal the restored resident word. A later reset forces fill 3 from the changed backing.

Local run in this session passed deterministically. Model SHA-256: `c5c3dd0dd41bcef6eea94d727236332d1824b60c1d82edaaae64621db8fbe83c`; captured result SHA-256: `3d0f32954a25ce5616f49ddf21967fc5dbce7168d53e6f5038af0d03954fdbe0`.

This disproves the candidate rule “same resident tuple as the latest observed fill implies that fill is the resident-byte origin” once reset/restore is admitted into the analysis chronology.

## Prepared independent reference check

`spikes/018-ares-cache-reset-restore/` contains a pinned ares headless fixture. It saves a synchronized full-system snapshot after fill 1, creates equal-payload fill 2, restores the snapshot (exercising `System::unserialize()`'s power-before-restore path), checks that no new completed fill occurred, and demonstrates that the un-reset external fill matcher identifies fill 2. It then mutates backing RAM, checks cached/uncached divergence, and exercises the exact `icache.power()` subroutine used by CPU reset before requiring fill 3. The runner also builds a no-observer baseline and compares full reported state against the traced run, with a repeated traced-run determinism check.

The current execution environment has no network access and no mounted `.refs/ares`, so that pinned full-reference harness was not executable here. Its source is durable and runnable by the primary checkout. No reference-execution result is claimed.

## Minimum provenance obligation

A future unified cache chronology should enforce all of the following:

1. `reset/cache_power`: invalidate every live fill-to-resident lineage, regardless of whether a later line has equal bytes.
2. `restore`: introduce an explicit state-restore event qualified by capture/snapshot identity. Restored cache lines must point to that restore provenance, not to a historical live fill event.
3. If restore provenance is unavailable, post-restore resident-byte origin stays unknown until a witnessed fill or another independently verified installation event replaces the line.
4. Exploration that forks from savestates needs a new chronology/event namespace or epoch. Event ordinals from the parent live run cannot be reused as causal predecessors merely because payloads compare equal.
5. Current RDRAM equality after a full restore is corroboration only. Full savestate restore also installs RDRAM bytes from the snapshot, so equality does not prove a post-restore backing transaction occurred.

These are analysis/provenance obligations. Emulator savestate restore is not an N64 guest-visible hardware event and must not be misrepresented as one; it matters because compiler-time exploration/instrumentation may use restore and then combine observations.

## What remains unknown

The exact prepared fixture still needs execution against pinned ares to confirm headless system serialization/deserialization, callback neutrality and deterministic checkpoints in this construction. Hardware reset varieties and emulator frontend reset scheduling are not covered. This result does not create a production executable generation, prove general cache lifetimes, or address DMA/copy/decompression lineage.

Integration recommendation: **PRIMARY-INTEGRATOR-REVIEW**. Adopt the fail-closed reset/restore boundary rule now; independently run the pinned spike before promoting the experimental event schema or any stronger ares behavioral claim.

## Primary-integrator reproduction

2026-10-08: the prepared pinned-reference fixture now passes in the primary
checkout on x64 WSL Ubuntu/G++ 15.2. Baseline, instrumented callbacks-disabled
and repeated callbacks-enabled executions agree on the complete reported
PC/s0/Count/exception/RAM/cache projection. Restore adds no completed fill; the
old external tuple matcher selects fill 2; cache power then forces fill 3.
Final PC=`ffffffff80000004`, s0=2, Count=100, exception=0, RAM word and resident
word=`24100002`. Full RAM/cache hashes are locked in the runner. This upgrades
the controlled restore/cache-power fixture to VALIDATED; NMI/system-reset variety,
full GPR/COP0/FPU state and general chronological coverage remain separate.
The earlier environment limitation above is the original worker's receipt.
