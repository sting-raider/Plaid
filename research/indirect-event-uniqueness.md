# Raw indirect trace-event identity uniqueness

Status: **VALIDATED**

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/indirect-event-uniqueness-gpt56sol`

Production candidate commit: `da7b7ee5fd75a6411831208a989c7b1af54aa18d`

## Question

Can one concrete `IndirectTargetObserved` trace-event identity be reused across multiple semantically incompatible `ObservedIndirect` facts and still pass `ProgramMap::validate()`?

This is an evidence-integrity question below indirect-target closure. It does not ask whether a finite set of observed targets proves an indirect site closed. It asks whether one concrete executed transfer can be fabricated into multiple distinct transfers before later provenance and closure logic consumes the raw facts.

## Producer contract

`merge::import_trace` assigns every trace record a session-qualified evidence identity of the form `trace:{session}:{seq}`. An `IndirectTargetObserved` record produces one raw `ObservedIndirect` carrying that record's evidence identity together with:

- executing site;
- observed target;
- optional delay-slot PC;
- current invalidation generation;
- optional `source_unit`, which is the Trace evidence identity of the relevant `CompileBegin` event.

The `source_unit` identity is deliberately different from the execution-event identity. A compiled source unit can execute multiple indirect transfers, so its `CompileBegin` evidence is reusable contextual provenance rather than a one-operation identity.

On canonical `main`, `ProgramMap::validate()` validated each raw indirect row independently. It checked alignment, exact `site + 4` delay-slot shape when present, the existence and Trace kind of `source_unit`, and non-empty valid evidence references. It did not require a Trace event identity attached to a raw indirect fact to retain one semantic meaning across the map.

## Counterexample on canonical main

The focused regression constructs valid Trace evidence for one concrete raw indirect event and reuses that same identity while changing exactly one semantic component.

Canonical `main` accepted all of these forged combinations:

1. same event identity, different target;
2. same event identity, different source site (with a correspondingly valid delay-slot PC);
3. same event identity, different delay-slot presence;
4. same event identity, different invalidation generation;
5. same event identity, different explicit source-unit identity.

The merge adversary is stronger than a single malformed hand-edited map: two maps validate independently, each assigns the same concrete event identity to a different target, and `merge_maps()` accepts their union. One observed execution can therefore be laundered into two executions by composition.

Baseline Actions run `38047251017`, job `114199157944`, ran the regression against unchanged canonical production code. Result: **expected FAILURE**, with 2 controls passing and 4 aggregate forged-event tests failing their expected-rejection assertions. The build used the pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

## Falsification controls

The regression also attacks an overly broad fix.

Valid cases that must remain accepted are:

- distinct concrete Trace event IDs supporting distinct transfers;
- equivalent transfer semantics accumulating additional provenance;
- one `CompileBegin` `source_unit` Trace identity contextualizing multiple distinct indirect execution events, even when that source-unit identity is also present in the generic evidence set.

The last case matters because simply treating every Trace reference on `ObservedIndirect` as a unique operation ID would reject legitimate repeated execution from one compiled unit.

## Candidate invariant

Within `indirect_observations`, every Trace evidence reference other than the row's explicit `source_unit` is bound to this tuple:

`(site, target, delay_slot_pc, generation, source_unit)`

If the same such Trace identity appears again with a different tuple, validation fails with:

`indirect trace event has conflicting semantics`

The check is local and value-independent. It does not infer identity from address equality, target equality, bytes, generation adjacency, or chronology. Two different event identities may describe identical semantics. One event identity may appear on equivalent facts with additional provenance. The explicit `source_unit` context may be reused across distinct events.

## Executable evidence

Candidate workflow run `38047462335`, job `114199760905`: **SUCCESS**.

It performed:

1. deterministic application of the candidate production hunk;
2. focused `indirect_event_uniqueness` regression: **7 passed, 0 failed**;
3. full `cargo test --locked -p plaid-core`: **110 passed, 0 failed** across the crate's test binaries;
4. `cargo fmt --all -- --check`: pass;
5. `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`: pass;
6. `git diff --check`: pass;
7. commit and push of the validated production hunk as `da7b7ee5fd75a6411831208a989c7b1af54aa18d`.

Post-commit run `38047537936`, job `114199987036`: **SUCCESS** with the candidate already committed, again passing the focused regression, full `plaid-core`, formatting and clippy.

The repaired integration diff is `research/indirect-event-uniqueness.patch`. In run `38047555800`, the explicit `git apply --reverse --check` step passed against the committed candidate, confirming the diff matches the production hunk rather than merely resembling it.

An intermediate run `38047411233` failed before compilation because the first hand-written unified diff had incorrect hunk metadata. That is a harness failure only, not semantic evidence. The corrupt diff was replaced with the exact committed diff and a deterministic source-transform spike.

## Artifacts

- `crates/plaid-core/tests/indirect_event_uniqueness.rs` - adversarial regression and controls.
- `crates/plaid-core/src/program.rs` at candidate commit `da7b7ee5...` - smallest production validator guard.
- `spikes/indirect-event-uniqueness/apply_candidate_fix.py` - deterministic candidate application from the canonical base.
- `research/indirect-event-uniqueness.patch` - integration-oriented production diff.
- `.github/workflows/research-indirect-event-uniqueness.yml` - executable validation harness.

## Composition with prior research

This composes and challenges:

- ADR-0009 deletion/fabrication resistance: one concrete observation must not be fabricable into multiple executions;
- ADR-0021 exact executing-unit provenance: `source_unit` remains a separate contextual identity and participates in the event semantic tuple;
- ADR-0023 canonical provenance union: equivalent facts may union provenance without collapsing distinct event identities;
- completed raw-indirect solver deletion-resistance work: a future solver must not consume a self-contradictory raw observation graph;
- completed DMA copy-event uniqueness and word-store event-identity research: concrete operation identities need stable semantics, but each fact type requires its own producer-aware invariant rather than blind global uniqueness.

## Closed-world impact

This bug does not by itself make the current declared-static-images solver falsely CLOSED: finite raw indirect observations are already insufficient to prove exhaustive indirect-target closure.

It does corrupt the evidence boundary that higher-order closure depends on. If one observed execution can be duplicated into multiple sites, targets, generations, or source units, later logic can overstate execution coverage, target coverage, generation-specific behavior, lifetime histories, or provenance-linked reachability. The merge adversary is especially relevant to whole-ROM composition because independently valid maps could otherwise form an invalid event graph only after union.

The candidate therefore strengthens ProgramMap as a composable evidence object. It prevents one concrete execution identity from acquiring two incompatible meanings before any future positive closure rule can trust it.

## Remaining gap

`Evidence` stores generic kind/producer/revision/detail metadata, not the original typed trace record. The validator can establish semantic uniqueness for Trace identities used by raw indirect facts, but it cannot prove that an arbitrary non-`source_unit` Trace identity actually originated from an `IndirectTargetObserved` record in the immutable source trace.

Full event-kind authenticity needs a source-bound typed evidence schema, immutable trace re-import/recheck, or an equivalent independently checkable binding. Cross-kind reuse of generic Trace identities must also be handled deliberately rather than assuming every Trace reference globally denotes the same class of operation.

This lane also does not prove indirect-target exhaustiveness, pointer-table immutability, executable lifetime, cache/TLB closure, exception-root completeness, or whole-ROM closure. Those obligations remain OPEN where not independently discharged.

## Reproduction

Against canonical base `211176e7...`:

```sh
git apply research/indirect-event-uniqueness.patch
cargo fmt --all
cargo test --locked -p plaid-core --test indirect_event_uniqueness -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

On the research branch, where the candidate is already committed, validate that the integration diff exactly reverses the production hunk with:

```sh
git apply --reverse --check research/indirect-event-uniqueness.patch
```

Do not merge this research branch wholesale. The primary integrator should selectively take the production `ProgramMap::validate()` hunk and focused regression, composing it carefully with neighboring validator changes that may have landed on `main` after the canonical base.