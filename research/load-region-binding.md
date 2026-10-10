# LoadMapping to Region structural binding

Status: VALIDATED.

## Scope

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`.

This experiment tests one structural provenance invariant: every retained `LoadMapping` produced by `loads::record_load` should remain bound to at least one executable `Region` with the exact same `(image, generation, rom_offset, destination)` tuple. It does not infer physical backing, copy-event identity, overlay lifetime, or executable lifetime.

## Hypothesis

`loads::record_load` always emits a matching Region for an accepted canonical executable snapshot, even when `copy_event` is absent. Base `ProgramMap::validate()` enforces that exact relation only inside its stronger `copy_event`/DMA coverage check. Therefore deleting or corrupting the Region attached to a legacy `LoadMapping { copy_event: None }` can leave a ProgramMap valid.

## Producer audit

`crates/plaid-core/src/loads.rs` constructs `LoadMapping { rom_offset, destination, image, generation, ... }` and later inserts `Region { image: load.image, generation: load.generation, range: load.destination, rom_offset: Some(load.rom_offset), ... }` before validating the result. Physical backing is optional and deliberately independent.

`ProgramMap::validate()` on the base validates a load's destination, ROM bounds, evidence, and image. Only when `copy_event` is present does it search for a Region with exact image/generation/destination/ROM source and then require a covering `ObservedDma` using that Region's physical mapping.

## Baseline reproduction

Branch regression: `crates/plaid-core/tests/load_region_binding.rs`.

Expected-red Actions run: `38095495426`, job `114340423401`.

The run compiled pinned Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`. Results on untouched validation logic:

- exact legacy load + exact Region + no physical mapping: PASS control;
- delete the exact Region while retaining the load: validator incorrectly accepts, regression FAIL;
- replace with same-image/generation Region using a different canonical ROM offset: validator incorrectly accepts, regression FAIL;
- replace with same-image/generation Region using a different guest start: validator incorrectly accepts, regression FAIL.

Baseline result: 1 passed / 3 failed, as expected for the reproducer.

The final focused matrix additionally checks wrong extent and an unrelated Region decoy. The intended invariant is existential: an exact matching Region is required, but unrelated Regions do not invalidate an otherwise sound relation.

## Candidate fix

Production commit: `dd931db15dd1a28c6542274f93283b9dcb724b58` (`fix: bind load mappings to executable regions`).

Before copy-event-specific validation, require at least one Region satisfying:

```text
region.image == load.image
region.generation == load.generation
region.range == load.destination
region.rom_offset == Some(load.rom_offset)
```

Return `load has no matching executable region` otherwise.

The production change is eight inserted lines in `crates/plaid-core/src/program.rs`. It is intentionally weaker than copy-event verification. It does not require `physical_start`, does not claim a DMA occurred, does not infer aliases from virtual addresses, and does not use byte/value equality as provenance. Existing `copy_event` validation still independently requires actual Trace provenance and a covering observed DMA/mapping.

## Falsification and validation

Final candidate Actions run: `38095619608`, job `114340784780`.

The workflow applied the candidate guard to branch head `fab6cb8e2798bb4f726ad0378d282012f6c00442`, ran all checks successfully, then committed the exact tested `program.rs` diff as `dd931db15dd1a28c6542274f93283b9dcb724b58`.

Evidence:

- focused `load_region_binding`: 6 passed / 0 failed;
- orphan legacy load: rejected;
- wrong ROM source: rejected;
- wrong guest start: rejected;
- wrong extent: rejected;
- exact relation with `physical_start=None`: accepted;
- exact relation plus unrelated mismatched Region decoy: accepted;
- full `cargo test --locked -p plaid-core`: 109 passed / 0 failed across unit, integration and doc-test targets;
- original `loads.rs` suite: 5 passed / 0 failed, including concrete copy-event reload/DMA behavior and explicit alias controls;
- `cargo fmt --all -- --check`: passed;
- `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`: passed;
- pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` was compiled in both red and green runs.

An earlier candidate run `38095605166` also completed focused/full/fmt/clippy successfully; its job was marked failed only because its final push raced a newer documentation commit. No test/check failed in that run. The later run above started from the newer branch head and committed successfully.

Base-to-tested-fix comparison is 7 commits ahead / 0 behind. Only the branch workflow, eight-line `program.rs` guard, focused regression, research note, and candidate patcher differ from canonical base.

## Prior research composed or challenged

- ADR-0009: removing producer-required evidence must not fabricate a valid/closable history.
- ADR-0010: canonical executable-load provenance must remain structurally tied to the executable image/source it establishes.
- ADR-0017: physical backing and alias identity remain explicit and are not inferred by this guard.
- ADR-0018: copy-event causal identity remains separate from the load snapshot/generation; this guard applies even when that stronger causal identity is unavailable.
- Completed Region-to-Overlay hardening is complementary: that work binds Region to Overlay source/span; this work binds LoadMapping to its producer-mandated Region before overlay/lifetime composition.
- Completed DMA-event uniqueness remains complementary and stronger only when a `copy_event` exists.

## Closed-world impact

This bug does not currently manufacture `DeclaredStaticImages` CLOSED because retained loads themselves are outside that scope, and WholeRom remains OPEN. It does remove a deletion/fabrication ambiguity from the evidence graph consumed by future copy/overlay/lifetime verifiers. A retained load can no longer outlive or borrow a structurally different executable Region while still passing ProgramMap validation.

## Limitations

This invariant proves no completeness of executable copies, no physical backing identity, no DMA authenticity for legacy loads, no mutation census, no overlay retirement, no cache-visible executable lifetime, and no whole-ROM closure. Those obligations remain separate and OPEN.

## Reproduction

Red baseline is preserved by commit `cdb747e60f280603ca4fb552f08846f8162878ea` plus the initial branch workflow; run `38095495426` records the expected failure.

Green validation commands used by run `38095619608`:

```sh
python3 spikes/load-region-binding/apply_candidate_fix.py
cargo test --locked -p plaid-core --test load_region_binding -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```
