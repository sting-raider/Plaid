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

Both prep clusters and all 45 core source/test candidate branches have been
reconciled through the batches below. Indexed research-only branches are not
certified or automatically integrated.
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

## Batch 5: executable Region and producer binding

Reviewed production producers and independently reproduced ten failures across
`research/{region-physical-span-overflow,region-physical-alignment,
load-region-binding,overlay-region-binding}-gpt56sol` on batch-4 main. All four
candidates are superseded by this integration. Retained their 19 adversarial and
positive controls: exactly ending physical spans remain valid, absent physical
metadata is not guessed, and overlay descriptors may serve separate generations.
Load binding is independent of copy-event presence; producer tuples and existing
DMA coverage obligations agree. Focused tests, full locked plaid-core, fmt and
strict Clippy pass. No branch workflow or upstream implementation is included.

## Batch 6: global fetch-summary realizability

Four adversaries reproduced on batch-5 main; two original controls passed.
Reviewed/adopted the quota scheduling validator and six regressions from
`research/fetch-summary-realizability-gpt56sol`, superseding both that candidate
and `research/fetch-summary-sequence-coverage-gpt56sol`. Interval union alone
misses endpoint/quota collisions. The endpoint-gap sweep retains separate
per-summary and provenance checks and does not expand every sequence position.

