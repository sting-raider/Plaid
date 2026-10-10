# LoadMapping / Region destination binding

Result: **REJECTED**

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`
Research branch: `research/load-region-destination-binding-gpt56sol`

## Question

Can a hand-edited or merged `ProgramMap` keep one real PI `copy_event` and matching
physical backing while moving the corresponding `LoadMapping.destination` to an
unrelated guest range, or changing the Region's canonical ROM source, and still
pass `ProgramMap::validate()`?

This matters because guest mapping identity, physical backing identity, and copy
event identity are distinct facts. Equal image/generation labels or equal bytes
must not let one concrete DMA witness authenticate a different executable mapping.

## Initial hypothesis

The hypothesis was that validation might only join a `LoadMapping` to a Region by
`(image, generation)` and then use that Region's `physical_start` in `copy_covers`.
If true, the same observed transfer could be replayed onto a different guest
range after hand editing.

The hypothesis was based on an initially truncated view of the validator and was
actively tested rather than assumed.

## Source audit

Current `main` already enforces the stronger invariant.

`crates/plaid-core/src/loads.rs::physical_start()` accepts physical mapping evidence
only from Regions that match all of:

- `image == load.image`;
- `generation == load.generation`;
- `range == load.destination`;
- `rom_offset == Some(load.rom_offset)`.

`record_load()` emits the same tuple into the new `Region` and `LoadMapping`.

Most importantly, `ProgramMap::validate()` independently repeats the same guest
range and ROM-source binding before accepting a `copy_event`; only then does it
call `copy_covers()` with that Region's physical start. Therefore a copy-backed
load cannot borrow physical provenance from a same-image/generation Region at a
different guest span or canonical source.

This is deliberately exact-range semantics, not value equality or virtual-alias
inference.

## Executable adversaries

`crates/plaid-core/tests/load_region_destination_binding.rs` constructs one
successful synthetic PI copy and one importer-shaped Region, then tests:

1. exact matching Region/LoadMapping control: accepted;
2. same DMA/ROM/physical facts but unrelated guest destination: rejected;
3. shifted smaller guest subrange with the same ROM and physical starts: rejected;
4. exact guest destination but Region canonical ROM source changed: rejected.

The first branch Actions run, `38073276279`, executed the tests against unmodified
production code. All focused adversaries passed and the complete `plaid-core` test
suite passed. That run stopped later only because the new research test needed one
`rustfmt` line wrap; no behavioral test failed.

## Reproduction

```sh
cargo test -p plaid-core --test load_region_destination_binding -- --nocapture
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --all-targets -- -D warnings
```

## Prior research composed

- ADR-0010: actual DMA copies are required before assigning executable sources.
- ADR-0017: physical overlap is evidence, not execution identity; guest and physical
  mappings remain distinct.
- ADR-0018: copy-event identity is distinct from a compiled executable snapshot and
  must be validated through typed DMA/physical-region facts.

The result also supports ADR-0009's broader fail-closed philosophy: this specific
mapping fact cannot be fabricated by deleting or moving only the guest-side load
row while retaining a plausible physical witness.

## Closed-world impact

This attack does **not** expose a current-main bug. The existing structural
validator already prevents a real PI copy identity from authenticating an unrelated
`LoadMapping.destination` or a Region with a different canonical ROM source.
Keeping this regression is useful because future provenance/lifetime composition
can rely on this narrow structural invariant without rediscovering it.

This result does not prove copy completeness, overlay unload/reload lifetime,
cache-visible executable lifetime, address-alias history, intervening CPU/RSP
writers, relocation/decompression provenance, or whole-ROM closure. Those remain
independent OPEN obligations.

## Integration recommendation

No production fix. The primary integrator may adopt the focused regression (or an
equivalent existing test) if explicit coverage of this invariant is desirable.
The research note is safe to retain as a negative result documenting an attempted
falsification and the exact validator contract that defeated it.
