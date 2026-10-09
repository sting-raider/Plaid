# Solver supplied-CodeImage provenance attack

Status: VALIDATED

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`.

Branch: `research/solver-supplied-image-provenance-gpt56sol`.

Validated code/test head: `37d879f87c06d77248868d8e00b2d7161b66b41f`.

## Result

Current `main` can report `Scope::DeclaredStaticImages == CLOSED` when the
ProgramMap retains one executable `Region` with explicit ROM and/or physical
provenance, but the external `CodeImage` supplied to `solve` asserts a different
explicit origin while presenting the same instruction bytes and the same
`(image, generation, PC)` executable identity.

This is a false-CLOSED proof bug. Equal bytes are sufficient to compare decode
behavior, but they do not establish equal source/backing provenance. A caller can
substitute an equal-payload image from another explicit ROM offset or physical
backing and the unmodified solver accepts it as the source used to re-derive the
CFG.

The bounded candidate fix makes explicit contradictions fail closed without
inventing facts when either side lacks provenance metadata.

## Root cause

`solver.rs::source` selects a unique caller-supplied `CodeImage` using only:

- image identifier;
- generation;
- whether the image contains the requested guest PC.

It does not compare `CodeImage::rom_offset` or `CodeImage::physical_start` with
the retained `Region` that covers the block. The later CFG recheck compares block,
edge and indirect-site structure, but does not otherwise bind the supplied image's
source/backing metadata to that Region.

This attack deliberately uses only one retained Region. It is therefore distinct
from Region-vs-Region consistency bugs.

## Reproduction on current main

`crates/plaid-core/tests/solver_supplied_image_provenance.rs` constructs a two-word
supported static image:

```text
0x80000000: J 0x80000000
0x80000004: NOP
```

The retained Region and control image use ROM offset `0x100`, physical start
`0x1000`, generation 7 and one fixed image identifier. Adversarial supplied images
retain the exact same words, identifier, generation and guest addresses while
changing only explicit provenance metadata.

Baseline Actions run `37999334196`, job `114053299852`, tested head
`50d44e12ba90f204d8579bdca0606329d3bbb6c6` with unchanged production solver
logic. Formatting passed and exact pinned Rabbitizer
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` compiled. The focused test produced:

- matching explicit provenance: PASS / CLOSED control;
- supplied metadata absent: PASS / CLOSED control;
- different explicit ROM offset: **FAIL**, solver returned `Closed` instead of
  expected `Open`;
- different explicit physical backing: **FAIL**, solver returned `Closed` instead
  of expected `Open`;
- both explicit origins different: **FAIL**, solver returned `Closed` instead of
  expected `Open`.

Thus the counterexample does not rely on changed instruction bytes, changed CFG,
an additional Region, an overlay, an executable write, or any unsupported static
instruction effect.

Reproduction command:

```sh
cargo test -p plaid-core --test solver_supplied_image_provenance -- --nocapture
```

## Candidate fix

Commit `525bfdb6dd37e39a595c30d6a5a2780feb04046f` adds a small solver-side
`supplied_region_provenance_conflict` check. For every covering Region of a block,
it compares the affine source/backing location represented by the supplied
`CodeImage` and Region at the block PC.

The rule is intentionally narrow:

- ROM offsets are compared only when both sides explicitly provide one;
- physical starts are compared only when both sides explicitly provide one;
- guest-address deltas are applied before comparing origins, so shifted affine
  mappings compare correctly;
- missing metadata does not become guessed provenance or guessed conflict;
- equal payloads are never consulted to reconcile a provenance disagreement;
- Regions that do not cover the block are irrelevant to this join.

An explicit disagreement emits `supplied_image_provenance_conflict` and keeps the
finite proof OPEN.

## Adversarial falsification controls

The final focused regression at head
`37d879f87c06d77248868d8e00b2d7161b66b41f` contains six tests:

1. matching explicit ROM + physical metadata => CLOSED;
2. identical payload/identity but different explicit ROM offset => OPEN;
3. identical payload/identity but different explicit physical start => OPEN;
4. identical payload/identity with both explicit origins different => OPEN;
5. one-sided missing ROM, missing physical, and both missing supplied metadata =>
   CLOSED controls, with no fabricated contradiction;
6. a disjoint same-identity Region with contradictory metadata => CLOSED control;
   unrelated provenance does not poison the source join.

These cases attack payload-equality laundering, source/backing substitution,
missing-fact guessing, and over-broad Region matching.

## Validation

Final Actions run `37999585210`, job `114054121787`, tested head
`37d879f87c06d77248868d8e00b2d7161b66b41f` and completed successfully.
Exact pinned Rabbitizer
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` was compiled by the run.

The run passed all of:

```sh
cargo fmt --all -- --check
cargo test -p plaid-core --test solver_supplied_image_provenance -- --nocapture
cargo test -p plaid-core
cargo clippy -p plaid-core --all-targets -- -D warnings
```

Focused result: `6 passed; 0 failed`.
The complete `plaid-core` test suite and clippy completed with zero failures.

## Composition with prior research

This result composes rather than replaces existing proof obligations:

- ADR-0009 requires closure to resist deletion/substitution of causal evidence.
  Here, substituting the recheck input while preserving equal bytes manufactured
  closure on current main.
- ADR-0017 keeps physical/source identity distinct from byte identity and warns
  that address/backing facts require explicit evidence.
- `loads::record_load` already accepts executable ROM provenance only against
  canonical source bytes and retains explicit backing identity rather than
  inferring provenance from values.
- The completed physical-alias solver attack covers distinct executable identities
  over overlapping explicit storage. This attack instead keeps one executable
  identity and one Region, then contradicts it with the external instruction
  source object.
- Concurrent Region-provenance-consistency work compares Region facts against
  other Region facts. This branch tests a different boundary: supplied
  `CodeImage` versus retained Region.

## Closed-world impact

The candidate fix closes one concrete false-CLOSED path in
`DeclaredStaticImages`: explicit retained executable provenance can no longer be
silently contradicted by the image object used to re-derive instruction control
flow.

This strengthens the finite solver's causal binding between "the bytes I decoded"
and "the explicitly identified source/backing those bytes are claimed to come
from." It does not turn matching values into provenance proof.

## Remaining gap

This bounded result does **not**:

- prove provenance when either side omits ROM/physical metadata;
- establish that a supplied `CodeImage` was actually captured from its claimed
  source merely because metadata agrees;
- validate hashes or immutable storage lifetimes beyond existing mechanisms;
- resolve contradictory Region-vs-Region facts, overlay lifetimes, TLB/context
  generations, aliases, stale I-cache residency, transforms or relocations;
- establish complete executable mutation accounting;
- change `WholeRom`, which remains independently OPEN;
- establish native completeness.

The candidate patch should also be reconciled with any simultaneously developed
Region-consistency solver gates so the primary integrator keeps one coherent
provenance policy rather than accumulating overlapping special cases.

## Integration recommendation

ADOPT the explicit CodeImage-vs-covering-Region provenance consistency invariant
and the focused adversarial regression. Preserve its fail-closed direction:
known contradiction blocks closure, missing information remains unknown, and
payload equality cannot discharge provenance identity.

The primary integrator should reproduce/cherry-pick the small solver change and
tests onto the then-current `main`, reconciling it with concurrent Region
consistency work. Do not merge this research branch wholesale; the branch-only
workflow and research note are coordination/reproducibility scaffolding.
