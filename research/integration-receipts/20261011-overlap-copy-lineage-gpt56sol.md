# Integration receipt: captured CPU-copy storage-writer chronology

Date: 2026-10-11

Worker: `gpt56sol-direct-overlap-copy-lineage-20261011`

## Base and source research

- Canonical base inspected before the claim: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`.
- Primary source research: `research/overlap-cpu-copy-lineage-gpt56sol` at `30f79b201766356c65c37137b4b1ef964f265d0f`.
- Issue #4 research closeout: comment `6091204841`.
- Exact pinned ares revision used by the research: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- Historical research Actions run: `38005949906`, successful.
- Historical deterministic model report SHA-256: `a233772b218285ab7f69be3d4b2c6ed7f13cb8c22ba66cb01f730aa2e67e5523`.
- The research exercised 10,000 overlap histories: 4,987/4,987 forward-overlap histories contradicted naive initial-snapshot ancestry, 0/5,013 backward histories did, and 104 equal-payload controls retained identical final bytes with different roots.

The integration did not mechanically cherry-pick the research branch. The exact-pinned reference experiment remains research evidence; production code is an original Rust composition over the already-integrated strict CPU-copy source protocol.

## Independent reproduction against current production contracts

The integration first rechecked current `main` and rejected a different SP-DMA ingress candidate as already represented by `SpDmaStoreReceipt`; that rejected lane did not modify production.

For the selected overlap cluster, new Rust regressions reconstruct authenticated adjacent uncached Word-copy histories and independently exercise the research invariant through the production source parser:

- forward overlap retains prior captured destination writes at the later source addresses;
- backward overlap has no such prior captured writer at its source reads;
- equal-payload forward/backward histories remain causally distinguishable despite identical copied values;
- a same-value successful non-copy SW still mints a fresh captured storage generation;
- a declared phase boundary prevents accidental cross-phase writer reuse;
- altered/deleted writer identities, altered sink identities and forged certification flags fail complete-source report rechecking.

These tests deliberately do **not** infer that the latest captured writer is the ultimate source writer. The authenticated source records are not a complete mutation census. A retained captured-writer generation is chronological evidence inside this finite source; ultimate storage ancestry remains uncertified.

## Production invariant adopted

`crates/plaid-core/src/cpu_copy.rs` now provides a separate `plaid-cpu-copy-lineage-v0` report without changing the existing `CpuCopyReport` wire shape.

The new replay:

1. reuses the existing strict adjacent-copy or captured-definition verifier first;
2. replays all already-validated successful scalar Word stores in ordinal order;
3. mints a fresh phase-scoped `CapturedStorageGeneration` for every captured successful SW, including same-value rewrites;
4. records, for each accepted copy witness, the latest matching captured writer present at the source address and the witness's own captured destination generation;
5. clears local writer state across source phases;
6. re-derives the complete report during verification rather than trusting serialized lineage; and
7. keeps source-storage ancestry, mutation coverage, executable lifetime and native-complete flags false.

`None` is not promoted to initial/immutable storage. A present captured writer is not promoted to ultimate ancestry without a separately proven complete writer history.

## Research patches rejected or superseded

No research implementation was cherry-picked. The overlap branch's Python model, fuzz harness and exact-pinned ares fixture remain research-only evidence. General memcpy inference, cached-copy behavior, arbitrary transforms, DMA/device interleavings, global storage generations and executable-consumption/lifetime logic were intentionally not imported.

The initially investigated SP-DMA ingress integration was rejected as duplicate because current `sp_history.rs` already retains the relevant bounded source/sink receipts and ambiguity-to-UNKNOWN behavior.

## Production files changed

- `crates/plaid-core/src/cpu_copy.rs`
- `crates/plaid-core/tests/cpu_copy_lineage.rs`
- `docs/STATUS.md` (canonical state note)
- `docs/NEXT.md` (next obligation narrowed)
- `docs/DECISIONS.md` (bounded captured-writer chronology decision)
- this receipt

No solver, ProgramMap schema, progress milestone or native backend file is changed.

## Validation

Initial PR Actions run `38150771272` failed only the formatting gate. The reported rustfmt changes were applied exactly; no semantic workaround was used.

Corrected code head `ea163dbbbe0b0cb4da032d292f917616e0b7a5fe` passed canonical Actions run `38150926408` / job `114504043008`:

- exact decoder dependency pin: PASS;
- `cargo fmt --all -- --check`: PASS;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS;
- `cargo test --locked --workspace`: PASS, including all five new overlap/writer-chronology regressions;
- `python scripts/test_cli.py`: PASS;
- synthetic CPU-copy history contracts: PASS;
- synthetic XORI history contracts: PASS;
- CPU SP producer, RSP CPU IMEM composition, XORI cache visibility, PageMask remap, PI cache visibility, SP-DMA ingress, RSP store isolation, EntryHi and TLBR retained contracts: PASS;
- independent fetch-summary assignment oracle: PASS.

Reference semantics were not rebuilt during integration. The exact-pinned source research run `38005949906` remains the independently executed ares evidence; this production change is a fail-closed Rust consumer/composition of already-validated source records rather than a new hardware-semantics claim.

## Known limitations and remaining proof obligations

Still OPEN:

- completeness of CPU/device/RSP/DMA writer sensing;
- ultimate RDRAM/ROM/storage ancestry for a source read;
- cached source and cache-resident generation composition;
- arbitrary subword, 64-bit, transformed and non-adjacent copy dataflow;
- asynchronous/device interleavings and interrupt boundaries;
- decompression and relocation provenance;
- executable consumption and executable lifetime;
- whole-ROM mutation census and certificate verification;
- native lowering/completeness.

The new report therefore cannot by itself justify ProgramMap source promotion, CLOSED, or `native_complete=true`.

## Milestone effect

No `docs/progress.json` milestone moves between OPEN/PARTIAL/VERIFIED. This integration converts a validated finite overlap/storage-generation invariant into reusable production evidence, but the larger CPU-copy provenance and whole-ROM closure obligations remain open.
