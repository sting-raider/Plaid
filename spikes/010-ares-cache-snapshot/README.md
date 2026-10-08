# Actual instruction-cache line snapshots

Hypothesis: the existing pre-decoder prologue can record the cache line that
supplied a cached word, including slot, tag/valid bits, index and eight resident
words, without extra guest reads, translation or clocks. Test stale cached data,
uncached access, invalidation, eviction/reload, TLB remapping and reverse-endian
word selection. A matching tag/data snapshot does not establish a cache lifetime
or its RAM/ROM lineage; identical bytes after eviction remain distinct events.

The pinned ISC reference is built separately with notices retained and both
recompilers disabled. Fixtures are original project-owned setup. No instruction
semantics change or reference CPU code enters Plaid core/native mode.

## Verdict: VALIDATED

### Evidence

- `python spikes/010-ares-cache-snapshot/run.py` builds the pinned reference and
  checks plain/traced/repeated execution of twelve original fetches. CPU/COP0/
  exception/Count and full RAM/instruction-cache hashes agree; repeated raw JSON
  is identical. Final s0=8, Count=444, cache hits=2 and misses=9.
- Eleven cached fetches retain their selected line; the uncached fetch has no
  invented cache snapshot. Effective physical lane selects the actual word,
  including reverse-endian fetch. Nonzero index and virtual banks are checked.
- Same line bytes recur after eviction. Separate slots 129 and 1 hold identical
  tag/index/data; snapshots therefore need slot identity and finite observation
  provenance. Slot 129 later changes while slot 1 retains its copy.

### Constraints and surprises

The fixture declares host setup and reference interpreter scope. Snapshot bytes
do not prove where the line was filled, its immutable lifetime, image generation,
or execution of the seven other resident words. No coherence helper or additional
guest bus/translation call occurs. Cache hashes serialize explicit fields rather
than object padding or host addresses.

### Recommendation

Check the same sensor on a broader boot prefix, with exact prior-stream and full
checkpoint agreement. Require a separate production decision and complete-source
verifier before import. Keep RAM/ROM-copy and cache-mutation lineage unresolved;
no production source/image/generation claim is promoted by this experiment.
