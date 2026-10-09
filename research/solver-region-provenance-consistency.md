# Solver same-identity Region provenance consistency attack

Status: VALIDATED

Branch: `research/solver-region-provenance-consistency-gpt56sol`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`.

## Result

`Scope::DeclaredStaticImages` on current main can report CLOSED while one executable `(image, generation)` has overlapping Region facts that disagree about the ROM or physical backing of the same guest bytes.

This is a false-CLOSED proof bug. The executable payload and CodeAddress identity can remain exactly the same while the map asserts mutually incompatible source/storage interpretations. Same values therefore do not rescue the proof.

This lane is deliberately separate from two neighboring attacks:

- `research/solver-guest-overlap-closure-gpt56sol` asks whether *different* executable identities may overlap guest virtual ranges without a selector.
- `research/solver-physical-alias-closure-gpt56sol` asks whether *different* executable identities may overlap explicit physical backing.

Here the executable identity is identical. The contradiction is inside its retained provenance.

## Compatibility rule exercised

For an overlap beginning at guest byte `g`, two simultaneously-known mappings for the same `(image, generation)` are compatible only if:

- both ROM mappings, when present, imply the same `rom_offset + (g - range.start)`; and
- both physical mappings, when present, imply the same `physical_start + (g - range.start)`.

One-sided missing metadata is UNKNOWN, not a contradiction and not evidence of equality. Payload equality is irrelevant. Disjoint regions do not constrain each other.

## Current-main reproduction

`crates/plaid-core/tests/solver_region_provenance.rs` builds a two-word `J self; NOP` CodeImage and a valid static ProgramMap. It then adds or merges same-identity Region rows while keeping the supplied instruction bytes unchanged.

Red Actions receipt against unchanged production solver:

- regression commit: `64e63f9e9efc1070127dffc23bde7418a26cb877`
- run: `37999024077`
- job: `114052262427`
- exact pinned Rabbitizer compiled by Cargo: `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`
- result: 2 controls passed, 4 positive adversaries failed because solver returned `Closed` instead of `Open`.

The four reproduced false-CLOSED cases are:

1. exact same-identity overlap with conflicting ROM offsets;
2. exact same-identity overlap with conflicting physical starts;
3. partial overlap whose affine ROM/physical mappings disagree;
4. contradictory Region facts merged in either map order.

`ProgramMap::validate()` accepted the contradictory maps in all of these cases.

The two controls that already behaved correctly were:

- consistent shifted partial overlap plus a row with missing backing metadata;
- disjoint same-identity regions.

This actively falsifies the alternative explanation that the failure is caused merely by duplicate Region rows or overlapping ranges. Only contradictory simultaneously-known mappings need a blocker.

## Candidate fix

Commit `fb4595999f0c0842ac7dbb4aa9af934a1f57ff77` adds a small `DeclaredStaticImages` solver-side recheck:

- compare only Region pairs with the same `(image, generation)` and overlapping guest ranges;
- evaluate ROM and physical mappings at the overlap start using 64-bit arithmetic;
- emit `conflicting_region_provenance` if either simultaneously-known affine mapping disagrees;
- union both Region evidence sets into the blocker;
- do not infer missing mappings, compare payload bytes, collapse identities, or change WholeRom's independent OPEN obligations.

The solver-side placement preserves contradictory research/import evidence for diagnosis instead of rejecting the ProgramMap before closure analysis can explain why it cannot close.

The pairwise implementation is intentionally the smallest research fix. If region counts become large in production certificates, the same rule can be indexed by `(image, generation)` and guest interval without changing semantics.

## Green validation

Candidate-fix Actions receipt:

- run: `37999177473`
- job: `114052769052`
- focused command: `cargo test -p plaid-core --test solver_region_provenance -- --nocapture`
- full command: `cargo test -p plaid-core`
- style: `cargo fmt --all -- --check`
- lint: `cargo clippy -p plaid-core --all-targets -- -D warnings`

All six focused adversarial cases passed. The complete `plaid-core` suite passed with zero failures, followed by clean formatting and clippy.

## Prior research composed/challenged

This result composes rather than weakens existing invariants:

- ADR-0009: a finite-scope closure must be independently rechecked; deleting or bypassing a derived blocker cannot manufacture CLOSED.
- ADR-0017: explicit mappings are evidence, not an excuse to collapse executable identity; contradictory mappings do not establish a unique alias.
- `loads.rs::physical_start`: contradictory physical mapping evidence already refuses to manufacture a unique location.
- `loads.rs::record_load`: different overlapping canonical sources become unresolved lifecycle candidates rather than being reconciled by payload equality.
- completed `research/solver-physical-alias-closure.md`: distinct executable identities sharing explicit backing need a fail-closed obligation. This experiment covers the complementary case where one identity itself has contradictory retained backing facts.

## Closed-world impact

A declared-static certificate must not claim one immutable executable identity has a unique known provenance while its Region evidence maps the same guest byte to two different known ROM or physical locations. Without this check, map merge can launder mutually incompatible source facts into an apparently CLOSED certificate.

The candidate fix closes that concrete finite-static false-CLOSED path only. It does **not** prove missing mappings, overlay/executable lifetimes, cache residency, relocation semantics, dynamic mutation completeness, exception roots, RSP coverage, or whole-ROM closure. Those obligations remain OPEN.

## Integration recommendation

Adopt the solver-side `conflicting_region_provenance` gate and the six-case regression, preferably alongside the neighboring guest-overlap and physical-alias fail-closed checks after the primary integrator reconciles their shared `solver.rs` conflict surface. Preserve the semantics exactly: known contradictory mappings block; missing metadata does not become guessed equality; equal payloads do not erase provenance.
