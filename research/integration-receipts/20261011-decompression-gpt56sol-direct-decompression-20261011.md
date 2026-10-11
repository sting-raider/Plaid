# Direct integration receipt: bounded decompression provenance replay

Date: 2026-10-11
Worker: `gpt56sol-direct-decompression-20261011`
Current canonical base at final reconciliation: `0e0e999b626dbda3f47cfd6aa89673618ae20350`
Current-main-derived code candidate: `3c9af281b8ca36ee40bd89716dd7fa71d91eb9da`
Result: **BLOCKED pending required local post-drift validation**

## Source research

- `research/decompression-lineage-receipt-gpt56sol` at `e3cf98a5414ba49afa695cbd890f98786d0ddc2c`.
- `research/decompression-ancestry-compaction-gpt56sol` at `7b7f2fb0e5faa802c38f403e559c4a87012cec5f`.
- Issue #4 research closeouts `6091116524` and `6096787689`.
- Canonical primary reviews retained by `55fdc15514f03739f84f52ccd90fea2be3bf53d9` and `76d5770ddcfffaa6aae65be3979de893f899b494`.

The validated lineage model covered 20,000 generated programs / 880,132 produced-byte writes. Strict generation replay rejected all 80,000 lineage forgeries. Value/hash-only substitutes accepted all 80,000, and value/write-shape replay accepted 70,000. These are research results, not production completeness claims. The primary reviews also identified caller-selected invocation reuse, loose Python integer typing, undeclared-source literal reads and empty/invalid operation boundaries as production-boundary holes.

## Reproduced evidence and validation chronology

The bounded production verifier was implemented independently rather than mechanically merging the research models. Focused run `38153498606` / job `114511615154` passed repository rustfmt plus `cargo test --locked -p plaid-core decompression`.

Full gate run `38153691008` / job `114512169468` passed exact decoder-pin checking, `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, canonical CLI checks, all retained synthetic contracts and the independent fetch-summary oracle.

After subsequent canonical integrations, the candidate was repeatedly reconciled. The most recent fully validated composition was the NMI-root main `60c5af29a9199ae207d487b4d791b13fb21ae708`: branch validation run `38154763246` / job `114515345870` passed exact decoder pin, formatting, focused decompression tests, strict workspace Clippy, full locked workspace tests, CLI, retained synthetic contracts 044-054 and the independent oracle. The temporary validation workflow was removed afterward; clean production head `926cf254fdb9aff6d72ef666e5657ff2e55e2af0` differed only by removal of that workflow.

Canonical main then advanced again to cached exception-root generation commit `0e0e999b626dbda3f47cfd6aa89673618ae20350`. The decompression candidate was reconciled onto that exact main as `3c9af281b8ca36ee40bd89716dd7fa71d91eb9da`, preserving `root_provenance` and `exception_root_generation`.

The coordination policy had meanwhile changed canonical Actions to manual-only specifically to preserve a local-validation policy and stop automatic Actions-minute use. This worker runtime has no `rustc` or `cargo`; explicit searches found no alternate Cargo binary, and the local shell cannot obtain a repository/toolchain through network access. Therefore the user-required post-main-change focused and full local validation cannot be executed here. No fresh PASS is invented, no temporary Actions workflow is used to evade the policy, and no MAIN-WRITE lease is acquired for this current-main-derived candidate.

No fresh pinned-emulator run is required for the adopted primitive itself because it is an original format-bounded causal receipt replay, not an emulator-specific guest decompressor recognizer. A future recognizer/sensor that claims specific guest implementation chronology must be validated against the exact pinned references.

## Proposed production invariant

For an already source-bound bounded literal/backreference transform receipt, payload equality is never provenance. Each produced byte must replay from the exact currently resident parent generation at the declared parent address. Every produced byte receives a fresh ordered transform generation inside the supplied invocation even when its payload equals the overwritten byte.

Overlapping backreferences therefore self-feed through previously produced output generations. Source/output aliasing is replayed against mutable generation-bearing memory, so an equal-value in-place output write changes the generation observed by a later literal read. The verifier requires exact declared source and output spans, a nonempty bounded operation stream, a complete ordered source snapshot, a complete one-write-per-output-byte history and an operation-stream digest. Deleted/reordered writes, wrong parents, wrong output generations, malformed operation boundaries and current-invocation generations in the starting source fail closed.

The upstream-history digest and operation digest are integrity bindings only. They do not create causal origin. `VerifiedDecompression` is verifier-produced and non-deserializable, so callers cannot inject a serialized `verified=true` equivalent.

## Rejected / superseded assumptions

- Research Python receipts are evidence, not a production input contract.
- Python bool/integer interchangeability is rejected by typed Rust IDs.
- Caller-supplied invocation identity does not establish freshness; an authenticated external invocation census is still required.
- Compact ancestry summaries are not accepted without independently authenticated operation semantics.
- Hash equality, final-state equality, destination shape and equal payloads never substitute for parent-generation identity.
- The supplied operation stream is not assumed to be every guest transform operation, and supplied writes are not assumed to be every mutation.
- The earlier prepared decompression ADR number `ADR-0104` is superseded because canonical `0e0e999b...` now uses ADR-0104 for cached exception-root resident-generation evidence. Canonical STATUS/NEXT/DECISIONS are intentionally left unchanged while this integration is BLOCKED; a successful future landing must allocate the next available ADR number from then-current main.

## Current candidate files

- `crates/plaid-core/src/decompression.rs`
- `crates/plaid-core/src/lib.rs` (one export, preserving all current canonical exports)
- `crates/plaid-core/tests/decompression_receipt.rs`
- this durable receipt

Canonical `docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` and `progress.json` are not changed by the blocked candidate.

## Remaining proof obligations

This primitive would verify only internal causal consistency of an explicitly supplied, source-bound, bounded literal/backreference receipt. It does **not** prove or supply:

- authenticated transform-invocation freshness or a complete invocation census;
- guest decompressor recognition or a complete operation/effect sensor;
- arbitrary decompression formats, transforms, relocation semantics or executable-patch recognition;
- complete CPU/RSP/PI/SP mutation accounting outside the receipt;
- source storage ancestry beyond the supplied upstream-history binding;
- cache-visible executable state, TLB/mapping identity or stale-cache composition;
- overlay unload/reload chronology or executable lifetime;
- complete roots, indirect-target closure, whole-ROM closure or native completeness.

The verifier deliberately reports invocation freshness, operation census, effect census, executable lifetime and native completeness as false. Missing evidence remains OPEN/UNKNOWN; no flag waives those obligations.

## Handoff

Fetch current `main`, reconcile `direct-integration/decompression-gpt56sol-direct-decompression-20261011` if main has moved, then run locally at minimum:

- `cargo test --locked -p plaid-core decompression`
- `cargo test --locked --workspace`
- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `python scripts/test_cli.py`
- current canonical synthetic contracts and independent oracle

Only after those pass on the then-current composition should the worker update canonical STATUS/NEXT/DECISIONS as justified, acquire a fresh MAIN-WRITE lease, refetch main and land without force. UNKNOWN remains UNKNOWN throughout.