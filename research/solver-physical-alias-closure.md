# Solver physical-alias closure attack

Status: VALIDATED

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

## Result

Current `main` can report `Scope::DeclaredStaticImages == CLOSED` for a valid
ProgramMap containing two independently closed executable images that claim
distinct executable identities over the same explicit physical backing span.
The witness can use contradictory instruction bytes, and the bug also survives
when the payloads are equal but the executable generations differ.

This is a false-CLOSED proof bug: the declared-static scope promises immutable
code, but the map simultaneously asserts incompatible executable identities for
one physical storage interval without an alias-equivalence or lifetime proof.

## Reproduction

`crates/plaid-core/tests/solver_physical_alias.rs` constructs two 8-byte static
self-loop images. One is mapped at KSEG0 `0x80000000`, the other at KSEG1
`0xa0000000`; both claim `physical_start = 0`. Each image alone closes. Their
merged ProgramMap passes `ProgramMap::validate()`. On unmodified current-main
solver code, the combined map closes with an empty blocker set.

Red Actions run:

- run: `37969524313`
- job: `113952280047`
- branch regression commit: `5dfdf0517d321119f736a80a0631f9f7abd46cb2`
- exact failure: `left: Closed`, `right: Open`
- blocker dump: `{}`
- pinned Rabbitizer compiled at
  `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`

The contradictory-byte witness uses allowed static instructions only: both images
execute `J self`; their ADDIU delay slots differ. Therefore no unrelated memory,
COP, trap, indirect, or unsupported-effect blocker explains the result.

## Composition

This result composes existing project invariants rather than inventing new alias
semantics:

- ADR-0009: removing or bypassing derived facts must not manufacture closure.
- ADR-0017: explicit physical overlap is useful alias evidence, but CodeAddress
  identities must not be collapsed from address shape or payload equality; cache,
  relocation, lifetime and dispatch remain independent obligations.
- `loads::record_load`: overlapping distinct canonical executable sources already
  create `overlay_candidate_lifecycle_unknown` when guest or uniquely explicit
  physical spans overlap.
- `research/solver-raw-store-closure.md`: the solver must independently preserve
  fail-closed consequences of retained explicit physical-backing evidence rather
  than trusting a particular importer path to have produced every blocker.

The new counterexample reaches the same semantic conflict through two ordinary
static `direct_cfg` maps merged together, bypassing load analysis entirely.

## Candidate fix

Commit `3d1b4c46456845d4cb4dfbbe0bad237d0afeeeae` adds a bounded solver-side check
for `DeclaredStaticImages` only. It compares explicit physical spans pairwise and
emits `ambiguous_physical_executable_identity` when overlapping regions carry a
different `(image, generation)` identity.

The gate intentionally does **not**:

- infer physical aliases from KSEG virtual bit patterns;
- compare or merge identities because instruction payloads happen to match;
- reject aliases whose `(image, generation)` identity is already the same;
- attempt to prove overlay/lifetime equivalence;
- claim anything stronger for `WholeRom`, which remains independently OPEN.

Physical intervals are compared in `u64`, avoiding 32-bit wrap in the overlap
calculation.

## Adversarial falsification controls

The final regression contains six cases:

1. exact physical overlap, distinct image IDs, contradictory bytes => OPEN;
2. exact physical overlap, same image ID but distinct generations, equal bytes =>
   OPEN;
3. partial physical overlap, distinct identities => OPEN;
4. exact physical overlap with the same `(image, generation)` identity => CLOSED;
5. disjoint explicit physical spans => CLOSED;
6. one absent `physical_start` despite cached/uncached-looking virtual aliases =>
   CLOSED; no alias is guessed.

This specifically attacks value-equality laundering, generation collapse, partial
span arithmetic, virtual-address guessing and overclassification.

## Validation

Candidate-fix Actions run `37969884839`, job `113953500887` passed both:

```sh
cargo test -p plaid-core --test solver_physical_alias -- --nocapture
cargo test -p plaid-core
```

All six focused adversarial cases passed, followed by the complete `plaid-core`
suite with zero failures.

## Closed-world impact

This closes one concrete false-CLOSED path in the finite static solver. A declared
static certificate can no longer simultaneously treat two distinct executable
image/generation identities as immutable over overlapping *explicitly known*
physical storage without carrying an unresolved obligation.

It does not prove physical mappings that are missing, establish alias/lifetime
certificates, model cache residency, close overlay lifetimes, or improve whole-ROM
mutation completeness. Those remain OPEN obligations.

## Integration recommendation

Adopt the small `solver.rs` physical-span identity gate and the six regression
cases. Keep the rule fail-closed and explicit: overlap of known physical backing
across distinct executable identities needs a verified equivalence/lifetime model
before it can be discharged. Do not weaken the check using equal payloads or
virtual alias heuristics. The branch-only workflow and patcher spike are research
scaffolding and need not be integrated.
