# Direct integration receipt: source-bound CPU COP1 mutation replay

Date: 2026-10-11
Worker: `gpt56sol-direct-cpu-mutation-20261011`
Result at receipt creation: integration-ready pending the serialized main-write lease

## Base and source research

- Original base main: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`.
- Reconciled canonical main before this receipt: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.
- Source research branch: `research/cop1-store-mutation-gpt56sol` at `b95a51d4f5ec8fcba3b8ac85c222a11dafe05a49`.
- Durable research note: `research/ares-cop1-store-mutation.md`.
- Executable research fixture: `spikes/035-ares-cop1-stores/`.
- Pinned behavioral oracle: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.
- The source branch was treated as evidence only. No research branch was mechanically merged.

## Reproduced evidence against current main

The integration branch was explicitly reconciled with canonical main `539ff0ce72a98b296a8a28135fda6eab90a2f6ac` in merge commit `d845871d0a3ad2b2367c7d537a99304974503459` before rerunning validation.

Exact-reference Actions run `38151993531`, job `114507167720`, checked out exact pinned ares and reproduced:

- `PASS: COP1 FR payload-selection model and 100000 adversarial register cases`
- `model_sha256=3c5075ecc450af75d167dd3a225943c410e6dcc1e0f4c4877604f08f353aa285`
- `PASS: 192 repeated pinned-ares SWC1/SDC1 cases`
- `results_sha256=f85760603c11f51ede16e4a9d4b4965703c6a635e5b925401d8014494ab68e05`

The reproduced bounded facts are the research closeout facts, not broader hardware claims: FR=0 odd `SWC1` selects the high 32-bit lane of the paired even FPR, FR=0 odd `SDC1` aliases the paired even 64-bit value, FR=1 uses the named FPR, successful uncached stores mutate RDRAM backing immediately, successful cached stores mutate resident D-cache state at the immediate checkpoint, and the tested TLB/alignment/CU1 fault cases emit no concrete mutation.

## Adopted production invariant

`crates/plaid-core/src/cpu_mutation.rs` adds a bounded finite-history consumer with these fail-closed rules:

1. The complete source byte stream is authenticated by a caller-supplied SHA-256 receipt before replay.
2. Source ordinals are contiguous and instruction begin/effect/end events remain in one explicit scoped context; missing, duplicated, reordered or cross-context events reject.
3. The initial accepted architectural cause surface is decoded `SWC1`/`SDC1`. This verifies cause inside a captured history; it is not an opcode allowlist claimed to be a complete mutation census.
4. Raw FPR state plus FR mode are normalized to the actual semantic source lane/value. Equal values in another FPR do not change source identity.
5. Semantic payload bytes are derived from the selected FPR value and captured endian context.
6. Cached success must be represented as `cache_resident`; uncached success must be represented as `backing`.
7. Observer callback topology is not architectural truth. A semantic store may be represented by one effect or multiple nonempty fragments only when those fragments are non-overlapping, stay inside the store range, exactly cover every semantic byte once and match the normalized payload.
8. Faulted attempts must emit no byte effects and carry no successful destination/cache metadata.
9. Successful replay explicitly leaves mutation-census completeness, ultimate FPR ancestry, executable lifetime, hardware atomicity and native completeness false.

This is intentionally a consumer of authenticated finite evidence, not a producer, runtime fallback or CLOSED waiver.

## Adversarial regressions

The module includes focused regressions for:

- FR=0 odd-`SWC1` paired high-lane selection;
- fragmented `SDC1` callback topology;
- little-endian semantic payload normalization;
- equal-valued wrong-register decoys;
- wrong equal-length payloads;
- overlapping or missing byte fragments;
- backing effects incorrectly attributed to cached stores;
- mutation effects emitted by faulted attempts;
- clean fault attempts that certify nothing broader;
- deleted/reordered ordinals and forged complete-source hashes.

## Canonical validation

Reconciled integration head `d845871d0a3ad2b2367c7d537a99304974503459` passed Rust workflow run `38151993516`, job `114507167774`:

- exact decoder dependency pin: PASS;
- `cargo fmt --all -- --check`: PASS;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS;
- `cargo test --locked --workspace`: PASS;
- synthetic CLI checks: PASS;
- all retained CPU-copy, transform, SP/RSP, cache/TLB and fetch-summary source-contract/model checks in the canonical workflow: PASS.

A production-only final head is rerun through the same canonical Rust gates after temporary validation workflows are removed. Its final run is recorded in the issue #4 integration closeout so this receipt does not need a post-validation content-only rewrite.

## Rejected / superseded approaches

- Do not merge `research/cop1-store-mutation-gpt56sol` wholesale.
- Do not conclude mutation coverage from integer store opcodes or any finite opcode allowlist.
- Do not infer FPR source identity from payload equality.
- Do not infer a hardware transaction count or atomicity property from emulator callback count. Pinned ares exposes `SDC1` through one `Dual` backing call while pinned Mupen64Plus/Gopher64 research exposes two 32-bit implementation writes.
- Do not treat a cached architectural store as immediate RDRAM backing provenance; later dirty-line writeback is a separate causal event.
- Do not turn successful finite replay into a sensor-completeness, executable-lifetime or native-completeness certificate.

## Files changed by the production integration

- `crates/plaid-core/src/cpu_mutation.rs` — new finite source-bound CPU mutation replay and focused tests.
- `crates/plaid-core/src/lib.rs` — exports the production module while preserving concurrently integrated modules.
- `docs/STATUS.md` / `docs/NEXT.md` — bounded canonical-state note and remaining obligation, if still applicable after final main reconciliation.
- this receipt.

Temporary exact-reference/formatting/documentation workflows used only to validate or edit the isolated branch are removed before main integration.

## Limitations and remaining proof obligations

This integration does **not** prove or provide:

- a complete CPU/RSP/DMA executable-mutation census or the actual general mutation sensor below all opcode handlers;
- ultimate FPR dataflow ancestry (`LWC1`/`LDC1`, arithmetic, conversions, copies or prior producers);
- integer unaligned/conditional/vector/RSP/DMA/decompression mutation completeness;
- cached dirty-line writeback ancestry from resident mutation to later backing generation;
- general virtual/physical alias, TLB-generation or reverse-endian hardware completeness beyond the captured finite evidence;
- executable visibility through I-cache residency, stale state, lifetime boundaries or later consumption;
- real VR4300/RDRAM transaction atomicity or physical write topology;
- whole-ROM mutation closure, solver CLOSED status or native completeness.

Those obligations remain OPEN. Equal values, final memory state, matching addresses, cache tags, finite traces and compilation remain insufficient provenance evidence.
