# Direct integration receipt: RSP IMEM installation lifecycle

Date: 2026-10-11
Worker: `gpt56sol-direct-rsp-imem-install-20261011`
Claim base: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`
Cluster: source-bound bounded RSP IMEM installation request lifecycle and exact-effect ownership

## Source research

- `research/rsp-imem-install-lifetime-gpt56sol` @ `a162772fb561f54c2c854bba4fca8178bc09c1f3`
- exact pinned-reference validation commit `9e236ca7551c3ba4b1346c9fa5b06dabb89523b6`
- `research/rsp-imem-install-lifetime.md`
- `research/sp-dma-lifecycle.md`
- `research/rsp-imem-dma-direct-write-interleave.md`
- `spikes/043-ares-rsp-imem-install-lifetime-gpt56sol`
- `refs.lock.toml` ares pin `9408cb43d4948fc3ea6e152a307a34348df3fe04`

The harvest classified the installation-lifetime branch as `indexed_only` with no integration commit. Current `sp_history.rs` already retained individual forward SP-DMA sink receipts, so this integration does not duplicate those receipts. It adds the missing bounded request-container replay that relates measured IMEM effects to actual promoted request identity and preserves later per-byte writer supersession.

## Reproduced evidence on current main

Before adding production code, commit `6d8c298944705aa260daf2c2bb3ead11a0ebddaa` added only an independent test-local reducer in `crates/plaid-core/tests/rsp_imem_install_reference.rs`. Against the then-current main merge candidate it reproduced:

- six strictly ordered promoted/completed requests;
- a count/skip request containing two measured IMEM row effects;
- an intervening same-value CPU IMEM write superseding only its four touched bytes;
- a later DMA row leaving those earlier CPU-owned bytes untouched where it did not overlap;
- two identical-payload installs retaining distinct request/writer generations;
- modulo-IMEM wrap as distinct measured effects at `0xff8` and `0x000`;
- direct completed-request handoff without requiring BUSY to fall between requests;
- rejection of wrong-active-request, reused request generation, missing completion, and reordered event history.

GitHub Actions run `38151654768`, job `114506181775`: **SUCCESS**. It passed exact dependency-pin validation, `cargo fmt --all -- --check`, strict workspace Clippy, full locked workspace tests, CLI checks, and all retained synthetic contracts. This reproduction preceded the production implementation.

The original executable reference experiment also remains independently green at exact pinned ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`: research Actions run `37915747585` at commit `9e236ca7551c3ba4b1346c9fa5b06dabb89523b6`: **SUCCESS**. No emulator behavior was silently generalized beyond the measured source contract; the known ares versus Mupen/Gopher FULL-policy disagreement remains unresolved hardware-wide.

## Adopted invariant

`plaid_core::rsp_imem_install` accepts one separately authenticated complete JSON observation source and replays only the following bounded facts:

1. event ordinals are contiguous;
2. promoted request generations are strictly monotonic and cannot overlap;
3. a DMA sink belongs only to the currently active promoted request;
4. each concrete completed DMA sink creates a fresh eight-byte IMEM writer generation with 12-bit bank wrapping;
5. each concrete completed CPU IMEM sink creates a fresh four-byte writer generation, even when its value equals the bytes already present;
6. request completion must match the active request and must have at least one measured DMA sink;
7. current byte ownership is derived from event chronology, so later writers supersede only bytes they actually touch;
8. the caller-supplied SHA-256 receipt authenticates the entire source; report verification replays that source and exact-compares the typed report.

The request descriptor fields (`initial_pbus`, `initial_dram`, `length`, `count`, `skip`) are retained as observed request metadata. Production does **not** synthesize unobserved DMA effects from them and therefore does not turn a descriptor into mutation-completeness evidence.

## Rejected / superseded patches and shortcuts

- No mechanical merge or cherry-pick of the research branch.
- No request content hash or equal payload is treated as writer identity.
- No final-byte equality is treated as proof that an intervening operation did not occur.
- No BUSY edge is used as request identity or completion boundary.
- No ares pending/FULL overwrite policy is promoted to hardware truth; Mupen/Gopher disagreement is preserved.
- No request is treated as an atomic executable-residency generation.
- No RDRAM numeric source address is treated as byte provenance or backing ancestry.
- No reverse IMEM-to-RDRAM DMA lineage is included; that is a separate active integration lane.
- No solver, ProgramMap, certificate, or native-lowering gate is weakened.

