# Solver supplied-CodeImage provenance attack

Status: IN PROGRESS

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`.

Branch: `research/solver-supplied-image-provenance-gpt56sol`.

## Question

Can `Scope::DeclaredStaticImages` report CLOSED when the ProgramMap retains one executable Region with explicit source/backing provenance but the external `CodeImage` used by the solver to re-derive its instruction graph carries contradictory provenance while presenting the same bytes and executable identity?

This is intentionally different from Region-vs-Region consistency work. There is only one Region fact in the counterexample. The disputed join is `solver.rs::source` selecting a caller-supplied `CodeImage` by `(image,generation,pc)` without checking the CodeImage's own `rom_offset` or `physical_start` against the retained covering Region.

## Hypothesis

Equal instruction bytes are enough to recheck decoding, but they are not enough to reconcile causal/source provenance. If both the retained Region and supplied CodeImage explicitly name a ROM offset or physical start, disagreement is a contradiction and must keep the finite static proof OPEN. One-sided missing metadata is not proof of disagreement and must not be guessed.

## Adversarial matrix

`crates/plaid-core/tests/solver_supplied_image_provenance.rs` uses one two-word `J self; NOP` image in the supported static subset and one retained Region. It tests:

1. matching explicit ROM + physical metadata => CLOSED control;
2. identical payload/identity but different explicit ROM offset => OPEN;
3. identical payload/identity but different explicit physical start => OPEN;
4. both explicit origins different => OPEN;
5. supplied metadata absent on both axes => CLOSED control, no guessed contradiction.

The mismatch cases deliberately keep the same words, image string, generation and guest PC. Numeric/content equality therefore cannot explain away the provenance conflict.

## Evidence

Baseline Actions run pending. The first run is intentionally against unchanged current-main solver production logic. No semantic result is claimed until that executable regression runs.
