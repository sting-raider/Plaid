# Independent observed PI-to-fetch replay

`python spikes/038-boot-pi-fetch-lineage/replay.py` independently replays the
retained complete v2/v5 boot sources against the new Rust lineage report. It
checks exact source digests, every sample/count and the ordered fetch-chain digest.
Inputs and generated outputs remain ignored. This adds no reference CPU reads,
clock steps or runtime code and does not distribute ROM/firmware assets.

Known records describe observed successful writers and witnessed fill/read paths.
Ordinary scalar and burst writes remove prior PI chains even for equal payloads;
cached residency survives backing changes until a witnessed cache transition
breaks it. Unsupported fills, ambiguous reads and payload contradictions stay
unknown. Complete mutation coverage and executable lifetime remain uncertified.

## Verdict: VALIDATED

### Evidence

Full retained replay passes: 610,000 fetches, 10,954 fully attributed observations,
185 exact samples, no partial words or contradictions. All counts/samples match
Rust; ordered digest `67158997c3fbec624afaea75cd8b255ef59c863258345a89ca80cda1bb3da5c7`.
Both complete source digests and the entire nested prior Rust report agree.

### Constraints and surprises

The independent checker requires canonical big-endian ROM input. Its result is
finite recorded lineage, not a complete mutation census or hardware timing proof.
Endpoint indices are discrete observations and cannot define image lifetimes.

### Recommendation

Independent complete-prefix agreement and Rust report/source tamper tests now
pass. Expose a separate finite CLI report; retain uncertified mutation/lifetime
flags before any contextual discovery promotion.
