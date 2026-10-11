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
