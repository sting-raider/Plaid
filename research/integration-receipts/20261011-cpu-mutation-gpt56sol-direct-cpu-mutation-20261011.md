# Direct integration receipt: source-bound COP1 mutation history replay

Date: 2026-10-11
Worker: `gpt56sol-direct-cpu-mutation-20261011`

## Source research and canonical predecessor

- Original claim base: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`.
- Research branch: `research/cop1-store-mutation-gpt56sol` at `b95a51d4f5ec8fcba3b8ac85c222a11dafe05a49`.
- Durable note: `research/ares-cop1-store-mutation.md`.
- Executable fixture: `spikes/035-ares-cop1-stores/`.
- Exact pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

While this integration was being prepared, direct worker `gpt56sol-direct-cop1-mutation-20261011` landed canonical main `dd3f627d2c27f84611439ec1888ec4e3015e6bd2`. That commit provides the lower-level `cpu_mutation::verify_cop1_store_effect` completed-effect normalizer, including CU1-aware FR source selection, semantic payload checks, bounded destination checks and cache-resident/backing domain preservation.

The earlier version of this branch reimplemented that normalization inside a source-history replay. That duplicate implementation is **superseded and rejected**. The production candidate recorded here keeps canonical `cpu_mutation.rs` and its public tests untouched and adds only the missing source-authentication/chronology layer in `cpu_mutation_history.rs`.

## Reproduced evidence

The same immutable COP1 evidence was reproduced repeatedly while canonical main advanced through exception-root and TLBWI integrations. The post-TLBWI exact-reference run `38153016217`, job `114510186430`, checked out exact pinned ares and reproduced:

- `PASS: COP1 FR payload-selection model and 100000 adversarial register cases`
- model SHA-256 `3c5075ecc450af75d167dd3a225943c410e6dcc1e0f4c4877604f08f353aa285`
- `PASS: 192 repeated pinned-ares SWC1/SDC1 cases`
- result SHA-256 `f85760603c11f51ede16e4a9d4b4965703c6a635e5b925401d8014494ab68e05`

The validated facts remain bounded: FR=0 odd `SWC1` selects the high lane of the paired even FPR; FR=0 odd `SDC1` aliases the paired even 64-bit value; FR=1 uses the named FPR; successful uncached stores can produce backing effects; successful cached stores can produce resident D-cache effects; the tested fault cases produce no completed mutation. Emulator callback grouping is not promoted into a hardware transaction-count or atomicity claim.

## Adopted invariant

`crates/plaid-core/src/cpu_mutation_history.rs` consumes an externally complete finite JSON source with format `plaid-cpu-mutation-history-v1` and requires:

1. a caller-supplied SHA-256 receipt matching the complete source bytes;
2. one ordered event stream with contiguous ordinals beginning at 1;
3. non-nested instruction contexts whose identity is the begin ordinal;
4. a supported decoded `SWC1`/`SDC1` cause and aligned instruction PC;
5. fragment/end context identity matching the active begin;
6. fault outcomes with no concrete effect fragments;
7. successful outcomes with at least one non-empty concrete fragment;
8. one mutation domain across all fragments of a semantic effect;
9. virtual and physical fragment addresses contiguous in source order, rejecting gaps, overlap and reordered fragments;
10. semantic completed-effect identity derived from the source `end` ordinal, not callback count or a caller-chosen generation label;
11. final source/destination/CU1/FR/payload/alignment/RDRAM verification delegated to canonical `cpu_mutation::verify_cop1_store_effect`.

This intentionally permits either one 8-byte callback or multiple ordered fragments to describe one semantic `SDC1` effect without asserting hardware atomicity. Fragment ordinals are retained separately from the derived semantic completion ordinal.

## Adversarial tests

Focused Rust tests cover:

- fragmented `SDC1` normalization into one canonical semantic effect;
- one-fragment versus two-fragment callback topologies producing the same semantic mutation while retaining different fragment histories;
- equal-value wrong-FR-source rejection by the canonical primitive;
- missing, overlapping or reordered fragments;
- cross-domain fragment joins;
- fault attempts with forged effects;
- CU1-disabled successful-effect forgery;
- deleted/gapped ordinals;
- cross-context fragments;
- forged complete-source hashes.

All report-level proof flags for capture completeness, physical mapping, FPR ancestry, dirty writeback, hardware atomicity, executable lifetime and native completeness remain `false`.

## Validation history

Before the canonical lower-level normalizer landed, the source-history prototype passed full workspace validation multiple times, including post-TLBWI run `38153016223` / job `114510186793`, and the exact pinned reproduction above. Those runs are evidence for the history contract but are not sufficient for the final additive candidate because canonical code changed afterward.

The additive candidate is therefore rebuilt from canonical `dd3f627d2c27f84611439ec1888ec4e3015e6bd2` with canonical `cpu_mutation.rs` untouched and is rerun through:

- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- all retained synthetic/oracle checks in `.github/workflows/rust.yml`;
- the exact pinned COP1 reproduction when relevant.

The exact final tested head/run is recorded in issue #4 closeout after temporary validation helpers are removed.

## Files changed by the additive candidate

- `crates/plaid-core/src/cpu_mutation_history.rs` — authenticated finite history replay and adversarial tests.
- `crates/plaid-core/src/lib.rs` — one public module export while preserving canonical `cpu_mutation`, `exception_roots` and `tlb_history` state.
- `docs/STATUS.md` / `docs/NEXT.md` — bounded note about the new source-bound layer and still-open producer/composition obligations.
- this receipt.

Canonical `crates/plaid-core/src/cpu_mutation.rs` and `crates/plaid-core/tests/cpu_mutation.rs` are deliberately not modified.

## Remaining proof obligations

This integration does **not** prove:

- that the supplied finite history is a complete mutation census;
- completeness of CPU/RSP/DMA/decompression/relocation mutation sensing;
- physical mapping or alias truth beyond the supplied completed effect;
- ultimate FPR ancestry or storage-generation provenance;
- dirty resident-line writeback ancestry to later backing generations;
- I-cache visibility, stale-state composition or executable lifetimes;
- hardware write transaction topology or atomicity;
- whole-ROM mutation closure, solver CLOSED status or native completeness.

UNKNOWN remains UNKNOWN. Equal values, final memory equality, matching addresses, callback count, finite traces and successful compilation remain insufficient provenance evidence.
