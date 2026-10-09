# Solver fetch-capture count laundering

Result: **VALIDATED**

Worker: `gpt56sol-solver-fetch-capture-count-laundering-20261010`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/solver-fetch-capture-count-laundering-gpt56sol`

## Question

Can a retained raw fetch-capture identity be made proof-inert by deleting all typed `ObservedFetch` summaries and changing only `FetchCapture.fetch_count` from a nonzero value to zero?

This matters because `Scope::DeclaredStaticImages` may close a finite CFG, while raw fetch observations are intentionally blockers: they record execution without an established `CodeAddress` image/generation/lifetime identity.

## Source contract on current main

`crates/plaid-core/src/fetch.rs` keeps two different verification layers:

1. `import_fetch` hashes the complete raw stream, counts exact sequential fetch records, stores the resulting SHA-256 as the capture/evidence identity, and emits coalesced `ObservedFetch` summaries.
2. `verify_fetch_capture` reimports the complete raw stream and requires the retained capture metadata, evidence item and summaries to exactly equal the rederived result.

`ProgramMap::validate()` cannot perform step 2 because it does not receive the raw stream. It only checks internal map consistency. In particular, the sum of retained summary occurrence counts must equal `FetchCapture.fetch_count`.

Generic non-boot fetch streams legitimately permit zero fetch records: `import_fetch` initializes `count = 0`, and the footer is valid when its `fetch_count` is also zero. Boot captures are different: validation requires a nonzero count and the power-entry observation.

Therefore `fetch_count == 0` is not itself malformed and cannot safely be rejected at the schema layer.

Before this work, `solver::solve` only made raw fetches proof-relevant when `map.fetch_observations` was nonempty. It did not inspect a retained `fetch_captures` entry with zero summaries.

## Current-main counterexample

The focused regression constructs an otherwise CLOSED two-instruction static CFG (`J self; NOP`) and adds one valid generic fetch capture.

Control cases:

- capture count 1 + one `ObservedFetch`: map validates and solver is OPEN with `fetch_execution_identity_unknown`;
- delete only the observation while leaving count 1: `ProgramMap::validate()` rejects with `fetch summaries do not account for capture count`.

Attack:

1. start with the same count-1 capture and one observation;
2. retain the exact capture ID, raw-stream SHA-256 string and Trace evidence identity;
3. delete the `ObservedFetch` row;
4. change only `fetch_count` from 1 to 0;
5. `ProgramMap::validate()` succeeds;
6. current-main `solve(..., Scope::DeclaredStaticImages)` returns **CLOSED**.

A separately constructed schema-valid count-0 generic capture also returned CLOSED. The solver has no raw-source argument, so at solve time it cannot distinguish that legitimate empty capture from the laundered metadata above.

### Red receipt

Branch head before the fix: `b35be8b1f16b9b6f1b2213936c25c39181652db6`

GitHub Actions run `38004690736`, job `114070665165`:

- exact Rabbitizer pin guard passed;
- formatting passed;
- focused regression: **2 passed, 2 failed**;
- both failing assertions were `left: Closed / right: Open` for the zeroed-count laundering case and schema-valid empty-capture proof-obligation case.

The build used pinned Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

## Candidate repair

Commit `2756f85d0460739cb85368d423049c845d5d263c` adds one fail-closed solver condition:

- if `fetch_observations` is empty but `fetch_captures` is nonempty, add blocker `unverified_fetch_capture`;
- use the retained capture evidence IDs as blocker provenance;
- do not parse or trust human-readable evidence detail;
- leave schema-valid empty captures representable.

This deliberately does **not** claim that an empty raw stream is impossible. It says only that the current solver has no authenticated raw-source-verification fact with which to make such a retained capture proof-inert.

A future typed proof object could discharge this blocker after complete-source revalidation. Numeric count equality, SHA-shaped strings, or evidence prose must not do so.

## Adversarial matrix

`crates/plaid-core/tests/solver_fetch_capture_count.rs` now covers:

1. nonzero count with deleted summaries: validation rejects;
2. retained observed fetch: existing `fetch_execution_identity_unknown` blocker remains;
3. deleted summaries + count rewritten to zero while retaining the same capture identity: OPEN with `unverified_fetch_capture`;
4. schema-valid generic zero-fetch capture without raw source: OPEN with `unverified_fetch_capture`;
5. forged human-readable evidence detail claiming an empty capture is verified: still OPEN, and blocker provenance remains the capture ID.

This explicitly avoids deriving provenance from count/value equality or from descriptive strings.

### Green receipt

Hardened head: `6ef4744fa0d553a6c7fcf74de24f3b9b9b1c12f6`

GitHub Actions run `38004908809`, job `114071346800`:

- exact Rabbitizer pin guard passed;
- `cargo fmt --all -- --check` passed;
- focused regression: **5/5 passed**;
- full `cargo test -p plaid-core`: **108/108 passed** across unit/integration tests;
- `cargo clippy -p plaid-core --all-targets -- -D warnings` passed.

An earlier candidate-fix run `38004809233`, job `114071028267`, was also fully green before the forged-prose adversary was added.

## Prior research composed or challenged

This attacks ADR-0009's deletion/fabrication-resistance principle at a seam between already-existing components rather than adding a new opcode experiment:

- raw fetch observations intentionally remain finite execution evidence without image/generation/lifetime closure;
- fetch summary validation already prevents simple row deletion when a nonzero count survives;
- complete-source `verify_fetch_capture` already exists and correctly rebinds metadata to raw bytes;
- solver v0 separately rederives finite static CFG facts for deletion resistance.

The bug was the missing composition rule: a surviving raw-capture identity with no retained observations was treated as if the capture did not exist.

## Closed-world impact

For `DeclaredStaticImages`, retaining a fetch capture can no longer be laundered into a CLOSED certificate merely by deleting its fetch summaries and rewriting the mutable summary count to zero. The surviving capture remains a proof obligation until its complete raw source is authenticated and a future verifier supplies a discharge mechanism.

This preserves the distinction between raw-capture identity and the map's mutable summary metadata. A count of zero is a value, not a causal proof that no execution occurred in the named raw source.

This change does not advance `WholeRom` to CLOSED.

## Remaining gap

The ProgramMap is not a cryptographically self-authenticating event manifest. If an adversary deletes the entire fetch capture **and** its evidence item, the solver has no surviving fact from which to infer that an external capture ever existed. The local guard cannot solve complete-history authenticity without a higher-level signed/committed input manifest or equivalent expected-evidence contract.

Likewise, this work does not prove fetch-sensor completeness, emulator/hardware truth, executable generations, cache residency, retirement/lifetimes, dynamic mutation, exception roots, or whole-ROM closure.

A verified genuinely empty raw capture also remains conservatively blocking in the current solver because `verify_fetch_capture` produces no solver-consumable typed verification receipt. That is intentional fail-closed behavior, not a claim that the capture contained execution.

## Integration recommendation

**ADOPT** the small solver guard and regression semantics.

Near term, a retained raw fetch capture with zero summaries should keep finite-static closure OPEN. Do not make generic zero-fetch captures schema-invalid and do not parse evidence prose to discharge the obligation.

Longer term, introduce an explicit source-bound verification receipt (or pass a verified capture set into the solver) so a complete raw stream that is independently rehashed and proven empty can discharge `unverified_fetch_capture`. Keep that receipt bound to the raw SHA-256 identity, revision/profile and complete-source verification result.

## Reproduction

```sh
cargo fmt --all -- --check
cargo test -p plaid-core --test solver_fetch_capture_count -- --nocapture
cargo test -p plaid-core
cargo clippy -p plaid-core --all-targets -- -D warnings
```
