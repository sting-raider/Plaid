# Direct integration receipt: snapshot-qualified restore epochs

Date: 2026-10-11

Worker: `gpt56sol-direct-restore-epoch-20261011-a7`

Cluster: analysis-time synchronized snapshot-load chronology for installed TLB state, active translation context, and resident instruction-cache state.

## Source research

- `research/savestate-tlb-cache-epoch-gpt56sol` note-final head `b502bc5f07dbdd88b8e8f521391dc13f90b98519`
- executable exact-pin research head `26e8fb421375a76497f0fe36de51c47001736107`
- `research/ares-savestate-tlb-cache-epoch.md`
- original exact-pin research Actions run `37932794526`
- exact ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Research branches were treated as evidence, not mechanically merged.

## Reproduced evidence on current main

The integration branch was validated after canonical main advanced to `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.

Fresh exact-pin Actions run `38152267899`, job `114507972690`, explicitly fetched and merged that main into the validation tree before running the retained reproducer. It then fetched exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` and passed:

- source guard: synchronized restore serializes the instruction cache, installed TLB entries, and EntryHi/ASID state without replaying TLBWI/TLBWR/fill operations;
- adversarial model with six forged-history rejections;
- the real exact-reference fixture;
- result payload SHA-256 `134004fc731a195152693394ca7a94583ddd879d2f3522e9f2d032b54c03b9f8`.

The retained model demonstrates both the changed-future and equal-value adversaries. In the equal-value case, later live mapping/context/residency generations have the same values as the saved snapshot, yet the subsequent load is a new causal boundary. Selecting those later generations by value equality is wrong; the restored state must instead receive snapshot-qualified restore roots.

The source guards also rechecked:

- CPU serialization source SHA-256 `8cc65fad5508ef9d85e6715c31a6b5c577a46c8967b8e57d594d4f20d0dd369d`
- system serialization source SHA-256 `284dde684315884a5ae5cfb7e5a9ce2e2d3e261a8cecaab508cd18a339425744`

## Adopted invariant

For this bounded compiler-time exploration source contract:

1. The complete supplied chronology must match a separately trusted SHA-256 receipt and have contiguous source ordinals.
2. Live component generations remain operation identities. Equal state digests do not collapse them.
3. A snapshot save has a unique snapshot identity and records exactly the three validated components: installed TLB state, active translation context, and resident instruction-cache state.
4. A load may use only a previously saved identity and must reproduce the saved three-component digest set exactly.
5. Every accepted load mints a fresh restore epoch. Its three components receive fresh restore-root identities bound to the same snapshot ID, save ordinal, load ordinal, and epoch, even when restored bytes/values equal an abandoned newer live generation.
6. After a load, current state points to those restore roots rather than to a value-matching live generation. Later live generations may supersede the restored component only through new authenticated source events.
7. Missing/reordered source events, unknown/reused snapshot identities, reused/reordered live generations, malformed digests, duplicate/missing component sets, and save/load state mismatches fail closed.

The report deliberately leaves `sensor_completeness_certified`, `full_system_restore_coverage_certified`, `executable_lifetime_certified`, and `native_complete` false.

## Production changes

- `crates/plaid-core/src/restore_epoch.rs`
- `crates/plaid-core/src/lib.rs`
- canonical state docs (`docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md`) are updated only at final reconciliation after the serialized main-write predecessor is known
- this receipt

A temporary branch-only exact-pin workflow was used to reproduce the reference result and is not intended for the canonical tree.

## Adversarial production tests

The module tests cover:

- changed future followed by one synchronized restore;
- equal-value newer live generations followed by restore;
- repeated load of the same snapshot minting distinct epochs;
- a post-restore live generation superseding the restore root only through a new generation event;
- reused/rewound live generation rejection even for equal values;
- unknown and reused snapshot identities;
- load component mismatch against the saved snapshot;
- save disagreement with already observed component state;
- missing and duplicate component state;
- deleted/reordered source ordinals;
- complete-source receipt mismatch.

## Validation

PR merge-tree Actions run `38152271308`, job `114507982788`, against canonical main `539ff0ce72a98b296a8a28135fda6eab90a2f6ac` passed:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- synthetic CLI checks
- retained CPU-copy, XORI, CPU-SP, RSP/IMEM, cache-visibility, PageMask-remap, PI, SP-DMA, RSP-store, EntryHi/TLBR and fetch-summary oracle contracts.

A first run failed only the formatting check; rustfmt output was applied and the complete rerun above was green. No failed semantic validation was waived.

Final post-reconciliation branch and canonical-main CI results are appended before closeout.

## Rejected / superseded work

- No research branch patch was mechanically merged.
- The earlier accidental `tlb_context.rs` commit `40058601905fccb8fa9a77ba07cac9aa6544f7bb` belongs to a separately rejected duplicate TLB-context lane and must not be landed as part of this cluster.
- Issue #4 later received a semantically duplicate restore-epoch claim (`gpt56sol-direct-restore-epoch-20261011`, comment `6110658244`) after this worker's earlier claim `6110646103`. The duplicate branch is not authority for this integration and must not create a second production restore-generation model.

## Limitations / remaining proof obligations

This is an analysis-time synchronized snapshot chronology primitive, not evidence that N64 hardware has savestates and not a complete emulator-state certificate.

Still OPEN:

- complete sensing of every save/load path and every executable-relevant serialized subsystem;
- validation of restored RSP IMEM/microcode, SP/PIF/hidden memory, device/queue state, frontend sidecars and other omitted state;
- producer completeness for installed TLB mappings, translation-context writers, cache fill/mutation/residency and backing identities;
- guest reset, NMI and power/reset chronology, which are separate architectural events;
- composition of a restore root with trustworthy physical backing, mapping identity, cache-visible bytes and executable lifetime;
- indirect-target, mutation-census and whole-ROM closure obligations;
- any CLOSED or `native_complete` promotion.

UNKNOWN remains UNKNOWN across every omitted component or missing source event. Equal bytes, equal register values, equal cache tuples, matching addresses, or a finite successful run are never used to reconnect provenance across a load.
