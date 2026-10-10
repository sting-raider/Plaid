# Overlapping CodeImage source contradiction can manufacture static closure

Result: **VALIDATED**

Worker: `gpt56sol-solver-overlapping-codeimage-source-20261010`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/solver-overlapping-codeimage-source-gpt56sol`

## Question

Can `Scope::DeclaredStaticImages` report CLOSED when supplied `CodeImage` fragments assign different instruction words to the same `(image, generation, pc)`, but the conflicting fragment begins inside an already-decoded block and therefore does not cover that block's root?

This is intentionally distinct from authenticating an image label to bytes. The fixture uses the opaque image label `opaque-overlap-test` so the experiment attacks source-fragment consistency, not the separate content-hash-binding problem.

## Current-main reproducer

The primary image begins at `0x80000000`, image `opaque-overlap-test`, generation 7:

```text
0x80000000  0x24080001  ADDIU t0,zero,1
0x80000004  0x24090002  ADDIU t1,zero,2
0x80000008  0x08000000  J 0x80000000
0x8000000c  0x00000000  NOP
```

`direct_cfg` builds the ProgramMap from that primary image. A second supplied image uses the same image and generation but begins at the interior PC `0x80000004` with `0x24090003` (`ADDIU t1,zero,3`).

On canonical main, the solver returned:

```text
scope: DeclaredStaticImages
status: Closed
blockers: {}
```

The red run is GitHub Actions run `38051003687`, job `114209945612`, commit `3a4e5725feed78850b9d1bbb51b528de4e51851b`. The focused matrix ran four cases: three controls passed and the intended conflicting-interior test failed because the solver returned CLOSED. Earlier run `38050967453` stopped at rustfmt before semantic execution and is not evidence for the bug.

## Root cause

`solver::source(images, &block.start)` selects a unique source only among supplied images that contain the block start. The interior fragment does not contain `0x80000000`, so it does not compete with the primary source for that block.

The later per-image CFG re-derivation also derives roots only from already-known block starts and entries contained by each supplied image. The interior-only fragment contains no such root, so its root set is empty and it is skipped. The contradictory word is therefore invisible to both mechanisms.

This makes byte consistency accidentally depend on block partitioning. A proof source can assign two different words to one execution identity and still produce a CLOSED static-scope report.

## Candidate fix

Commit `d00ca664e53b5c5a13b3fb588d2201faf3d38bf2` adds a solver-input consistency check before CFG-root logic. For every supplied word it compares all fragments with the exact same `image` and `generation` at the same PC. If any words disagree, the solver emits:

```text
conflicting_instruction_sources
```

and remains OPEN.

The candidate deliberately does **not** infer provenance from equality. Equal overlapping words merely avoid a contradiction; they do not prove common origin. Different image or generation identities remain distinct. Region evidence is attached when a matching executable region covers the conflicted PC.

The implementation is deliberately simple and is roughly O(total supplied words × supplied image count). If this becomes a scaling issue, an integrator can replace the scan with a keyed `(image, generation, pc) -> word` map without changing the semantic rule.

## Adversarial matrix

`crates/plaid-core/tests/solver_overlapping_codeimage_source.rs` now checks:

1. A different interior arithmetic word for the same identity is OPEN in either input order.
2. A different **interior control-flow word** is OPEN: the primary `J 0x80000000` at `0x80000008` is contradicted by same-identity `J 0x80000004`.
3. An equal interior word remains CLOSED and is not labeled a conflict.
4. Different image or different generation decoys remain distinct and do not create this blocker.
5. A contradiction covering the block start was already OPEN through existing source ambiguity (`missing_instruction_source`).

The strengthened test commit is `b784bf84c86499bdb169a7f125aa12f43d9d529a`.

## Green evidence

A clean read-only workflow verifies the committed branch without applying or persisting patches in the runner. Workflow commit: `eaa984f41ab98255acb38b68bb0b8298371d5b89`.

GitHub Actions run `38051321249`, job `114210859221` succeeded with:

- exact Rabbitizer revision guard: `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` in both `crates/plaid-core/Cargo.toml` and `refs.lock.toml`;
- `cargo fmt --all -- --check`;
- focused overlapping-source matrix: 5/5 passed;
- `cargo test -p plaid-core`: all 108 tests passed, including the five focused tests;
- `cargo clippy -p plaid-core --tests -- -D warnings`.

Reproduction commands:

```sh
grep -F 'rev = "724a49a5b4dbfb99f1a9e6992e63964fd29c90c8"' crates/plaid-core/Cargo.toml
grep -F 'rev = "724a49a5b4dbfb99f1a9e6992e63964fd29c90c8"' refs.lock.toml
cargo fmt --all -- --check
cargo test -p plaid-core --test solver_overlapping_codeimage_source -- --nocapture
cargo test -p plaid-core
cargo clippy -p plaid-core --tests -- -D warnings
```

## Prior research composed or challenged

This composes:

- ADR-0005: executable identity includes image plus generation;
- ADR-0009: finite-scope closure must be deletion/fabrication resistant and instruction facts are re-derived from supplied bytes.

It is distinct from `research/solver-codeimage-content-binding-gpt56sol`, which asks whether an image identifier is cryptographically/self-consistently bound to its bytes, and from `research/solver-cross-fragment-edge-gpt56sol`, which attacked missing CFG facts across non-overlapping source fragments. Here the failure exists even with an opaque identity and a complete primary CFG: a second fragment contradicts bytes *within the same declared execution identity* and is ignored only because of source partitioning.

## Closed-world impact

For a declared immutable executable identity, there cannot be two different instruction words at one PC. Before this fix, block-root partitioning could hide such a contradiction and manufacture `DeclaredStaticImages == CLOSED`, including when the hidden disagreement changes direct control flow. The candidate restores a necessary local consistency obligation: supplied byte facts for one execution identity must form a single-valued function of PC before they can participate in closure.

This does not make the scope native-complete and does not advance whole-ROM status by itself.

## Remaining gaps

This result does **not** establish:

- authentication of opaque image labels to canonical byte content or ROM provenance;
- physical backing/copy/transform provenance;
- overlay load/unload or executable lifetimes;
- cache-visible executable state or TLB/mapping context;
- exception/interrupt/NMI/reset root completeness;
- RSP executable identity;
- whole-ROM executable-universe closure.

Equal payloads still do not imply equal provenance. The candidate only rejects an impossible contradiction inside one already-declared execution identity.

## Integration recommendation

Reproduce the red case on current main, then cherry-pick or adapt the small solver invariant from `d00ca664e53b5c5a13b3fb588d2201faf3d38bf2` together with `crates/plaid-core/tests/solver_overlapping_codeimage_source.rs`. Do not integrate the branch-only research workflow as a production requirement.

If this lands alongside the separate CodeImage content-binding work, preserve both obligations: first, one `(image, generation, pc)` must not have conflicting supplied words; separately, whatever semantics are assigned to `image` must be independently authenticated rather than trusted because equal bytes happened to appear.