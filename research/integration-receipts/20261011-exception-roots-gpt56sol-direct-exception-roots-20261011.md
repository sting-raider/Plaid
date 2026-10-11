# Direct integration receipt: bounded R4300 exception roots

Date: 2026-10-11
Worker: `gpt56sol-direct-exception-roots-20261011`
Result at receipt creation: integration-ready pending main-write lease

## Base and source evidence

- Base main: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`.
- Source research branch: `research/exception-vector-roots-gpt56sol` at `e58a31c88d42c3761844002f9c4e9042b427dd7a`.
- Durable source note: `research/ares-exception-vectors.md`.
- Executable research fixture: `spikes/019-ares-exception-vectors/`.
- Issue #4 validated closeout: comment `6062936102`.
- Original exact-reference Actions run: `37798306997`.
- Exact reference revisions are those in `refs.lock.toml`; the reproduced behavioral oracle used pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`. Pinned Gopher64 remains a documented disagreement for the 64-bit XTLB offset and is not treated as hardware authority.

## Independent reproduction against current main

The source experiment was inspected rather than cherry-picked. Its 28 guest-triggered cases distinguish ordinary/general entry, matching-invalid TLB entry, true TLB miss, BEV selection, EXL nesting, 32/64-bit kernel context and delay-slot cases. The production rule was independently encoded from those inputs rather than importing emulator code.

On integration head `56d4b94301147c7be3f1f75620d0660260dc5ba9`, temporary validation workflow run `38151077322`:

- fetched exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`;
- syntax-checked `spikes/019-ares-exception-vectors/run.py`;
- built and executed all 28 guest-triggered cases successfully;
- reproduced the durable `results.json` SHA-256 `9e9aff42c258177daa94f9de8be296c816735b67c2a4d0c04fdb89501d322de7`.

The branch-only exact-reference workflow was then deleted and is not a production dependency.

## Adopted production invariant

`plaid-core::exception_roots` now exposes a typed, deterministic root derivation from already-classified state:

- `General` and `TlbInvalid` select the general vector at base + `0x180`;
- a true `TlbMiss` with `EXL=0` selects base + `0x000` in 32-bit kernel context;
- a true `TlbMiss` with `EXL=0` selects base + `0x080` in 64-bit kernel context;
- a true `TlbMiss` with `EXL=1` selects the general vector at base + `0x180`;
- `BEV=0` uses base `0xffffffff80000000` and `BEV=1` uses base `0xffffffffbfc00200`.

The receipt retains the input and selected vector class. TLB-invalid and true-miss states therefore cannot be collapsed merely because they share an architectural TLB exception code.

This primitive intentionally does **not** claim exception reachability, provenance of the exception classifier, provenance of BEV/EXL/address-mode state, handler-byte provenance, cache/mapping lifetime, or completeness of execution roots.

## Production files changed

- `crates/plaid-core/src/exception_roots.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md` (ADR-0101)
- this receipt

No `docs/progress.json` milestone was changed because this integrates one bounded root-selection primitive, not a complete execution-root certificate.

## Focused regressions

Four Rust tests in `exception_roots.rs` cover:

1. replay of the validated 28-case vector-selection matrix;
2. TLB-invalid versus true-miss separation in 64-bit context;
3. nested true miss (`EXL=1`) returning to the general vector;
4. BEV base selection without collapsing vector class.

Delay-slot cases from the source matrix are replayed only for root selection. EPC/BD update behavior is deliberately not promoted into this primitive.

## Canonical Rust validation

Canonical PR workflow run `38151077459` on `56d4b94301147c7be3f1f75620d0660260dc5ba9` completed successfully after one earlier formatting-only failure was corrected. The successful run included:

- `cargo fmt --all -- --check` — PASS;
- `cargo clippy --locked --workspace --all-targets -- -D warnings` — PASS;
- `cargo test --locked --workspace` — PASS;
- `python3 scripts/test_cli.py` — PASS;
- all canonical synthetic CPU-copy, XORI, CPU/SP, RSP/IMEM, cache/remap, PI, SP-DMA, RSP-store, EntryHi/TLBR and fetch-summary checks — PASS.

The earlier run `38150953609` stopped at rustfmt because two match arms needed standard formatting; no semantic test had failed. Commit `56d4b94301147c7be3f1f75620d0660260dc5ba9` applied exactly that formatting correction and the full gate then passed.

## Research patches rejected or kept research-only

- No research branch was mechanically cherry-picked.
- The branch-only exact-reference CI workflow was removed after reproduction.
- The temporary documentation patch helper was removed after updating canonical docs.
- EPC/BD mutation semantics were not folded into this root selector.
- Interrupt, watch, reset, NMI and cache-error roots were not inferred from nearby exception behavior.
- Pinned Gopher64's absence of the `+0x80` XTLB branch remains an explicit reference disagreement rather than being silently reconciled.
- Finite reference execution is not promoted into whole-ROM completeness or hardware truth.

## Known limitations and remaining proof obligations

The following remain OPEN and must fail closed in any whole-ROM/native-complete certificate:

- prove which exception classes are actually reachable for the declared scope;
- authenticate the causal chronology of exception classification and BEV/EXL/address-mode state;
- compose numeric vector roots with executable handler-byte provenance, mapping/cache visibility and executable lifetimes;
- cover interrupt/watch and independently justified reset/NMI/cache-error roots;
- cover broader privilege/TLB contexts not established by the bounded 28-case matrix;
- preserve and investigate the ares/Gopher64 disagreement rather than choosing one reference as hardware truth;
- establish root-set completeness before any CLOSED/native-complete claim.

Milestone change: none. Solver/native-complete behavior is unchanged and remains fail-closed.
