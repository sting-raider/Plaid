# Cache-operation hit and miss outcomes

Hypothesis: completed CACHE-operation snapshots preserve hit/miss distinctions,
explicit fills and writebacks without adding guest accesses or clocks. Extend
the measured tag fixture with original hit-invalidate, fill and writeback opcodes.

Run `python spikes/015-ares-cache-outcomes/run.py`.

## Verdict: VALIDATED for identity-mapped controlled RAM

### Evidence

Seventeen fetched guest instructions, eight completed cache operations, four
fills and one writeback pass. Hit invalidation forces a refill; miss invalidation
preserves the line. Explicit fill replaces resident words. After host RAM changes
to word 8 while the cache holds word 9, guest writeback restores RAM; a later
uncached fetch observes word 9. Miss writeback leaves RAM unchanged. A separate
baseline without fill/operation hooks matches instrumented plain/traced/repeated
complete checkpoints. JSON repeats exactly. Count=257, hits=5, misses=4 and s0=9.
RAM SHA-256: `50a18fe00c8412198450b7c3b145685651d375984164e4e87ec60f4c050fa4bd`.
Cache SHA-256: `c6caf1bddc422cd59faa433446a3d02649b05dd2fba13bc54539e6a3c11f28a6`.
The earlier three-operation spike still retains its complete projection golden.

### Constraints and surprises

Host setup supplies fixed PCs, TagLo/target registers and the deliberate RAM
change. Guest CACHE instructions perform every observed cache operation. This
is identity-mapped RAM in a controlled integer/cache scope, with recompilers
disabled. General backing policies, failed translations and reset/restore are
unverified; operation completion alone supplies no general write-success proof.

### Recommendation

Retain these finite transition outcomes and actual bus/backing witnesses before
unified event/lifecycle handling. A writeback attempt is not general write success.