Retained the independent Python exact-assignment experiment: 21,845 concrete
histories, 949 unique genuine sets, 20,000 oracle comparisons (9,184 feasible,
10,816 impossible), zero disagreements and a million-event sparse probe reproduce
SHA-256 `7c7e9a402accdcb8e7d9288a946fdc5cb15d106f483fac61042f9ffc20ad5f2a`.
Added a primary bounded exhaustive concrete-history oracle against actual Rust
validation for up to six events and three distinct summaries, including equal
payloads. All seven focused tests, full locked core, fmt and strict Clippy pass.
The exact Rabbitizer checkout/manifest/lock/reference revision remains
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`. Realizability supplies no original
source authentication, mutation census, executable lifetime or closure receipt.

## Batch 7: guarded pointer-table composition

Eight regression failures reproduced on batch-6 main across predecessor bypass,
dispatch-prefix bypass and exceptional executed guard slots; five original
controls passed. Reconciled `research/{pointer-prefix-bypass,
pointer-guard-predecessor-bypass,pointer-guard-trap,pointer-target-generation}
-gpt56sol`; all four production candidates are superseded. No CFG edge suppression
or raw branch merge. Kept exact image/generation checks and selected-edge annulment.

Added a primary remote taken-branch fixture: standalone slot entry reaches an
exit, not the dispatch, while branch entry skips the compare and must reject.
The target-generation candidate supplies an independent unresolved obligation;
current solver behavior was already OPEN, so no false-CLOSED repair is claimed
for that candidate. Seventeen focused tests, full locked core, fmt and strict
Clippy pass. Removed an unused research-test import and a redundant closure
found by strict Clippy. The exact pinned Rabbitizer trap/opcode metadata and
existing discovery unsupported policy agree. No upstream code is reused.

## Batch 8: intervening executable writers

Four research adversaries reproduced on batch-7 main; three controls passed.
Reviewed/adopted `research/import-dma-intervening-store-gpt56sol`, superseding its
production candidate. Primary review additionally reproduced stale attribution
after an equal-byte partial DMA following an older covering copy. Extended the
same causal rule to retained DMA writers rather than allowing a second primitive
kind to evade it. Added a later complete-copy control and an exact store-event
evidence assertion plus complete-source/installed-entry recheck.

Nine focused cases, shared source-projection suites, full locked core, fmt and
strict Clippy pass. `scripts/test_mupen_hooks.py` reproduces 38 events/four units,
clipped DMA, links, epoch separation, Rust import and OPEN solving. Reviewed the
original cartridge copy implementation via `git show` at exact Mupen revision
`ba95bab92a76744753bfe61470823a4937850ab0`, separately from the applied sensor patch
and its limited successful cached-RDRAM SW contract. No sensor patch changed.
No byte-equality origin inference, positive store/mixed-writer lineage, complete
mutation coverage or native readiness is claimed. Writer scans remain bounded
linear checks without a scalability claim.

## Batch 9: retain negative controls and source-unit decoys

Selectively retained regressions from `research/{indirect-delay-slot,
load-region-destination-binding,solver-cross-fragment-edge,
solver-static-generation-lifetime,solver-rsp-microcode-closure,
solver-resource-limit-deletion,solver-rom-source-binding}-gpt56sol`.
No production patch is warranted for these rejected/relative-scope hypotheses.
Their regression deliverables are now reconciled into main. Canonical-ROM byte
authentication remains outside the declared immutable-image solver contract;
the strict source-binding prototype remains unadopted, and native completeness
stays false in every source-binding control.

One old generation control expected overlapping generations to close. ADR-0078
supersedes that expectation: retained the overlap as OPEN with an explicit
identity-selection blocker and added a disjoint-root CLOSED control. Generation
numbers remain identity labels, not evidence of runtime transitions.

Reconciled `research/{entry-verification-source-unit-binding,
indirect-source-unit-binding}-gpt56sol` using one combined equal-byte/same-identity
recompile adversary against the complete-source verifier. Both compile units
occur on the unioned Region, yet substituting the wrong unit in either primitive
is rejected. The failed Region-membership candidate remains rejected; its
branch-local helper is not promoted into production or permanent tests.

All 28 retained scope/deletion controls and the new source-unit adversary pass.
The real 520-stage/512-pass frontier test takes about 127 seconds locally and is
retained without shrinking its boundary or ignoring it. Full locked workspace,
fmt, strict workspace Clippy and synthetic CLI checks pass. No production
behavior, milestone state or closure scope is expanded by this test batch.

## Batch 10: measured merge conflict indexing

Reviewed the exact-source transformer and equivalence argument from
`research/programmap-merge-scalability-gpt56sol`; its production candidate is
superseded. Reproduced release baseline on batch-9 main before modifying source.
Retained four research equivalence cases and an explicitly invoked ignored
release benchmark; added a 256-subset independent old-pairwise oracle covering
generation separation, edge-kind groups, canonical diagnostic collisions and
merge reversal. No semantic winner or provenance reference is discarded.

Local release medians (three samples each), in milliseconds:

| Facts | Blocks before | Blocks indexed | Edges before | Edges indexed |
| ---: | ---: | ---: | ---: | ---: |
| 500 | 1.230 | 0.628 | 1.012 | 0.645 |
| 1,000 | 3.893 | 1.170 | 3.061 | 1.407 |
| 2,000 | 14.738 | 2.745 | 10.710 | 2.954 |
| 4,000 | 55.622 | 4.910 | 39.558 | 6.997 |
| 8,000 | 224.453 | 11.273 | 154.773 | 14.700 |

At 8,000 facts, measured speedups are about 19.9x and 10.5x on this host.
Five focused equivalence tests, the 14-test existing merge suite, full locked
core (including the real 512-pass exhaustion case), fmt and strict Clippy pass.
Exact Rabbitizer pin remains unchanged. These synthetic measurements claim no
general solver/ProgramMap scaling, hardware behavior, memory improvement or
whole-ROM closure. The branch-only transformer/workflow is not included.

## Batch 11: bounded two-path indirect join

Reviewed `research/cross-block-join-gpt56sol` and reproduced its conservative
baseline on batch-10 main: five desired completeness cases failed while six
negative controls passed. Its production candidate is now superseded. Adopted
the exactly-two-path certificate and independent reconstruction, sharing scalar
path simulation with the existing chain rather than duplicating transfer logic.
The existing whitelist, unknown-state initialization, final-slot separation and
bounded root/path policies remain intact; no pseudo-op widening or runtime guest
execution is added.

Retained all eleven research regressions and added excess-path, unsupported-arm
effect and tampered-digest controls. An initial overbroad effect assertion was
corrected: SYSCALL terminates one CFG arm, allowing the older single-path prover
to certify the other target, while the independent unsupported-scope effect
still keeps the solver OPEN. No exceptional arm is admitted to the join proof.

Fourteen focused join cases, existing ten indirect/four delay-slot cases, full
locked workspace (including the real 512-pass frontier), fmt, strict workspace
Clippy and synthetic CLI checks pass. Exact pinned Rabbitizer and existing
transfer semantics remain unchanged. No whole-ROM or native scope is expanded.

## Canonical CI and harvest inventory

Added a production Rust workflow rather than preserving worker-specific patching
or emulator-build scaffolding. Actions run `38129473623` at `d74b2a0` passes the
exact decoder-pin guard, fmt, strict workspace Clippy, full workspace suite,
synthetic CLI checks and independent fetch-summary model on Linux. The same
semantic gates were exercised locally on Windows during integration.

`integration-harvest-20261011-branches.json` retains all 157 discovered research
heads, their note paths and matching CLOSEOUT links from the full issue ledger,
plus both prep heads. All 45 core source/test candidate branches are reconciled
by reviewed production fixes or retained/rejected regression proposals. The
112 research-only entries were initially indexed: their source contracts and
experiments were not certified or automatically adopted. An index and a worker's
VALIDATED label do not substitute for primary reproduction or production proof.

The high-confidence core integration debt is substantially reduced. Continuing
with the existing CPU/RSP refetch composition and relevant research-only source
contracts; preserve unknown lineage and hardware/reference disagreements.

## Source-contract follow-up: controlled refetch and adjacent CPU copy

`add1943` reconciles the broader RSP/CPU refetch branch with the primary
unchanged-reference checkpoint gate: nineteen phases, 78 records, fifteen RSP
byte effects, two CPU Word effects, three foreign sinks and ten backing reads.
Seventeen histories are rejected and three causal forgeries fool payload-only
replay. Partial and unknown byte writers are preserved. The original seven-phase
result remains exact. Full core, fmt and strict workspace Clippy pass.

`607c88e` reconciles adjacent CPU-copy research after reproducing three new
false certificates in its verifier. Strict architectural continuity/address/
effect/type checks preserve the two intended LW/LWU-to-SW controls. Fourteen
independent instruction checkpoints agree, twelve measured adversaries and
seven separate synthetic regressions pass. Full locked workspace, fmt, strict
workspace Clippy and synthetic CLI pass. The unmodified branch verifier is
rejected and its bounded fixture is superseded.

The inventory now distinguishes four reconciled source contracts from the
108 still indexed-only entries. No reference implementation, branch-specific
workflow or manual build scaffolding is imported into production. These finite
contracts establish neither complete sensing nor lifetime, general dataflow,
hardware equivalence, whole-ROM or native closure. Milestone state is unchanged.

Canonical Actions run `38131501041` passes at `72e557a`, including the added
seven synthetic CPU-copy history regressions alongside the existing Rust/CLI/
model gates. This CI step checks the finite history contract; it does not run
the separate pinned ares neutrality fixture or certify sensor completeness.

`05ed9cd` reconciles the tested one-step XORI branch after reproducing the same
three continuity/address gaps in its verifier. Reuse the strict instruction/
scalar history validator under an explicit transform mode; keep copy mode
separate. Twenty independent instruction checkpoints agree; forty boundaries
and thirteen scalar effects yield the four intended transform certificates.
Thirteen measured forgeries and six synthetic regressions pass. XORI zero
preserves explicit transform identity; wrong-source equal bits do not certify.
Full core, fmt and strict workspace Clippy pass. The branch's bounded fixture/
verifier is superseded, with no broader producer/native milestone change.

Exact-head canonical Actions `38132454063` passes at `05ed9cd`, including all
seven copy and six transform synthetic contracts alongside the Rust/CLI/model
gates. Separate fresh pinned-reference neutrality checks remain required.

`a990cfa` reconciles CPU SW/SB/SWC1-to-SP context after reproducing accepted
selector/bank/bounds forgeries in the branch verifier. Observe actual decoded
instruction/GPR/FPR context instead of caller metadata, require bank/offset/
payload checks and replay guest bytes. The first reference run caught a host-
order IMEM snapshot error; fix capture through guest accessors and preserve the
gate. Corrected original/disabled/enabled/repeated eight-point checkpoints
agree; 21 records retain six attributed effects, one unscoped effect and one
CU1-denied/no-sink case. Sixteen measured forgeries and eight synthetic contracts
pass, as do full core, fmt and strict workspace Clippy. No ultimate ancestry,
census, hardware truth, lifetime or native milestone is inferred.