## Files changed

- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/src/rsp_imem_install.rs`
- `crates/plaid-core/tests/rsp_imem_install_reference.rs`
- `crates/plaid-core/tests/rsp_imem_install.rs`
- this receipt

`docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` and `progress.json` are intentionally unchanged. This bounded consumer changes neither milestone/closure state nor an architectural decision: current `docs/NEXT.md` already records that SP lifecycle identity requires actual promotion/pending mutation evidence, grouped count/skip rows and modulo-bank spans while BUSY/length commits are insufficient; ADR-0059 already preserves the same request-lifecycle and FULL-policy disagreement. Native completeness remains false.

## Production validation

Production head `728a554475b2ba2db774ed7371c697fd84614699` was tested through PR #13 as a GitHub merge candidate against canonical main `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.

GitHub Actions run `38152128790`, job `114507567617`: **SUCCESS**.

Passed:

- exact pinned Rabbitizer dependency guard;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- synthetic CLI checks;
- CPU-copy, XORI, CPU-SP producer, RSP-CPU-IMEM composition, cache visibility, PageMask remap, PI cache visibility, SP-DMA DMEM ingress, RSP store isolation, EntryHi/TLBR cache-reactivation contracts;
- independent fetch-summary assignment oracle;
- focused RSP IMEM request/effect ownership, same-value generation, modulo-wrap, source/report tamper, malformed identity/order, and fail-closed closure-flag regressions.

Earlier production attempts `38151866189` and `38151908916` failed at formatting only and were not accepted as validation. The formatting defect and a focused-test wrap-index error were corrected before the successful run above.

## Canonical-main reconciliation

After the serialized TLBWI integration advanced canonical main to `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`, this cluster was rebuilt directly on that exact head rather than merging exploratory history. PR #29 head `85853d8f4e71f2ec056d6194a3a8183137edfec9` passed GitHub Actions run `38153033614`, job `114510236550`: **SUCCESS**, including the exact dependency pin guard, format, strict workspace Clippy, full locked workspace tests, CLI, every retained synthetic contract and the independent fetch-summary assignment oracle.

While the mandatory main-write lease remained with the COP1 mutation worker, canonical main then advanced legally to `dd3f627d2c27f84611439ec1888ec4e3015e6bd2`. This integration was rebuilt again directly on that commit, preserving the newly integrated `cpu_mutation` API as well as prior exception/TLB state. The resulting branch contains only the four production/test paths plus this receipt relative to that canonical base. No main write occurs until this receipt-bearing reconciliation itself passes the full gate and the current lease is formally released. The issue #4 closeout records the final receipt-head and post-main CI run IDs, avoiding a self-referential receipt edit after validation.

## Limitations

This abstraction authenticates and checks internal chronology of the supplied bounded observation source. It does not prove that the sensor captured every relevant operation or that the observed RDRAM source bytes have known ancestry. It does not establish hardware-wide SP scheduling/FULL policy, reset/save-state continuity, executable lifetime boundaries, instruction-cache visibility, mapping/TLB context, or RSP execution reachability.

All report proof flags remain fail-closed:

- `source_backing_certified = false`
- `mutation_coverage_certified = false`
- `executable_lifetime_certified = false`
- `rsp_closure_certified = false`
- `native_complete = false`

## Remaining proof obligations

- compose each DMA source range with trustworthy RDRAM physical-backing and writer ancestry;
- prove capture/mutation completeness for CPU, RSP, PI/SP DMA, transforms, relocations, overlays, resets and restored state;
- compose request effects with executable lifetimes and cache-visible IMEM state rather than treating request identity as residency identity;
- establish complete RSP execution roots and microcode reachability;
- resolve or conservatively bound scheduler/FULL-policy disagreements where they matter to a declared scope;
- cover reverse IMEM-to-RDRAM egress separately;
- compose with mapping/cache/control-flow facts before any CLOSED decision;
- retain WholeRom and native-complete status as OPEN until all required obligations are independently discharged.
