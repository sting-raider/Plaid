# Executable region physical-start alignment

Status: VALIDATED

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/region-physical-alignment-gpt56sol`

Issue #4 claim: worker `gpt56sol-region-physical-alignment-20261010`, claim comment `6090973292`.

## Question

Can an executable `Region` carry a word-aligned guest code range but an explicitly unaligned `physical_start`, and can that malformed affine guest-to-physical mapping participate in a `CLOSED` static-scope result?

This is deliberately narrower than the separately claimed physical-span-overflow question. It asks whether the local base of one explicit executable physical mapping is itself a valid instruction-word mapping.

## Hypothesis

`GuestRange::validate(true)` requires executable guest start/size alignment, but current `ProgramMap::validate()` did not impose the corresponding 4-byte alignment invariant on `Region.physical_start`. If so, a normal aligned static image could be assigned `physical_start = 1`, pass validation, and still report `CLOSED`.

For an affine executable mapping of R4300 instruction words, an aligned guest word cannot soundly map to an unaligned physical word base. The mapping should be rejected before physical alias, copy, provenance, or closure reasoning can consume it.

## Current-main reproduction

The fixture is intentionally ordinary:

- guest base `0x80000000`;
- two words: `J 0x80000000` (`0x08000000`) followed by `NOP`;
- declared static-image scope;
- no payload trick, transform, or inferred provenance;
- explicit `physical_start = 0x00000001` for the adversarial case.

On the canonical base, Actions run `38004557286`, job `114070242859`, compiled against the pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`. The adversarial image reached the solver and returned `ClosureStatus::Closed`. The regression failed exactly because `left: Closed` while `right: Open` was required. In the same run, aligned/absent controls remained valid.

This disproves the implicit assumption that executable guest alignment alone is enough to validate an explicit physical mapping.

## Adversarial matrix

The final regression covers explicit physical starts at offsets `1`, `2`, and `3` modulo four. It also keeps positive controls for:

- no explicit physical mapping;
- `physical_start = 0`;
- `physical_start = 4`;
- `physical_start = 0xfffffff8` with an eight-byte image, chosen to remain aligned and non-overflowing so this work does not consume the separate span-overflow claim.

The malformed cases use the same instruction payload as the controls. Equal payload therefore cannot be used as a substitute for valid mapping identity or provenance.

## Candidate fix

`ProgramMap::validate()` now rejects any executable region whose explicit physical base is not 4-byte aligned:

```rust
if r.physical_start
    .is_some_and(|physical| !physical.0.is_multiple_of(4))
{
    return Err("unaligned executable physical mapping".into());
}
```

The initial candidate source commit is `65f71d2f12211ecb01dcc136d6369ace4344e42b`. The final formatted source is present on the research branch.

The guard is intentionally placed at the `ProgramMap` validity boundary rather than only in `solve()`: discovery/load paths and later alias/copy/provenance consumers all rely on a valid `ProgramMap`, so malformed explicit backing should not enter the evidence model at all.

## Regression construction

After adding the validation guard, `direct_cfg()` itself correctly rejected an image created with an unaligned physical base. To test the public validity boundary rather than merely that constructor path, the final regression first builds a valid static map with no explicit physical mapping, then adversarially mutates the copied `Region.physical_start` to `1`, `2`, or `3` and reinserts it.

Each forged malformed map must fail both:

- `ProgramMap::validate()`; and
- `solve(..., Scope::DeclaredStaticImages)`.

This also demonstrates deletion/fabrication resistance at the solver entry boundary rather than relying on one producer to sanitize its own output.

## Verification

Research workflow: `.github/workflows/research-region-physical-alignment.yml`.

Commands:

```text
cargo test --locked -p plaid-core --test region_physical_alignment -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

Final cleaned-head verification is Actions run `38005042501`, job `114071769126`. The focused adversarial regression, full `plaid-core` suite, formatting check, and clippy all passed.

An earlier semantic verification run, `38004925456` / job `114071401561`, already had both the focused regression and the complete `plaid-core` test suite passing; it failed only rustfmt, after which the source/test were formatted and re-run.

## Composition with prior work

This result composes with and tightens:

- ADR-0005: explicit executable identities must not be conflated merely because bytes or addresses look compatible;
- ADR-0009: malformed or fabricated proof facts must fail closed rather than be accepted by a weak validation boundary;
- ADR-0010: physical execution/copy reasoning requires exact, defensible physical coverage;
- ADR-0017: explicit physical mappings are proof-relevant facts and therefore require structural validity before overlap/alias composition.

It is distinct from:

- `research/region-physical-span-overflow-gpt56sol`, which owns the 32-bit physical span-bound question; and
- `research/solver-physical-alias-closure-gpt56sol`, which tested conflicting/overlapping explicit physical identities rather than local alignment of a single mapping.

## Closed-world impact

Before this fix, an impossible explicit physical executable mapping could be accepted as a valid region and an otherwise finite static CFG could report `CLOSED`. That malformed mapping could subsequently contaminate physical-overlap, alias, copy, and provenance reasoning because those consumers treat `ProgramMap` mappings as typed facts.

After the fix, the malformed mapping is rejected before it can participate in closure. This removes one structural route to false physical-backing claims; it does not itself prove that any surviving physical mapping has complete causal provenance.

## Remaining gap

This result does not solve physical-address span overflow, physical mapping provenance/completeness, TLB/context correctness, cache residency/lifetimes, executable mutation accounting, dynamic code discovery, or whole-ROM closure. Those obligations remain independently OPEN until their own evidence is satisfied.

## Integration recommendation

Adopt the `ProgramMap::validate()` 4-byte `physical_start` guard and the adversarial regression. When integrating, reconcile the validation-loop edit with the separate physical-span-overflow worker rather than dropping either invariant. No solver flag or scope exception should waive malformed mapping structure.
