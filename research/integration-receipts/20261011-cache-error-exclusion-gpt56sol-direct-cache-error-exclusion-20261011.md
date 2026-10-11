# Direct integration receipt: VR4300 cache-error root exclusion

Date: 2026-10-11
Worker: `gpt56sol-direct-cache-error-exclusion-20261011`
Result at receipt creation: integration-ready, pending serialized main write

## Source research

- Initial claimed base main: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`.
- Validated source branch: `research/cache-error-root-sol` at `c52bf1845d89629116ce36fc0023260fe0c7635a`.
- Durable source note: `research/cache-error-root-obligation.md`.
- Source experiment: `experiments/cache-error-root-obligation/{model.py,driver.cpp,run.py}` on the research branch.
- Issue #4 research closeout: comment `6078802507`.
- Source exact-pin final-head Actions run `37915619202`, job `113770944214`, PASS; evidence artifact `11609637580`, SHA-256 `48f5ad67d2ea062b7e81513f89c40799a83e66bfa542a6b95eeb193f8fe2450b`.
- Exact reference revisions used here match `refs.lock.toml`: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`, Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`.
- Hardware authority: NEC VR4300/VR4305/VR4310 User's Manual `U10504EJ7V0UM00`, Appendix B.1.7 / Table B-1, with the CacheErr compatibility-state description in Chapter 4.

## Reproduced evidence

Research branches were treated as evidence, not code authority. A temporary integration-only fixture was staged on the direct-integration branch and then removed before canonical landing.

First integration reproduction at head `909d51595a290bf6a815c1e20afc3a08aa10e8bf`, Actions run `38151850906`, job `114506753500`, PASS:

- fail-closed certificate model executed twice byte-identically;
- compact model payload SHA-256: `aa7acaef54e2cb9965aff90aee1bedef8d25e5890e31a8be831ee0500f3124e3`;
- exact pinned ares guest fixture executed for BEV=0 and BEV=1;
- both cases retained CacheErr/readback zero, EXL/ERL clear, preset Cause/EPC/ErrorEPC unchanged, and entered no candidate exception vector;
- exact result JSON SHA-256: `87556a786d87fb5f812d267452fc0436b26a0e8b5bf04b0efe33aeae846afb3b`;
- pinned ares/n64-systemtest/Gopher64 source guards matched;
- evidence artifact `11706732434` was uploaded.

Current-main reconciliation added canonical exception-root work without importing it into this proof. Reconciled head `8ab2584eeade32a78b0915e017600708b599ddf5` was built from main `539ff0ce72a98b296a8a28135fda6eab90a2f6ac` plus this candidate. Exact-pin Actions run `38152189643`, job `114507747976`, PASS with the same model and result hashes; artifact `11706997061`.

Canonical Rust merge-context validation for the reconciled head used Actions run `38152192817`, job `114507758323`, PASS. It completed formatting, strict workspace Clippy, full workspace tests, CLI checks and every canonical synthetic evidence contract.

## Adopted invariant

For an explicit Nintendo 64 / NEC VR4300 target, Plaid may record the cache-error exception class as `ExcludedByTargetHardware` only because the target hardware documentation states that the VR4300 has no cache parity/error mechanism and the cache-error exception does not occur.

Production `plaid_core::root_policy` therefore:

- models the target explicitly as `RootTarget`;
- returns `ExcludedByTargetHardware` only for `Nintendo64Vr4300`;
- preserves the exact hardware authority and manual section in the report;
- leaves `GenericMipsIii` `Unresolved`;
- recomputes report contents from the typed target instead of trusting a serialized report;
- rejects schema additions and forged/deleted evidence fields through strict serde plus report re-verification;
- keeps `whole_rom_roots_certified=false` and `native_complete=false` in every result.

The research model's field named `closed=true` is scoped only to the single cache-error-class exclusion obligation. It is deliberately **not** imported as whole-ROM closure.

## Rejected / superseded approaches

- Rejected: `reference emulator did not transition => root impossible`. Emulator silence and finite traces are not exclusion evidence.
- Rejected: globalizing the VR4300 fact to generic MIPS III or VR4000/VR4200/VR4400 CPUs.
- Rejected: seeding a fictitious VR4300 cache-error handler merely because other MIPS implementations define such a vector.
- Rejected: weakening `WholeRom` solver blockers or treating this exclusion as exception-root census/reachability.
- Rejected: mechanically merging the research branch or shipping its exact-pin harness as production code. Temporary integration validation copies were removed after their Actions receipts were captured.
- Preserved separately: `plaid_core::exception_roots` resolves already-classified general/TLB root candidates; this cache-error exclusion neither supplies nor authenticates its exception classification/BEV/EXL/address-mode chronology.

## Production files

- `crates/plaid-core/src/root_policy.rs`
- `crates/plaid-core/src/lib.rs`
- `research/integration-receipts/20261011-cache-error-exclusion-gpt56sol-direct-cache-error-exclusion-20261011.md`
- canonical status/next/decision documentation if updated at final landing

## Tests / adversarial cases

Production unit tests cover:

- explicit VR4300 hardware exclusion while root completeness/native completeness stay false;
- generic MIPS III remaining unresolved;
- forged replacement of the hardware exclusion with emulator-silence reasoning being rejected by report verification;
- added/forged serialized fields being rejected.

Exact-pin integration validation additionally covers both BEV settings, sentinel exception state, deterministic repeated execution, exact source revisions and independent source guards.

Required canonical gates passed on reconciled head `8ab2584eeade32a78b0915e017600708b599ddf5` via run `38152192817`:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- canonical CLI and synthetic evidence checks in `.github/workflows/rust.yml`

## Limitations / remaining proof obligations

This integration excludes one nonexistent target-specific root class. It does **not** prove:

- interrupt, watch, reset, NMI, ordinary/TLB or other exception reachability;
- exception classifier provenance or BEV/EXL/address-mode chronology;
- handler executable-byte provenance, cache visibility, mapping identity or executable lifetime;
- complete mutation, overlay, relocation, RSP or indirect-target coverage;
- complete execution-root census;
- whole-ROM CLOSED status or native completeness.

Those obligations remain fail-closed and OPEN. No solver/native-complete gate is weakened and `progress.json` is intentionally unchanged.

## Final landing

This section is updated after the serialized MAIN-WRITE lease and canonical merge. At receipt creation the latest reconciled tested base was `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`; a later main advance requires reconciliation plus repeated focused/full validation before landing.
