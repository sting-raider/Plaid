# Actual instruction-cache fill events

Hypothesis: a callback immediately after the existing completed bus burst can
distinguish refills with equal payloads, without another guest read or clock.
Reuse spike 010's twelve controlled fetches. Record monotonic fill ordinals,
selected slot, effective request, actual burst address and eight returned words.
Observe no guest memory beyond the existing result. Reference builds and outputs
remain ignored, with upstream notices preserved.

Run `python spikes/012-ares-cache-fill/run.py`.

## Verdict: VALIDATED for the controlled completed-fill scope

### Evidence

Plain/traced/repeated complete checkpoints match spike 010's fixed goldens, with
both recompilers disabled. Nine actual fills distinguish two equal-payload
refills and two physical-line aliases in distinct cache banks. Twelve fetches
link to fill ordinals 1/1/none/2/3/4/5/6/6/7/8/9. The uncached fetch has no link;
two hits reuse the existing fill. Count=444, hits=2, misses=9 and s0=8. Repeated
JSON is exact; full RAM/cache hashes remain unchanged. The callback reads only
the existing completed bus result and computes slot from its array position.
No host pointer is serialized and no additional bus or translation call occurs.

### Constraints and surprises

This sensor covers completed fills in the controlled fixture only. It does not
cover tag stores, invalidation history, resets/restores, RAM mutation/copy lineage
or all bus sources. A last-fill link is not a general cache/executable lifetime.
The bus burst address alone does not identify backing RAM or ROM.

### Recommendation

Extend invalidation/tag-store and backing-source witnesses before broader
lifecycle claims or production handling. A completed fill ordinal supplies an
event boundary but cannot certify the interval until a later fetch.
