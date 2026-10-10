# LoadMapping to Region structural binding

Status: VALIDATED candidate fix under test.

## Scope

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`.

This experiment tests one structural provenance invariant: every retained `LoadMapping` produced by `loads::record_load` should remain bound to at least one executable `Region` with the exact same `(image, generation, rom_offset, destination)` tuple. It does not infer physical backing, copy-event identity, overlay lifetime, or executable lifetime.

## Hypothesis

`loads::record_load` always emits a matching Region for an accepted canonical executable snapshot, even when `copy_event` is absent. Current `ProgramMap::validate()` enforces that exact relation only inside its stronger `copy_event`/DMA coverage check. Therefore deleting or corrupting the Region attached to a legacy `LoadMapping { copy_event: None }` can leave a ProgramMap valid.

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

Before copy-event-specific validation, require at least one Region satisfying:

```text
region.image == load.image
region.generation == load.generation
region.range == load.destination
region.rom_offset == Some(load.rom_offset)
```

Return `load has no matching executable region` otherwise.

This is intentionally weaker than copy-event verification. It does not require `physical_start`, does not claim a DMA occurred, does not infer aliases from virtual addresses, and does not use byte/value equality as provenance. Existing `copy_event` validation still independently requires actual Trace provenance and a covering observed DMA/mapping.

## Falsification targets

- orphan legacy load must fail;
- wrong ROM source must fail;
- wrong guest start or extent must fail;
- exact relation with `physical_start=None` must remain valid;
- exact relation plus an unrelated mismatched Region must remain valid;
- existing copy-event/DMA tests must remain green.

## Closed-world impact

This bug does not currently manufacture `DeclaredStaticImages` CLOSED because retained loads themselves are outside that scope, and WholeRom remains OPEN. It does weaken the integrity of the evidence graph consumed by future copy/overlay/lifetime verifiers. A retained load must not outlive or borrow the structural executable Region that gives the snapshot its guest/source identity.

## Limitations

This invariant proves no completeness of executable copies, no physical backing identity, no DMA authenticity for legacy loads, no mutation census, no overlay retirement, no cache-visible executable lifetime, and no whole-ROM closure. Those obligations remain separate and OPEN.
