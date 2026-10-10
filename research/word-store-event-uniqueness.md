# Word-store trace event identity uniqueness

Status: **VALIDATED**

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/word-store-event-uniqueness-gpt56sol`

## Question

Can one concrete trace-event identity be reused across multiple semantically incompatible `ObservedWordStore` facts and still pass `ProgramMap::validate()`?

This is deliberately narrower than the existing raw-store CLOSED/OPEN work. Those lanes ask what a valid raw CPU store means for executable mutation/source closure. This lane asks whether the identity of the raw store operation itself is protected against fabrication before those later proof obligations consume it.

## Existing producer contract

`merge::import_trace` assigns each trace record the session-qualified identity `trace:{session}:{seq}`. A `CpuWordStoreObserved` record produces one `ObservedWordStore` carrying the current record's evidence ID. Thus a Trace evidence ID is an operation identity, not a reusable descriptive tag.

On the canonical base, `ProgramMap::validate()` checked each `ObservedWordStore` independently for aligned site/destination, cached-RDRAM destination range, and existing non-empty provenance. It did not check that the same Trace evidence ID always denoted the same raw store semantic tuple.

## Counterexample

The focused regression creates a valid Trace evidence entry `trace:session:7`, then attaches that same ID to two individually valid stores while changing exactly one of:

- executing store site;
- destination;
- written value;
- import generation.

All four pairs represent two different raw operations but claim the same concrete trace-event identity. Canonical `main` accepts the forged map, so the regression expecting rejection fails.

Controls preserve intended sharing:

- two distinct Trace IDs may support two distinct stores;
- two equivalent store facts may share one Trace ID while unioning additional provenance;
- unrelated non-Trace evidence may be shared across distinct stores and does not create operation identity.

## Executable evidence

Baseline regression commit: `257bd33efb6971084613b95f06955047337e78c2`.

Baseline workflow head: `a9f626b4dd9fc5dead8708c5d0008e8bef13829d`.

Baseline Actions run `38046138981`, job `114195945206`: **FAILURE** in the focused regression on unmodified canonical production code. Later steps were skipped.

Candidate semantic run `38046317735` showed the guard applying successfully; focused regression and full `plaid-core` suite both passed. Its only failure was rustfmt on the unformatted research working tree, not semantics.

Final formatted candidate run `38046394317`, job `114196690634`: **SUCCESS**. It passed:

1. patch application;
2. rustfmt of the candidate working tree;
3. focused `word_store_event_uniqueness` regression;
4. full `cargo test --locked -p plaid-core`;
5. `cargo fmt --all -- --check`;
6. `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`.

The run uploaded artifact `11666879011`, `word-store-event-uniqueness-candidate`, ZIP digest `sha256:94bc1cf6d68aecbd4bafa174f6d97b9fe19c741c6be35f266842d38c757e657c`. The formatted production patch inside has SHA-256 `be8147678948acc3bf23815b1991138dfc6647969842ef118034a5a92320fee3`.

Two intermediate runs (`38046231408`, `38046269878`) failed before compilation because the first research patch file carried bad diff metadata. They are harness failures only and are not counted as semantic evidence. The exact formatted diff from the successful run was subsequently committed as `research/word-store-event-uniqueness.patch`.

## Candidate invariant

Within `word_store_observations`, every evidence reference whose `EvidenceKind` is `Trace` is mapped to the tuple:

`(site, destination, value, generation)`.

If the same Trace ID appears again with a different tuple, validation fails with `word store trace event has conflicting semantics`.

The guard intentionally does **not** impose global uniqueness on arbitrary evidence IDs. Static/model/other provenance can legitimately be shared. Nor does it reject multiple equivalent facts that carry the same event identity plus additional provenance.

This is a local `BTreeMap<&str, tuple>` check inside `ProgramMap::validate()`: no payload equality, address adjacency, generation arithmetic, or inferred chronology is used.

## Why it matters for closed-world proof

A future executable mutation certificate may consume `ObservedWordStore` as a successful writer event. If one concrete event ID can be duplicated onto two incompatible store facts, a single observed CPU operation can be fabricated into multiple mutations. That can falsely populate mutation coverage, writer ancestry, executable-lifetime transitions, cache/backing causality, or absence-of-unseen-writer arguments.

The bug does not make the current `DeclaredStaticImages` solver directly CLOSED by itself: raw store effects already participate in separate fail-closed checks. Its impact is at the evidence-integrity boundary that higher-order closure work depends on. Fixing it prevents later proof composition from receiving a self-contradictory raw event graph as if it were trustworthy input.

Same value is not a defense. The equal-value/different-destination or equal-value/different-generation cases are still distinct operations and must remain distinct provenance.

## Composition with prior work

This composes:

- ADR-0009 deletion/fabrication-resistant proof obligations;
- ADR-0020 retention of successful raw SW observations;
- ADR-0023 provenance union semantics;
- the completed DMA copy-event uniqueness lane as a neighboring precedent that concrete operation IDs need one semantic meaning.

It does not replace DMA uniqueness, raw-store destination/source closure, executable mutation census, cache/TLB composition, overlay lifetime, decompression/relocation lineage, or WholeRom closure.

## Remaining gap

This lane only binds Trace identities when they are used as evidence by `ObservedWordStore`. It does not prove that a referenced Trace ID actually came from a `CpuWordStoreObserved` record in the original immutable trace. ProgramMap currently stores generic evidence metadata, not the original typed trace record, so full event-kind authenticity needs a stronger source-bound evidence schema or independent re-import/recheck.

Equivalent identity-uniqueness checks may also be needed for other operation-bearing raw facts, but they must be researched independently rather than generalized blindly: some evidence IDs intentionally cover ranges or multiple equivalent derived facts.

## Reproduction

From this research branch:

```sh
git apply research/word-store-event-uniqueness.patch
cargo fmt --all
cargo test --locked -p plaid-core --test word_store_event_uniqueness
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

Do not merge this research branch wholesale. The primary integrator should selectively apply the production validator hunk and focused regression, then format the test in the integration commit.
