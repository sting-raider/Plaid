# Raw fetch summary global realizability

Status: VALIDATED candidate fix on isolated research branch.

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`  
Research branch: `research/fetch-summary-realizability-gpt56sol`  
Coordination claim: issue #4 comment `6097816739`  
Materialized candidate: `a223a960f877d284dafa4396269a259d4b17b696`

## Question

Can a serialized `ProgramMap` pass every current per-summary check, exact aggregate
`fetch_count`, non-conflicting exact first/last endpoint witnesses, and even complete
union coverage of all sequence positions while still describing no possible concrete
capture sequence?

Yes. This is stronger than the sequence-coverage gap documented by
`research/fetch-summary-sequence-coverage-gpt56sol`.

## Current-main counterexample

For `fetch_count = 7`, use three distinct summaries:

- A: `first_seq=0`, `last_seq=2`, `occurrences=3`
- B: `first_seq=1`, `last_seq=3`, `occurrences=2`
- C: `first_seq=4`, `last_seq=6`, `occurrences=2`

The occurrence total is exactly seven. Every endpoint is in range, endpoint identities
are compatible, every summary count fits inside its span, and the interval union covers
all positions `0..=6`.

Nevertheless no concrete history exists. A has three occurrences in a three-position
span, so A must own positions 0, 1 and 2. B's exact first occurrence requires B to own
position 1. Those requirements collide.

Unmodified canonical main accepted this forged map. Expected-red Actions run
`38054635011`, job `114220474292`, checked the exact Rabbitizer pin
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`; the focused test matrix had two controls
pass and the two impossible cases fail specifically because `ProgramMap::validate()`
returned `Ok(())`. An equal-word (`0xdeadbeef`) variant was also accepted, confirming
that payload equality cannot repair impossible chronology.

## Reduction to interval-quota scheduling

Each summary contributes fixed occurrences at `first_seq` and `last_seq` (one fixed
occurrence when they are equal). Its remaining quota is therefore:

- `occurrences - 1` when `first_seq == last_seq`;
- `occurrences - 2` otherwise.

Every remaining occurrence must occupy one free sequence position strictly inside that
summary's `(first_seq,last_seq)` interval. Existing endpoint conflict checks guarantee
that fixed endpoint positions have a unique semantic owner.

The remaining problem is a unit-slot interval scheduling / bipartite matching problem:
interior occurrences have release `first_seq + 1`, deadline `last_seq - 1`, and exact
per-summary demand. An earliest-deadline-first (EDF) assignment is a complete
feasibility test. The candidate implementation processes endpoint boundaries and
consumes entire free gaps in quota-sized chunks, so it does not loop over every raw
fetch sequence number.

A standard exchange argument gives the local completeness step: if a feasible schedule
uses a later-deadline active occurrence at a free slot while the earliest-deadline
occurrence is scheduled later, swap the two. The earliest-deadline occurrence was
already released, and the displaced occurrence's deadline is no earlier, so the swap
preserves legality. Repeating produces an EDF schedule whenever any schedule exists.
Between adjacent endpoint boundaries no new summary is released, so bulk consumption
of the free gap is equivalent to per-slot EDF.

Complexity is `O(S log S)` time and `O(S)` space for `S` summaries/endpoints, rather
than `O(fetch_count)`. The check uses chronology constraints only. It does not infer
provenance, execution identity, generation, lifetime, source, cache residency, or copy
identity from equal values.

## Independent falsification model

`experiments/fetch-summary-realizability/model.py` contains two independent predicates:

1. an exponential exact assignment oracle for small candidate sets; and
2. the candidate aggregate EDF sweep.

It also reconstructs summaries from concrete histories so that genuine histories are
positive controls.

Deterministic Actions evidence (runs `38054906544`, `38054950414`, and green run
`38055031210`) produced the same report twice per run:

- exhaustive concrete histories checked: `21,845`;
- unique genuine summary sets: `949`;
- seeded random exact-oracle comparisons: `20,000`;
- random feasible candidates: `9,184`;
- random impossible candidates: `10,816`;
- sweep/oracle disagreements: `0`;
- large sparse probe: `1,000,000` events represented by `100,000` summaries;
- seed: `1179865676` (`0x4653524c`);
- semantic report SHA-256:
  `7c7e9a402accdcb8e7d9288a946fdc5cb15d106f483fac61042f9ffc20ad5f2a`.

