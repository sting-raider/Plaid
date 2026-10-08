# Cache-operation outcomes in controlled RAM

2026-10-08. Hypothesis: the completed-operation sensor can preserve hit/miss
invalidation, explicit fill and hit/miss writeback outcomes without new guest
accesses or clocks. Spike 015 extends the tag-store counterexample with original
guest CACHE instructions, retaining the baseline without fill/operation hooks.

Seventeen fetched instructions contain eight cache operations. Hit invalidation
clears validity and the next fetch refills; miss invalidation leaves the selected
line valid. Explicit fill replaces data from another physical page. A host fixture
write changes RAM word 9 to 8 while the resident cache retains 9. Guest CACHE hit
writeback restores RAM, checked by subsequent uncached instruction fetch of word
9. Miss writeback does not alter RAM, checked by the complete RAM golden. Four
completed fills occur; profile counts are hits=5, misses=4 and writebacks=1.
Count=257, s0=9 and the final PC is uncached 0xffffffffa0004004.

Baseline/plain/traced/repeated complete CPU/COP0/timing/RAM/cache checkpoints
agree; JSON repeats exactly. All GPR/HI/LO/PC, exception/status/configuration,
post-step tags/fill counts and before/after operation data pass. RAM SHA-256:
`50a18fe00c8412198450b7c3b145685651d375984164e4e87ec60f4c050fa4bd`.
Cache SHA-256:
`c6caf1bddc422cd59faa433446a3d02649b05dd2fba13bc54539e6a3c11f28a6`.
The earlier three-operation spike retains its complete prior JSON projection.

Host setup supplies PCs, TagLo/target registers and the deliberate RAM mutation;
guest opcodes perform all cache operations. Both recompilers are disabled. This
proves outcomes for identity-mapped controlled RAM only. A completed operation or
writeback counter is no general backing/write-success certificate. Actual bus
transactions, mapping/degradation/failure policies, reset/restores and a unified
fill/mutation/fetch/copy history still need witnesses. No production image,
generation, lifecycle or native artifact is promoted.
