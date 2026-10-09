# SP DMEM -> RDRAM DMA egress provenance

Status: experiment prepared; exact-pin execution is performed by the branch-only workflow.

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.
Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Question

Can a successful SP write-DMA RDRAM storage effect inherit current DMEM writer ancestry from an exact measured DMEM read/lane, while rejecting equal-payload and descriptor-proximity shortcuts?

## Source basis

Pinned ares `ares/n64/rsp/dma.cpp` performs two DMEM Word reads before the corresponding two identity-RDRAM Word writes. That ordering makes an equal-payload nearest-read rule directly falsifiable: for two equal DMEM Words, the second read is closer to the first sink even though the first sink came from the first source lane.

The observer records, on one monotonic research ordinal:

1. normalized CPU-visible DMEM Word storage effects;
2. one explicit measured foreign DMEM same-value effect used as a fail-closed counterexample;
3. the actual two DMEM Word reads inside write-DMA with both DMEM and DRAM lane addresses;
4. only successful RDRAM writes after mapping/bounds checks and backing/hidden updates.

No callback performs guest accesses, clocks, reset/serialization or reference-state mutation.

## Fixture

The standalone fixture covers equal-valued source Words, byte-identical reloads, count/skip destination gaps, modulo-DMEM wrap, same-value CPU replacement, a measured foreign same-value mutation and an OOB RDRAM destination. The verifier replays per-byte writer generations and requires a unique exact source-read lane for each successful sink.

Six adversarial histories target wrong equal-payload lane selection, missing source reads, skip-gap fabrication, deletion of a same-value CPU generation, deletion of the foreign same-value cut and non-monotonic ordinals.

## Limits

This experiment is bounded to controlled identity-mapped pinned-ares component execution. It is not hardware atomicity/timing evidence; it does not cover translated/degraded RDRAM, all RSP producers, complete mutation sensing, save/reset/restore, DMEM executable lifetimes, scheduler contention or whole-ROM closure. The foreign mutation is deliberately measured at the fixture effect boundary; this does not claim a production-complete foreign-sink sensor.