The fixed published impossible counterexample is rejected by both the exact oracle and
EDF candidate; a concrete `A,B,B,A,C,C,C` control is accepted by both.

## Rust regression matrix

`crates/plaid-core/tests/fetch_summary_realizability.rs` covers:

- the seven-event interval-covered but globally impossible A/B/C set;
- the same endpoint/quota collision with equal payload words;
- the prior trailing uncovered-sequence adversary;
- the prior internal-hole adversary with equal payloads;
- a concrete interleaved history (`A,B,B,A,C,C,C`);
- a zero-fetch capture with no summaries.

The stronger realizability invariant therefore subsumes the earlier interval-union
coverage check while preserving non-contiguous repeated observations.

## Candidate implementation

`crates/plaid-core/src/program.rs` now contains `fetch_summaries_realizable`. During
`ProgramMap::validate`, each capture collects only `(first_seq,last_seq,occurrences)`
constraints. After the existing exact aggregate-count check, validation rejects the map
with `fetch summaries are not jointly realizable` unless the EDF sweep can assign all
remaining occurrences to legal free positions.

The tested source was materialized as commit
`a223a960f877d284dafa4396269a259d4b17b696` after green Actions run `38055177374`, job
`114222048833`. That run passed:

- exact dependency pin guard;
- deterministic model and repeated-output comparison;
- `cargo fmt --all -- --check`;
- the expanded six-case realizability regression;
- full `cargo test --locked -p plaid-core`;
- `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`;
- branch-only materialization of the already-tested `program.rs` diff.

An earlier expected-red run (`38054635011`) preserves the current-main reproduction.
A subsequent green run (`38055031210`) independently passed the four-case matrix,
complete core suite and clippy before the two prior coverage cases were added.

## Closed-world impact

This removes a fabrication path in the finite raw-fetch evidence substrate. Later proof
composition can reject summary sets whose exact chronology facts are mutually
inconsistent, instead of accepting them merely because aggregate counts and interval
coverage look plausible.

It does **not** make either solver scope CLOSED. Raw fetch observations remain finite
observations, not proofs of executable reachability, generation/lifetime, cache
residency, source completeness, mutation completeness, or whole-ROM closure. This check
only proves that the serialized `(first,last,count)` facts admit at least one concrete
sequence assignment.

## Remaining gap

Realizability proves existence of a history consistent with the summaries, not that the
serialized summaries are the summaries of a particular original raw trace. Where the
raw capture is available, `verify_fetch_capture` remains the stronger source-bound
recheck. Event-kind authenticity, evidence-manifest completeness, executable lifetimes,
cache/TLB composition, mutation accounting and whole-ROM closure remain separate proof
obligations.

The fuzz/exhaustive search is strong falsification evidence, not a substitute for a
formal machine-checked proof of the EDF reduction. The exchange argument above and the
independent exact oracle are the present justification.

## Reproduction

From `research/fetch-summary-realizability-gpt56sol` after materialization:

```sh
python3 -m py_compile experiments/fetch-summary-realizability/model.py
python3 experiments/fetch-summary-realizability/model.py
cargo fmt --all -- --check
cargo test --locked -p plaid-core --test fetch_summary_realizability -- --nocapture
cargo test --locked -p plaid-core
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

To reproduce the original false acceptance, use canonical base
`211176e7a489fecf8331d02915ee982cd279cb62` with the regression from commit
`ef311bb7a49ba233322328276a6439938e6c19d7`, or inspect Actions run `38054635011`.

## Integration recommendation

Prefer the global realizability validator over the earlier interval-union-only
candidate. It strictly covers the earlier missing-position adversaries and also rejects
quota/endpoint conflicts whose interval union is complete. Integrate the helper,
per-capture constraint collection, six-case regression and deterministic model; retain
the existing endpoint/value/provenance checks as separate invariants.

Do not promote realizability into a source, lifetime or closure certificate, and do not
collapse equal-valued semantic summaries.
