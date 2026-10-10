# Raw fetch summary sequence coverage

Status: VALIDATED candidate fix on isolated research branch.

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`  
Research branch: `research/fetch-summary-sequence-coverage-gpt56sol`  
Coordination claim: issue #4 comment `6097483039`

## Question

Can a serialized `ProgramMap` claim a complete finite raw-fetch capture even when no
summary can possibly own one or more capture sequence positions?

The raw importer itself requires `seq == count` for every event and therefore cannot
produce such a history. The question is whether the independent `ProgramMap::validate`
recheck preserves that structural property after import, serialization, merge or
adversarial editing.

## Counterexample

For a capture with `fetch_count = 6`, construct two individually valid summaries:

- A: `first_seq=0`, `last_seq=4`, `occurrences=4`
- B: `first_seq=1`, `last_seq=3`, `occurrences=2`

The occurrence total is exactly six. Both counts fit inside their respective spans and
all summary endpoints are in range and non-conflicting. Nevertheless, the union of all
possible sequence positions is only `0..=4`. Sequence 5 cannot belong to either summary,
so no concrete six-event history can have these summaries.

Unmodified canonical-base validation accepted the forged map. Actions run
`38052159296`, job `114213296990`, compiled the exact pinned Rabbitizer revision
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`; the focused matrix produced two passing
controls and one expected-red failure because `validate()` returned `Ok(())`.

A second adversary leaves an *internal* hole at sequence 4 while using equal fetched
words for every summary. That demonstrates that payload equality cannot create missing
chronology.

## Candidate invariant

For each capture, validation now additionally collects every summary's exact
`[first_seq,last_seq]` interval, sorts those intervals and requires their union to cover
all sequence positions `0..fetch_count` without a gap. Existing checks still separately
require exact total occurrence count, endpoint consistency, per-summary bounds and
provenance.

This is deliberately only a necessary structural invariant. It does **not** treat every
position inside a summary interval as an actual occurrence, infer contiguity, infer
execution identity, establish executable lifetime, or derive source provenance from
value equality.

The candidate production diff is commit
`d78b1d3849efd2a94dfae9c7e2fc8ccbd93357c9` (`program.rs`, 21 insertions / 1 deletion).
The first candidate run `38052261607`, job `114213587094`, passed the focused 3-case
matrix, the complete `plaid-core` suite (106 tests at that branch point), and clippy;
that same run materialized the tested diff onto the research branch.

## Falsification controls

The Rust regression preserves these boundaries:

- an empty zero-fetch capture with no summaries remains valid;
- nested/interleaved summaries corresponding to concrete history `A,B,C,C,B,A` remain
  valid even though repeated observations are non-contiguous;
- a trailing missing sequence is rejected despite exact aggregate counts;
- an internal missing sequence is rejected even when all fetched payload words are equal.

`experiments/fetch-summary-sequence-coverage/model.py` independently models the legacy
predicate and the added coverage predicate. It brute-forces genuine histories over a
small alphabet, verifies that every genuine summary set passes the new invariant, and
constructs a family of forged trailing-hole summaries that pass the legacy aggregate
checks but fail coverage.

The same model also deliberately preserves a stronger counterexample that defeats both
the legacy and candidate predicates without contradicting this bounded result. For a
seven-event capture:

- A: `[0,2]`, `occurrences=3`
- B: `[1,3]`, `occurrences=2`
- C: `[4,6]`, `occurrences=2`

The interval union covers `0..=6`, all endpoints are distinct, and total occurrences are
seven. Yet no exact history exists: A's three occurrences force A at sequence 1 while
B requires sequence 1 as its first occurrence. This is why interval coverage must not
be promoted into a whole-summary feasibility certificate.

## Closed-world impact

This closes one deletion/fabrication path in the raw evidence substrate: a map can no
longer claim that all fetch occurrences of a finite capture are summarized while
leaving a sequence position outside every summary interval.

It does **not** by itself make either solver scope CLOSED. Current solver policy already
keeps retained raw fetch observations OPEN because executable identity/lifetime are not
proved by finite samples. The benefit is earlier and more fundamental: later proof
composition and complete-source rechecking can rely on the serialized summary set not
having this specific impossible chronology.

## Remaining gap

Interval-union coverage is necessary, not a proof that every arbitrary set of interval
counts has a globally realizable assignment of individual occurrences. The explicit
seven-event A/B/C counterexample above passes interval coverage while having zero
concrete histories. A stronger whole-summary feasibility proof is separate work and
should not be silently inferred from this result. Raw fetch summaries also remain finite
observations, not reachability, lifetime, cache-residency or source-completeness
certificates.

## Reproduction

On the research branch:

```sh
python3 -m py_compile experiments/fetch-summary-sequence-coverage/model.py
python3 experiments/fetch-summary-sequence-coverage/model.py
cargo test -p plaid-core --test fetch_summary_sequence_coverage -- --nocapture
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --tests -- -D warnings
```

To reproduce the original red result, run the focused regression against canonical base
`211176e7a489fecf8331d02915ee982cd279cb62` before applying candidate commit
`d78b1d3849efd2a94dfae9c7e2fc8ccbd93357c9`.

## Integration recommendation

Adopt the small `ProgramMap::validate` interval-union recheck together with the focused
regression. Preserve the distinction between an interval's *possible* occurrence
positions and actual per-event chronology. Do not use this invariant to infer missing
occurrences, prove global summary feasibility, or collapse equal-valued summaries.
