# Declared-static guest-overlap closure attack

Status: VALIDATED

Branch: `research/solver-guest-overlap-closure-gpt56sol`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62` (solver behavior is unchanged from technical base `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`).

## Question

Can `Scope::DeclaredStaticImages` report CLOSED when two distinct decoded executable image/generation identities occupy overlapping guest virtual addresses, even though no mapping or lifetime evidence selects which identity a raw CPU guest PC denotes?

Yes on current `main`.

This is deliberately separate from the completed explicit-physical-alias attack. The counterexample supplies no `physical_start`; it attacks the guest-address-to-executable-identity relation itself.

## Existing invariant being composed

`loads::record_load` already treats different canonical executable sources that overlap in **guest** address space as an unresolved overlay/lifecycle candidate. The finite solver re-derives several importer consequences so deleting derived facts cannot manufacture closure (ADR-0009). The completed physical-alias solver research established the same proof-monotonicity requirement for explicit physical overlap, but did not test identical/partially overlapping guest decoded execution with unknown physical mappings.

The important boundary is decoded executable block extent, not arbitrary overlapping region metadata. Region overlap alone can describe dormant or duplicate metadata and is not sufficient to prove simultaneous ambiguity. The regression therefore attacks blocks that the finite solver already treats as execution roots when it re-derives each supplied image.

## Adversarial regression

`crates/plaid-core/tests/solver_guest_overlap.rs` builds independently CLOSED `J self` images using only the declared-static integer/control-flow subset, then merges them. Cases:

- exact same guest block range, distinct image IDs, conflicting delay-slot bytes;
- exact same guest block range and payload, same image name but different generations;
- partial guest block overlap across distinct identities (one identity's delay slot is the other identity's decoded jump PC);
- disjoint guest ranges (negative control);
- an extra overlapping region description for one image/generation identity (negative control).

Equal payload is intentionally not an identity proof.

## Baseline reproduction

Regression commit: `a6ef824f5a8f17983d7f157310199f994b0af6f2`.

Workflow commit: `66a9c038385bfd1ef80a5bc57a7dd9d66b409e1c`.

Actions run `37998635740`, job `114050965091`, exact pinned Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`:

- exact overlap / distinct images: **CLOSED**, blockers `{}` -> regression FAIL;
- exact overlap / equal payload / different generations: **CLOSED**, blockers `{}` -> regression FAIL;
- partial decoded overlap: **CLOSED**, blockers `{}` -> regression FAIL;
- disjoint guest ranges: CLOSED as intended;
- same-identity overlapping region metadata: CLOSED as intended.

Focused result: 2 passed / 3 failed. The failure is therefore a current-main false-CLOSED path, not merely a missing diagnostic.

Reproduce baseline by checking out `66a9c038385bfd1ef80a5bc57a7dd9d66b409e1c` and running:

```sh
cargo test -p plaid-core --test solver_guest_overlap -- --nocapture
```

## Candidate fix

Commit `b6b914f61fefaff4ed49c3f628505e5d1fd1ef9e` adds a 24-line `DeclaredStaticImages`-only recheck over pairs of decoded block extents. If two overlapping guest spans carry different `(image, generation)` identities, the solver emits `ambiguous_guest_executable_identity` with the union of both block evidence sets.

The gate deliberately does **not**:

- collapse equal instruction payloads;
- guess physical aliasing from virtual shape;
- reject overlapping metadata for the same image/generation;
- reject disjoint guest execution;
- claim to solve TLB/ASID/overlay lifetime selection.

A future mapping/lifetime certificate may justify multiple identities at one guest VA, but `DeclaredStaticImages` has no such selector and explicitly excludes overlays and external mapping machinery. Until one exists, simultaneous decoded identities at the same raw PC cannot be called closed.

## Green evidence

Actions run `37998819762`, job `114051580235`:

- focused regression: 5 passed / 0 failed;
- full `cargo test -p plaid-core`: PASS;
- pinned Rabbitizer revision remained `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

At the validated patch commit, branch-vs-main was 4 commits ahead / 0 behind and changed only:

- `.github/workflows/research-solver-guest-overlap-closure.yml`;
- `crates/plaid-core/src/solver.rs` (+24 lines);
- `crates/plaid-core/tests/solver_guest_overlap.rs`;
- this research note.

## Closed-world impact

The finite solver currently permits independently valid `CodeAddress` tags to hide a missing runtime identity-selection proof. CPU execution ultimately presents a guest PC; two distinct decoded executable identities at that PC require a mapping/lifetime selector before either can be treated as the active executable generation. A static CLOSED result must therefore be monotone under retention of both identities and fail closed when their decoded extents overlap.

This result composes with, but does not replace, physical-backing alias checks. Guest overlap and physical overlap are independent axes: the former asks which executable identity a PC denotes; the latter asks whether apparently distinct virtual identities share mutable storage.

## Remaining gap

The candidate is intentionally bounded to `Scope::DeclaredStaticImages` and decoded CPU block extents. It does not certify TLB/ASID selection, cache residency, overlay load/unload chronology, exception roots, RSP execution, dynamically produced code, region-only dormant alternatives, or whole-ROM future reachability. The pairwise check is also a simple O(n^2) research implementation; a production-scale interval index can preserve the same invariant if block counts make that necessary.

## Integration recommendation

Adopt the invariant and regression. When integrating alongside the completed physical-alias solver patch, combine the two independent static-scope rechecks rather than treating one as a substitute for the other. Keep the exact identity key `(image, generation)`; do not weaken it to guest PC or payload equality. The branch-only workflow is research scaffolding and need not be merged.
