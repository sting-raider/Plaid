# Direct Integration Receipt: reset/cache lifetime transition replay

Date: 2026-10-11

Worker: `gpt56sol-direct-reset-cache-lifetime-20261011-r1`

Cluster: source-bound reset/NMI cache-residency vs backing-lifetime transition receipts

## Source research

- `research/reset-cache-lifetime-20261008` at `bd5c9d60a5c7424f4fc8e0f55d9d542ef096ee13`
- `research/reset-cache-lifetime.md`
- `spikes/018-reset-cache-lifetime/model.py`
- issue #4 research closeout `6062905910`
- exact pinned ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

The source research is evidence, not production authority. It establishes a bounded exact-pinned ares contract in which NMI preserves resident instruction-cache and backing-RAM state, system reset clears resident instruction-cache state while preserving backing RAM, and full/cold power reinitializes both. The research explicitly does not promote these reference-specific effects to universal VR4300/N64 hardware truth. Save-state restore is a separate non-monotonic chronology operation and is intentionally excluded from this production primitive.

## Reproduced evidence

Before adopting a production abstraction, the retained deterministic reset/cache lifetime model was replayed against the current repository evidence. Its documented checkpoints were reproduced:

- initial/stale/NMI/ERET resident-cache checkpoint SHA-256: `4400cfd587a469a9e8fa4757a3042115ada231d62499943fddc35d296ce4c211`
- RAM after backing mutation SHA-256: `8a2545e25ad42c710dc6c78c43afea5c55be2330332f00638db15b2914537a31`
- post-system-reset/refill resident-cache checkpoint SHA-256: `992261360b5cd14d4a2d1a6d84a36bfbb865d0a77b2befab5eff3cdc0c8c328c`
- later backing-RAM checkpoint SHA-256: `8df03d19bcc929629b617f7d04500b3c0612d0cf9caa4d6eb0e8fc2aaa735bec`

The replay therefore reproduced the important asymmetry used here: a reset-like transition can end resident-cache lifetime without ending backing-byte lifetime, while an NMI-like transition can preserve both. This receipt does not claim a fresh hardware experiment or a byte-identical rebuild of the historical research checkout; the exact reference binding remains the pinned ares revision and the retained research receipts.

## Adopted invariant

Production now has a deliberately small source-bound replay contract:

- the complete finite transition source must match an externally supplied SHA-256 receipt;
- the source format and reference profile are fixed to `plaid-reset-cache-lifetime-v0` and `ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-reset-cache-v0`;
- transition ordinals must be contiguous, so deletion/reordering does not silently produce a valid replay;
- NMI, system-reset and full-power records must carry exactly the resident/backing reinitialization effects established by that pinned profile;
- resident-cache generation and backing generation are advanced independently from authenticated reinitialization operation occurrence, never from payload equality or final-state comparison;
- repeated same-kind/same-value operations remain distinct generations where the operation actually reinitializes that domain;
- save-state restore is rejected rather than coerced into a monotonic reset generation;
- report verification replays the complete source and exact-compares the derived report.

The report explicitly leaves `transition_census_certified`, `hardware_semantics_certified`, `executable_lifetime_certified` and `native_complete` false. This primitive therefore cannot waive missing reset/NMI producers, sensor completeness, cache/backing provenance, executable consumption, or whole-ROM closure.

## Rejected or superseded approaches

- No research branch was merged mechanically.
- No emulator-specific behavior was declared hardware truth.
- No single reset/NMI generation collapses resident-cache and backing lifetime.
- No equality of bytes, tags, addresses, before/after values or final snapshots is accepted as provenance or as evidence that an operation did not occur.
- No current/latest backing state is used to explain stale resident instruction bytes.
- Save/restore chronology is not folded into this monotonic replay; active restore-epoch work owns that separate composition problem.
- No reset/NMI event detector, producer identity, interrupt/exception root proof, mapping/TLB proof, PI/D-cache/I-cache writer join, mutation census, solver promotion or native-complete gate is added here.
- The temporary branch-only Rust workflow trigger used to execute canonical checks after `main` became `workflow_dispatch`-only is validation scaffolding and must not land on `main`.

## Files changed by the integration candidate

- `crates/plaid-core/src/reset_cache_lifetime.rs`
- `crates/plaid-core/src/lib.rs` (module export only)
- this receipt

No milestone is changed, so `docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` and `progress.json` are intentionally unchanged by this cluster.

## Adversarial regressions

The module tests cover:

- NMI preserving both generations;
- system reset cutting resident generation while preserving backing generation;
- repeated system resets minting distinct resident generations;
- full power cutting both domains;
- forged NMI residency cuts;
- forged system-reset backing cuts;
- incomplete full-power effects;
- missing/reordered ordinals;
- restore masquerading as a monotonic transition;
- wrong source receipt or reference profile;
- tampered derived reports;
- proof flags remaining false even for a syntactically valid finite source.

## Validation receipts

First full validation attempt:

- branch head: `ae0782c7fa178f5de55e64446a58b230e4a70fe6`
- Actions run: `38154536439`
- job: `114514673657`
- result: **FAILED** at `cargo fmt --all -- --check`; later gates were correctly skipped.
- action taken: applied exactly the rustfmt diff; no semantic test failure was waived.

Green validation after formatting:

- tested branch head: `e77cba4b0b8af35f261953bade7e7d2f1cda4b36`
- Actions run: `38154604136`
- job: `114514871636`
- result: **SUCCESS**
- exact Rabbitizer pin guard: PASS (`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`)
- `cargo fmt --all -- --check`: PASS
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS
- `cargo test --locked --workspace`: PASS
- canonical CLI and every retained synthetic CPU-copy/XORI/SP/RSP/cache/PageMask/PI/ASID/TLBR contract: PASS
- independent fetch-summary realizability oracle: PASS

The branch is subsequently reconciled onto whatever canonical `main` exists immediately before the MAIN-WRITE lease, and the complete gate is rerun if canonical main moved. The final issue #4 closeout records that final tested head and resulting main commit.

## Limitations and remaining proof obligations

This integration establishes only a finite source-replay primitive for a specific pinned-reference transition profile. It does **not** establish:

- a complete reset/NMI/full-power occurrence census;
- hardware-universal reset/NMI cache semantics;
- producer identity, reset timing or reset/NMI reachability;
- PIF/root executable-byte provenance beyond independently supplied root/source receipts;
- physical backing identity or alias/TLB/PageMask/context generations;
- cache-line fill origin, replacement, invalidation or stale-resident provenance outside the supplied transition contract;
- save-state restore chronology or restored older generations;
- CPU/RSP/PI/DMA mutation completeness;
- decompression, relocation or overlay lifetime completeness;
- indirect-target or pointer-table lifetime closure;
- exception/interrupt/root-set completeness;
- executable-consumption lifetime completeness;
- WholeRom CLOSED or native completeness.

Any missing composition evidence remains UNKNOWN/OPEN.