# Direct integration receipt: bounded decompression provenance replay

Date: 2026-10-11
Worker: `gpt56sol-direct-decompression-20261011`
Base validated against: `9154b30b12026c8c122f654d7fe90f0f67968dce`
Production code validation head: `2d12158f3de714ea985d7bb2437705e3d7fd42a2`

## Source research

- `research/decompression-lineage-receipt-gpt56sol` at `e3cf98a5414ba49afa695cbd890f98786d0ddc2c`.
- `research/decompression-ancestry-compaction-gpt56sol` at `7b7f2fb0e5faa802c38f403e559c4a87012cec5f`.
- Issue #4 research closeouts `6091116524` and `6096787689`.
- Primary harvest reviews retained on canonical main by `55fdc15514f03739f84f52ccd90fea2be3bf53d9` (`research/decompression-primary-review.md`) and `76d5770ddcfffaa6aae65be3979de893f899b494` (`research/decompression-compaction-primary-review.md`).

The lineage model reported 20,000 valid generated programs / 880,132 produced-byte writes. Its strict generation replay rejected all 80,000 lineage forgeries while value/hash-only substitutes accepted all 80,000 and value/write-shape replay accepted 70,000. Those numbers are retained as research evidence, not recreated as production truth. The primary reviews explicitly identified supplied invocation reuse, loose Python integer typing, undeclared-source literal reads, and empty/invalid operation boundaries as production-boundary holes.

## Reproduced evidence on current main

The production candidate was rebuilt as a clean direct child of canonical `9154b30b12026c8c122f654d7fe90f0f67968dce`, preserving the already-landed TLBWI, COP1 mutation and BEV=1 PIF-root integrations.

Focused GitHub Actions run `38153498606`, job `114511615154`, executed repository `rustfmt` and `cargo test --locked -p plaid-core decompression`; both passed. The focused suite covers overlapping self-feeding backreferences, equal-payload false ancestry, source/output aliasing with same-value overwrites, distinct same-value invocations, deletion/reordering, forged generations, out-of-bounds literals, empty backreferences, operation-digest tampering, strict integer typing and current-invocation source smuggling.

Canonical PR #28 Actions run `38153691008`, job `114512169468`, passed on production code head `2d12158f3de714ea985d7bb2437705e3d7fd42a2`:

- exact decoder dependency pin check: PASS;
- `cargo fmt --all -- --check`: PASS;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS;
- `cargo test --locked --workspace`: PASS;
- canonical CLI checks: PASS;
- all retained synthetic CPU-copy/XORI/SP/RSP/cache/TLB contracts: PASS;
- independent fetch-summary assignment oracle: PASS.

No fresh pinned-emulator run was required for this integration because the adopted primitive is an original, format-bounded causal receipt replay and does not depend on an emulator-specific decompressor semantic claim. Exact pinned-reference behavior remains necessary when a future guest decompressor recognizer/sensor claims a specific implementation or instruction chronology.

## Adopted invariant

For an already source-bound bounded literal/backreference transform receipt, payload equality is never provenance. Each produced byte must replay from the exact currently resident parent generation at the declared parent address. A produced byte receives a fresh ordered transform generation within the supplied invocation even when its payload equals the overwritten byte.

Overlapping backreferences therefore self-feed through previously produced output generations. Source/output aliasing is replayed against mutable generation-bearing memory, so an equal-value in-place output write changes the generation observed by a later literal read. The verifier requires exact declared source and output spans, a nonempty bounded operation stream, a complete ordered source snapshot, a complete one-write-per-output-byte history and an operation-stream digest. Deleted/reordered writes, wrong parents, wrong output generations, malformed operation boundaries and current-invocation generations in the starting source fail closed.

The upstream history digest and operation digest are integrity bindings only. They do not create causal origin. `VerifiedDecompression` is verifier-produced and non-deserializable; callers cannot inject a serialized `verified=true` equivalent.

## Rejected or superseded patches/assumptions

- The research Python receipt schema is not a production input contract. In particular, Python bool/int interchangeability and caller-selected transform identity are not trusted.
- Invocation freshness is not inferred from a supplied invocation ID or from equal/different payloads. A future authenticated invocation census must establish uniqueness/freshness.
- Compact ancestry summaries are not accepted without independently authenticated operation semantics. The production primitive replays the explicit bounded operation stream.
- Hash equality, final-state equality, destination shape and equal payloads do not substitute for parent-generation identity.
- The verifier does not infer that the supplied operation stream is every guest transform operation or that the supplied writes are every mutation.

## Files changed

- `crates/plaid-core/src/decompression.rs`
- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/tests/decompression_receipt.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- this receipt

No temporary formatter/reference workflow is part of the intended production diff.

## Limitations and remaining proof obligations

This integration verifies only internal causal consistency of an explicitly supplied, source-bound, bounded literal/backreference receipt. It does **not** prove or supply:

- authenticated transform-invocation freshness or complete invocation census;
- guest decompressor recognition or a complete operation/effect sensor;
- arbitrary decompression formats, transforms, relocation semantics or executable patch recognition;
- complete CPU/RSP/PI/SP mutation accounting outside the receipt;
- source storage ancestry beyond the supplied upstream-history binding;
- cache-visible executable state, TLB/mapping identity or stale-cache composition;
- overlay unload/reload chronology or executable lifetime;
- complete roots, indirect-target closure, whole-ROM closure or native completeness.

The verifier deliberately reports invocation freshness, operation census, effect census, executable lifetime and native completeness as false. Missing evidence must remain OPEN/UNKNOWN; no flag may waive those obligations.
