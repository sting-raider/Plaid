# Solver CodeImage content binding

## Result

VALIDATED on canonical base `211176e7a489fecf8331d02915ee982cd279cb62`: `Scope::DeclaredStaticImages` could accept instruction bytes that no longer matched the content-derived image identity carried by the ProgramMap, as long as the caller retained the old `CodeImage.base.image`/generation and the mutated bytes preserved the decoded CFG shape.

This is a proof-input authentication bug, not a MIPS semantic disagreement. The solver already re-derived control-flow facts from supplied bytes, but it trusted the caller to bind those bytes to the claimed executable image identity.

## Current-main counterexample

The bounded fixture uses three words at `0x80000000`:

- original: `ADDIU t0,zero,1 ; J 0x80000000 ; NOP`
- forged:   `ADDIU t0,zero,2 ; J 0x80000000 ; NOP`

Only a non-control immediate changes, so the basic-block extent and direct edge are identical.

Big-endian executable bytes and identities:

- original bytes: `240800010800000000000000`
- original SHA-256: `04df1b7c460e17d3929404e7eca1074fb2ff0a7f92880deaf1f556b5acb4cd4b`
- forged bytes: `240800020800000000000000`
- forged SHA-256: `a32936b0b68f8a8e71782375d901cadfc7a704eb60aa741b16f558bfce3f5fb4`

The ProgramMap is derived from the original content-hashed image. The adversary then mutates `words[0]` but retains the original image identity. On unpatched current-main behavior, the solver's source lookup accepts the supplied image by `(image,generation,pc)`, re-derives an equivalent CFG from the forged bytes, and has no byte-identity blocker. The red regression therefore observes a result incompatible with the required fail-closed `instruction_source_identity_mismatch` outcome.

Branch-only Actions run `37999205145`, job `114052866156`, failed exactly at the focused regression on the unpatched solver; all later validation steps were skipped.

## Root cause

`solver.rs::source` matches a supplied `CodeImage` by image string, generation and address coverage. It does not authenticate the supplied word vector against that image string.

That omission matters because Plaid already has two production self-authenticating image forms:

1. `CodeImage::from_rom` uses the SHA-256 of the supplied image bytes as `base.image`.
2. trace-only compiled units without a unique known image use `trace-<sha256(bytes)>`.

Thus an image identity that originally meant a particular byte string could be detached from those bytes at the final solver boundary.

## Candidate fix

Commit `4380f0583b2e7e53363c3660b5dcdbc40755a6c4` adds a minimal fail-closed check in `solve`:

- raw lowercase 64-hex image IDs are interpreted as an explicit SHA-256 content claim;
- `trace-<lowercase-64-hex>` image IDs are interpreted as the same claim with a namespace prefix;
- the supplied words are serialized big-endian and hashed;
- a mismatch adds blocker `instruction_source_identity_mismatch`.

The patch deliberately does **not** guess that arbitrary opaque image labels are hashes. Those labels remain a v0 compatibility surface. A stronger schema should carry an explicit mandatory executable-content digest separately from semantic/source identity instead of encoding authentication conventions in a string.

## Adversarial controls

The regression suite covers:

- unchanged content-derived image: still closes under the declared finite static scope;
- same CFG, changed non-control immediate, stale raw hash identity: OPEN with `instruction_source_identity_mismatch`;
- same mutation followed by recomputing a new content hash: the new identity no longer matches the old ProgramMap, so OPEN via `missing_instruction_source` rather than laundering the old map;
- same CFG mutation with `trace-<sha256>` identity: OPEN with `instruction_source_identity_mismatch`;
- existing opaque synthetic labels remain accepted by existing tests, avoiding an unrelated schema migration inside this bounded fix.

The first candidate-fix run, `37999415991` / job `114053574327`, passed the focused regression, full `plaid-core` tests, `cargo fmt --all -- --check`, and `cargo clippy -p plaid-core --all-targets -- -D warnings` before the extra controls were added.

Run `37999522202` showed the expanded semantic tests passing (focused and full `plaid-core`) but failed formatting only; no semantic regression was observed. Commit `28f5e4455366e503be53cb76bf4c05db8c924787` applies the required test layout and is the final code/test candidate before this note.

## Reproduction

```sh
cargo test -p plaid-core --test solver stale_content_derived_image_identity_cannot_close -- --exact
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --all-targets -- -D warnings
```

The branch-only workflow is `.github/workflows/research-solver-codeimage-content-binding.yml`.

## Prior research composed or challenged

This composes:

- ADR-0005's separation of guest address from executable image/generation identity;
- ADR-0009's rule that closure must resist fact deletion/contradiction and recheck instruction-derived control flow;
- `CodeImage::from_rom` content-derived image construction;
- trace import's `trace-<sha256(bytes)>` fallback identity;
- the CLI's existing caution about reconstructing a solver image only when its identity matches the declared region.

It challenges the implicit assumption that re-decoding caller-supplied words is enough to authenticate the executable source. Re-decoding proves facts *about those words*; without a binding check it does not prove they are the words named by the ProgramMap identity.

## Closed-world impact

For the finite declared-static solver, a stale or forged `CodeImage` must not be able to borrow a previously established executable identity merely because its control-flow shape is unchanged. The candidate fix closes that hole for Plaid's current production content-derived identity forms.

This does **not** advance `WholeRom` to CLOSED. It does not prove byte provenance, physical backing, mapping generations, cache residency, mutation chronology, overlays, exception roots, RSP identity or executable lifetime. A digest establishes content identity only; it is not causal provenance.

## Remaining gap

`CodeImage` has no mandatory, explicit content-authentication field. Opaque labels therefore remain unauthenticated by this candidate patch. The production design should separate at least:

- executable content digest;
- semantic/source image identity;
- generation/lifetime identity;
- backing/mapping provenance.

The primary integrator should either adopt this small blocker as an immediate hardening step or generalize it into an explicit `CodeImage` content digest carried and checked at every solver boundary. Do not infer any of the other identities from digest equality.
