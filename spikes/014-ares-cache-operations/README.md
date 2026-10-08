# Completed guest cache operations

Hypothesis: a callback around the existing guest CACHE handler can retain exact
before/after tag/data transitions, without another bus/translation access or
clock. Reuse spike 013's measured tag-store/invalidation counterexample.

Run `python spikes/014-ares-cache-operations/run.py`.

## Verdict: VALIDATED for tag-store/index-invalidate operations

### Evidence

Three completed tag-store/index-invalidate operations retain unchanged resident
words, plus the same two fills and seven fetches. Operation PC, virtual/physical
address and before/after tag/words are exact. Transitions are 1→0x4001,
0x4001→0x4000 and 0x4001→1, at fill counts 1/1/2. Plain/traced/repeated complete
checkpoints match the independently checked spike 013 goldens; JSON repeats
exactly. Count=103, hits=2, misses=2 and s0=9, with unchanged full RAM/cache hashes.
The complete prior JSON projection remains exact, including every fetch/fill and
post-step record. A fresh default-observer spike 013 rebuild also retains its goldens.
The observer copies existing line fields before the handler and after completion;
it performs no additional guest access or timing step. Default builds omit the
generated operation observer entirely.

### Constraints and surprises

Only tag-store/index-invalidate behavior is measured here. Hook coverage also
selects hit-invalidate/fill/writeback operations, which need separate cases.
Operation completion is no proof of successful backing-memory writeback.
Resets/restores, general bus sources and executable lifetimes remain unresolved.

### Recommendation

Verify additional operation outcomes and actual backing reads/writes before
joining a complete cache lifecycle or promoting production handling.
