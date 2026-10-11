# Primary integration harvest, 2026-10-11

Authoritative base: `211176e7a489fecf8331d02915ee982cd279cb62` on `main`.
Ledger: https://github.com/sting-raider/Plaid/issues/4.

Remote discovery found exactly two integration-prep branches: static executable
identity (`5d4eaa8`) and trace/event identity (`defa8f1`). Both final CI runs passed;
there were no open PRs. Main had only progress-map changes since `ae41bdb`.
The earlier untracked CPU/RSP experiment is preserved outside this harvest.

## Batch 1: finite-static executable identity

Hypothesis: an immutable finite CFG must not close if its instruction values,
execution ownership or simultaneously-known source relations contradict.

The prep branch's consolidated suite ran against unchanged production on
`211176e`: seven adversarial families failed with CLOSED/no relevant blocker;
two controls passed. After reviewing `solver.rs`, CodeImage constructors, the
prep closeout and its research reconciliation, the solver guard was adopted
with all nine tests. The branch-only CI workflow was excluded.

Integrated/superseded production candidates:

- `research/solver-guest-overlap-closure-gpt56sol` (`e071617`)
- `research/solver-physical-alias-closure-gpt56sol` (`c442525`)
- `research/solver-conflicting-region-mapping-gpt56sol` (`2b65dd2`), subsumed
- `research/solver-region-provenance-consistency-gpt56sol` (`eb6a334`)
- `research/solver-codeimage-content-binding-gpt56sol` (`e98f8e0`)
- `research/solver-overlapping-codeimage-source-gpt56sol` (`d2ec016`)
- `research/solver-supplied-image-provenance-gpt56sol` (`75281aa`)

Rejected proposals remain durable evidence: generation labels as lifecycle
chronology (`562c188`) and a redundant cross-fragment edge gate (`f4cc306`).
The canonical-ROM source prototype (`ced56f0`) remains PARTIAL; the solver has no
canonical source witness. Unknown provenance is not guessed. No new native or
whole-ROM completeness claim follows.

Validation: focused 9/9; full locked plaid-core suite; rustfmt check; strict
locked plaid-core Clippy; whitespace check. The Rabbitizer revision in the
checkout, manifest, lockfile and reference lock is exactly
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`. No upstream implementation was copied.
Overlap checks remain pairwise; there is no scalability claim.

## Remaining harvest

First land the consolidated structural event-role/source-projection cluster.
Then reconcile small fail-closed solver, Region/load/overlay and table fixes.
Research-only TLB/cache, copy/transform, RSP and execution-root findings need
selective source-contract composition, not wholesale branch merges. Negative
results and cross-reference disagreements remain explicit obligations. The
progress map retains its existing milestone states until those states change.

## Batch 2: trace/event integrity

Hypothesis: concrete primitive events must have one role/semantic tuple, while
explicit compilation-unit contexts remain reusable. Eight structural adversaries
failed on batch-1 main; the context-sharing control passed. Reviewed/adopted the
consolidated prep guard and complete-source primitive/entry rechecker, excluding
the branch-only workflow and patch-generation helper.

Primary review found an additional contradiction: the source rechecker rejected
a structurally valid observation carrying its explicit source-unit as generic
provenance. A new positive test reproduced that failure. The rechecker now skips
only that explicitly typed context, authenticates its source metadata, and still
requires every source primitive exactly once. A forged context-metadata test
also passes rejection. Focused suites: 9 structural + 11 primitive + 5 entry.
Full locked core, fmt and strict Clippy pass on the composed integration.

Superseded candidates (all `research/*-gpt56sol`): dma-event-uniqueness,
word-store-event-uniqueness, indirect-event-uniqueness,
entry-verification-event-uniqueness, primitive-event-kind-exclusivity,
generic-trace-cross-kind-exclusivity, copy-event-kind-exclusivity,
discovery-trace-source-recheck, entry-install-event-uniqueness (its separate
module is folded into this rechecker). Entry-verification/indirect source-unit
Region-membership candidates remain rejected; equal-byte decoys falsify them.
Global Trace uniqueness and evidence-detail parsing remain rejected.

The solver has no positive verified-source receipt boundary yet. These APIs
authenticate supplied finite projections and cannot establish sensor coverage,
arbitrary lifecycle/copy/root completeness or native readiness.

## Batch 3: deletion-resistant primitive solver gates

Reproduced all six research candidates against batch-2 main. Fourteen adversarial
tests failed across raw stores, raw indirect execution, verification epochs,
empty fetch captures and restricted masks (one epoch test already stayed OPEN
for another reason but lacked its independent blocker).

Adopted/reconciled `research/{solver-raw-store-closure,
solver-raw-store-source-closure,solver-raw-indirect-closure,
solver-entry-verification-epoch,solver-entry-verification-mask,
solver-fetch-capture-count-laundering}-gpt56sol`; no branch workflows landed.
The older store controls now stay OPEN for the broader successful-store scope
exclusion while retaining absence of an unproved executable-write diagnostic.
Added a context-only indirect laundering regression and shared-context control.
Unit membership supplies a correlation consistency check, not exact source-unit
authentication; ADR-0079's source rechecker remains independently necessary.

Focused suites and full locked plaid-core, fmt and strict Clippy pass. No reference
semantic change or native/whole-ROM completeness claim follows.

## Batch 4: retain source-uncorrelated target dispatch

Reproduced diagnostic deletion yielding CLOSED after merging a raw lookup into
a static map. Adopted the typed lookup/runtime-link retention candidate from
`research/solver-targetlookup-monotonicity-gpt56sol`, retaining both source event
kinds, generation and provenance through import/merge/roundtrip. Empty additive
fields are omitted to preserve legacy JSON. The solver independently blocks
these source-uncorrelated facts; an equal-PC static certificate cannot lend them
a source site. Extended ADR-0079's role table and complete-source projection to
the new primitive rather than creating a disconnected validation path. Added
fork/cross-role and deletion/generation-tamper controls. Focused/full locked
core, fmt and strict Clippy pass. No native or whole-ROM proof is added.
