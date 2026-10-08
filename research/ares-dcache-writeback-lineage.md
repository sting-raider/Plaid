# ares D-cache store-to-writeback lineage

2026-10-09. Status: **PARTIAL (experiment in progress)**.

## Bounded hypothesis

For exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, a controlled identity-mapped cached VR4300 store can be joined to a later successful RDRAM burst write only through the same resident D-cache line generation. Explicit `CACHE 0x19` hit writeback and dirty same-index replacement should preserve that chain. Clean replacement and dirty `CACHE 0x11` invalidation must not manufacture a backing mutation merely because address or payload values match.

## Exact pinned source map

`ares/n64/cpu/dcache.cpp` selects a line with `lines[vaddr >> 4 & 0x1ff]`. On a read/write miss it writes back only when the old line is both valid and dirty, then fills the new tag. `Line::fill` clears dirty state, performs `busReadBurst<DCache>`, and installs validity from that result. `Line::write<Size>` changes resident bytes and records a byte dirty mask. `Line::writeBack` sends the complete resident 16-byte line through `busWriteBurst<DCache>`; it does not itself clear dirty state.

`ares/n64/cpu/interpreter-ipu.cpp` `CACHE 0x19` invokes `line.writeBack()` for a matching dirty line and then clears `line.dirty`. In contrast, `CACHE 0x11` simply clears validity on a matching line. A dirty cached mutation can therefore be discarded without ever becoming an RDRAM write.

`ares/n64/rdram/rdram.hpp` successful identity burst reads materialize the backing words used by a D-cache fill; successful burst writes store all four D-cache words and update hidden RAM. The research sensor samples only after those controlled successful identity-path effects.

## Experiment

`spikes/034-ares-dcache-writeback-lineage/` adds generated, layout-neutral observers for successful fills, resident stores, writeback entry/exit, invalidation, and actual RDRAM bursts. One shared monotonic ordinal permits the verifier to require the actual RDRAM write to be nested between the exact line's writeback entry/exit. Baseline, observer-disabled, observer-enabled and repeated observer-enabled executions are compared for neutrality.

The four guest phases are explicit hit writeback, dirty same-index eviction, clean same-index replacement with equal backing payloads, and dirty hit-invalidate/drop followed by replacement.

The independent deterministic model currently passes 3,000 histories x 120 actions. It records 1,546 legitimate certificates and rejects 50,062 forged/unjoined writes. Canonical model report SHA-256: `c3d3e0894be61574d865ec2330056dc099e4dd4cce91b0f0282e1fa605dbf002`.

## Current limitation

The actual pinned-reference build/execution and neutrality comparison are not yet recorded in this note. Until that succeeds, the source/model result is not promoted beyond PARTIAL. This study also intentionally excludes arbitrary TLB/cacheability histories, other store widths/families, reset/save-state epochs, external DMA coherence, non-identity RDRAM and global executable-universe closure.

## Primary integration completion (2026-10-09)

The worker closeout above was PARTIAL. Retained original fixture from `674109b`;
its last model commit adds mutation revisions after the older receipt. The current
model repeats 3,000 x 120 histories with 1,179 certificates and 50,206 rejected
forgeries, SHA-256
`02bbfbfd58817fcdd10d21523018be2b69dba1cf8b2e2b9c9c6afcc4dd98a9eb`.
This supersedes the earlier model numbers for the current revision.

Primary actual-reference execution now passes all four phases, original/disabled/
enabled reported-state equality and exact repeated output. Actual trace SHA-256:
`e0cf9f8332b72377c20f665d89f640b80406ea358de7ecbf68de4b6936329192`.
Current result including local recipe/source hashes:
`8e4845630414a9ec99904fca5834ea0eab9162f67322c0598428473c74623034`.
Explicit writeback and dirty eviction export exactly two resident-generation
lineage certificates; clean replacement and dirty invalidate export none.

The primary also added mutation revisions to the measured-trace reducer, fixing
its same-value intervening-store acceptance. Six adversarial measured histories
now reject stale revisions, wrong address/width/phase/value and duplicate global
ordinals. The positive measured history still passes. Exact nested full-line
backing transaction, generation, revision and single consumption are required.
Generated reference shadows/build caches are retained rather than recursively
removed. **VALIDATED** now applies to this bounded primary fixture only; arbitrary
stores, unseen epochs, all source classes and production integration remain open.
