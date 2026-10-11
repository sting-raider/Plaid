# Direct integration receipt: snapshot-qualified restore epochs

Date: 2026-10-11

Worker: `gpt56sol-direct-restore-epoch-20261011`

Initial base main: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`

First reconciled main during validation: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`

Second reconciled main after the independent TLBWI integration: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`

Hardened code head before final documentation: `84a9248c9f64627300f76b317eb0a33923ae282c`

## Source research

- `research/savestate-tlb-cache-epoch-gpt56sol` at `b502bc5f07dbdd88b8e8f521391dc13f90b98519`.
- Exact executable/reference head `26e8fb421375a76497f0fe36de51c47001736107`.
- `research/ares-savestate-tlb-cache-epoch.md`.
- Exact pinned ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- Research Actions run `37932794526`, job `113827386285`: SUCCESS. The job passed the adversarial model, exact-source contract guard, exact-reference fixture, durable-result hashing and artifact upload.
- Issue #4 research closeout `6081322237`.

## Reproduced evidence against current integration state

Current production main had no snapshot-qualified restore-epoch primitive or restore-root identity. The bounded validated reference result therefore remained unconsumed rather than contradicted by an existing implementation.

The production integration re-expresses the important counterexample as deterministic Rust adversaries:

- two loads of one snapshot with byte-identical TLB/context/I-cache digests mint distinct restore roots because the restore epoch differs;
- equal component values cannot compose across restore epochs;
- equal component values cannot compose across snapshot identities;
- deleted and duplicate component roots fail closed;
- a restored component digest that differs from its saved snapshot fails closed;
- unsaved snapshots, reused/reordered epochs, forged load-boundary metadata, source-receipt tampering, noncontiguous source ordinals, invalid snapshot identities and orphan component roots fail closed;
- empty/save-only histories issue no restore roots.

This directly preserves the validated research invariant that deserialization can reinstall state without replaying the historical live TLB/context/fill operations whose equal values might otherwise be selected as causal predecessors.

## Adopted invariant

For the bounded synchronized compiler-time restore scope validated by the exact pinned-reference experiment:

1. A snapshot save binds opaque digests for installed TLB state, active translation context and resident instruction-cache state to one explicit snapshot identity.
2. Every accepted snapshot load must mint a fresh, monotonically ordered restore epoch.
3. The load must provide exactly one restored root for each of those three validated components, bound to the same load ordinal, snapshot identity and restore epoch.
4. Each restored component digest must equal the digest captured by that snapshot.
5. A composed restored executable context is valid only when all three roots come from the same snapshot/load/restore epoch.
6. Equal component contents never repair a mixed-snapshot or mixed-epoch causal history.
7. Restore roots and reports cannot be constructed or deserialized by callers; they originate only from successful source-bound replay and expose read-only accessors.
8. The receipt authenticates the supplied finite source only. It does not certify sensor completeness, all serialized emulator subsystems, hardware savestate behavior, executable lifetime, whole-ROM closure or native completeness.

## Review hardening

A pre-lease code review found that the first public result structs exposed public fields and `Deserialize`, which would have allowed a caller to construct a `RestoreRoot` and invoke composition without first passing source inspection. That API was rejected before integration. The hardened implementation makes `RestoreRoot`, `RestoreEpoch`, `RestoreEpochReport` and `RestoredExecutionContext` fields private, removes public deserialization, and exposes read-only getters. The same review added a fail-closed requirement that a history must contain at least one synchronized load before it can issue any report roots.

## Rejected or superseded patches

An earlier broad TLB mapping/context integration attempt on PR #12 was closed unmerged after live issue #4 refresh exposed earlier, narrower active claims for TLBWI mapping generations and EntryHi/TLBR context generations. No code from that abandoned PR was adopted here.

The separately owned TLBWI generation integration subsequently landed on canonical main as `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5` (ADR-0102). This restore branch was reconciled onto that exact main and preserves its `tlb_history` module and documentation; restore epochs remain a higher-order load boundary rather than an alternate TLBWI model.

No research branch was mechanically merged. The production API is original Rust code derived from the validated invariant, not copied reference-emulator implementation.

## Files changed

- `crates/plaid-core/src/restore_epoch.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- this receipt

## Validation

Exact-reference evidence:

- Actions `37932794526` / job `113827386285`: SUCCESS at exact pinned ares. Passed source guard, adversarial model, exact-reference build/execution and result hashing.

Production branch evidence:

- PR #19 reconciled onto main `539ff0ce72a98b296a8a28135fda6eab90a2f6ac` at merge-reconciliation commit `201f003a78b4acf0c0a6ee04a2d54eb37536e774`.
- First CI pass correctly rejected unformatted Rust at formatting step; no later gates were treated as passed.
- Formatting fix head `56b379e5c627eef0f3ee6c30ba78f43ad63c4945`: Actions `38152227331` / job `114507860719` passed every canonical step.
- Receipt head `10a7c63ee1af0267db786b00dcf72e01d78fa124`: Actions `38152446585` passed.
- Hardened API head `84a9248c9f64627300f76b317eb0a33923ae282c`: Actions `38152785479` / job `114509496943` passed every canonical step, including:
  - `cargo fmt --all -- --check`;
  - `cargo clippy --locked --workspace --all-targets -- -D warnings`;
  - `cargo test --locked --workspace`;
  - synthetic CLI checks;
  - CPU-copy, XORI, CPU-SP-producer, RSP-CPU-IMEM, XORI-cache, PageMask-cache, PI-cache, SP-DMA-DMEM, RSP-store-isolation, EntryHi-cache and TLBR-cache retained contracts;
  - independent fetch-summary assignment oracle.
- The hardened branch was then merge-reconciled onto TLBWI canonical main `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5` at `62deb99fbf0383e1e37a147b1267abfdfc837fab`. A final canonical workflow is required after documentation is appended and before the main-write lease.

The local shell environment could not resolve `github.com` and did not contain the Rust toolchain, so local cargo output is not claimed. The repository's canonical GitHub Actions workflow supplies the required format/Clippy/workspace validation instead.

## Limitations

- This is a compiler-time exploration/savestate chronology primitive, not N64 hardware behavior.
- Only the three components established by the bounded exact-reference experiment are represented: installed TLB state, translation context and resident I-cache state.
- RSP state, queues/tokens, hidden/frontend memories, device state, external provenance sidecars and every other executable-relevant serialized component remain outside this bounded coverage unless separately modeled.
- Persistent/distributed snapshot-ID allocation is not defined here.
- A source SHA authenticates supplied bytes but does not prove the sensor/capture observed every required restore.
- The module does not yet connect restore roots to canonical TLBWI operation generations, context-writer generations or a complete cache-residency/lifetime solver.
- No ProgramMap solver blocker is waived and `native_complete` remains false.

## Remaining proof obligations

- compose canonical TLBWI mapping-operation evidence and EntryHi/TLBR context generations with restore roots without allowing pre-load abandoned-future generations to survive a load;
- connect resident I-cache restore roots to byte-level executable provenance and later invalidation/replacement chronology;
- define equivalent restore treatment for every executable-relevant serialized subsystem required by a declared exploration scope;
- bind snapshot/save/load capture identity to the complete exploration chronology, including forked/distributed exploration;
- keep reset/NMI guest-visible chronology distinct from emulator savestate load;
- only after those obligations compose may executable lifetime or whole-ROM CLOSED reasoning consume restore evidence.
