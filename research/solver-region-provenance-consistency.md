# Solver same-identity Region provenance consistency attack

Status: IN PROGRESS

Branch: `research/solver-region-provenance-consistency-gpt56sol`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`.

## Question

Can `Scope::DeclaredStaticImages` report CLOSED while one executable `(image, generation)` has overlapping Region facts that disagree about the ROM or physical backing of the same guest bytes?

This lane is deliberately separate from two neighboring attacks:

- `research/solver-guest-overlap-closure-gpt56sol` asks whether *different* executable identities may overlap guest virtual ranges without a selector.
- `research/solver-physical-alias-closure-gpt56sol` asks whether *different* executable identities may overlap explicit physical backing.

Here the executable identity is identical. The attack is whether contradictory provenance can be hidden inside that identity.

## Hypothesis

Current `ProgramMap::validate` validates Region rows independently, while `solver.rs::source` chooses supplied instruction bytes by `(image, generation, pc)`. If two overlapping Region rows carry the same identity, the solver does not currently appear to recheck whether their affine backing mappings agree over the overlap.

For an overlap beginning at guest byte `g`, two simultaneously-known mappings are compatible only if:

- both ROM mappings, when present, imply the same `rom_offset + (g - range.start)`; and
- both physical mappings, when present, imply the same `physical_start + (g - range.start)`.

One-sided missing metadata is UNKNOWN, not a contradiction and not evidence of equality. Payload equality is irrelevant.

## Adversarial regression

`crates/plaid-core/tests/solver_region_provenance.rs` contains six cases:

1. exact same-identity overlap with conflicting ROM offsets => OPEN;
2. exact same-identity overlap with conflicting physical starts => OPEN;
3. partial overlap whose affine ROM/physical mappings disagree => OPEN;
4. consistent shifted partial mapping and one-sided unknown metadata => CLOSED controls;
5. disjoint same-identity regions => CLOSED control;
6. merge-order symmetry: contradictory same-identity Region facts cannot be laundered by map union order.

The executable fixture is a two-word `J self; NOP` loop inside the declared-static effect subset. The supplied CodeImage is unchanged across all cases, so byte/value differences cannot explain any result.

## Evidence

Baseline branch Actions receipt pending. The intended first run is against unchanged current-main production code. No semantic verdict is claimed until that run reproduces or rejects the expected false CLOSED behavior.
