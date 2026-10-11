# Integration prep: finite-static executable identity integrity

Status: integration candidate, not merged to `main`

Worker: `gpt56sol-static-exec-identity-20261011`

Branch: `integration-prep/static-exec-identity-gpt56sol`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Production commits:

- `b1cdab0ac9959dc89693a25d9cb79f0d39eb4ad1` — consolidated adversarial regression suite.
- `a94b49c25775d7acf2741985690f67dc813af5f0` — unified finite-static executable identity consistency enforcement.

Evidence-only commit:

- `189a28fd33029b7e8e743a66071ffcbb24016006` — branch-only validation workflow. This workflow is useful for review but is not required to land on `main`.

## 1. Research reconciled

This integration-prep branch reconciles one coherent family of false-`CLOSED` failures in `Scope::DeclaredStaticImages`: the solver could validate finite CFG shape while the executable identity, byte source, or backing relation used to justify that CFG was internally contradictory or ambiguous.

Validated source branches used as evidence:

| Status | Research branch | Head used | Integrated meaning |
|---|---|---|---|
| VALIDATED | `research/solver-guest-overlap-closure-gpt56sol` | `e0716177738d064f73db61afabdeea32c898b755` | Distinct image/generation identities cannot simultaneously own overlapping decoded guest bytes in finite-static scope without a selector/lifetime proof. |
| VALIDATED | `research/solver-physical-alias-closure-gpt56sol` | `c442525b0f8e934d84197678cd6f265ab56d3688` | Distinct executable identities cannot overlap explicit physical backing without a proved alias/lifetime relation. |
| VALIDATED, SUPERSEDED | `research/solver-conflicting-region-mapping-gpt56sol` | `2b65dd27ec93ee86f759f1793c8b2c03fc25bf0b` | Narrow same-identity physical mapping disagreement. Subsumed by the broader Region provenance invariant below. |
| VALIDATED | `research/solver-region-provenance-consistency-gpt56sol` | `eb6a334511e0fcda11ff0ccb203115baa6b73672` | Overlapping Region observations for one executable identity must agree on all simultaneously-known affine ROM and physical backing facts; merge order cannot launder a contradiction. |
| VALIDATED | `research/solver-codeimage-content-binding-gpt56sol` | `e98f8e0670c8d01cbd0aa590410326d3930b5c63` | Content-derived image identities (`<sha256>` and `trace-<sha256>`) must authenticate the supplied instruction words. |
| VALIDATED | `research/solver-overlapping-codeimage-source-gpt56sol` | `d2ec0168491baa203cced78496d25e1f51aea971` | Multiple `CodeImage` fragments for one exact `(image, generation, pc)` must be single-valued even when the disagreement is interior to a decoded block. |
| VALIDATED | `research/solver-supplied-image-provenance-gpt56sol` | `75281aa809dd7a64767c78b05cfae545bc2522f8` | Explicit ROM/physical provenance on the selected `CodeImage` must agree with the covering executable `Region`. Equal bytes do not excuse contradictory provenance. |
| REJECTED | `research/solver-static-generation-lifetime-gpt56sol` | `562c1883d7e73fece7554e4389edcb441b3c2831` | Generation numbers are identity labels, not lifecycle chronology. Nonzero or multiple generations alone must not create a blocker. |
| REJECTED | `research/solver-cross-fragment-edge-gpt56sol` | `f4cc3068edd9325f1566c855cf50ac4c2422f02c` | No new cross-fragment edge gate is required: existing CFG re-derivation already catches deletion of required direct control flow. |
| PARTIAL / NOT ADOPTED | `research/solver-rom-source-binding-gpt56sol` | `ced56f0dfd7a8905d96de4014b5c98b4210b7a37` | Canonical ROM-byte binding needs a canonical ROM/source witness at the solver boundary. The research branch reverted its strict production prototype after falsification, so this integration does not pretend that witness exists. |

No research branch was merged or mechanically cherry-picked. The stale physical-alias branch was treated as evidence only.

The active `integration-prep/trace-event-identity-gpt56sol` lane was explicitly excluded from this scope.

## 2. Bugs reproduced against current `main`

The canonical base remained `211176e7a489fecf8331d02915ee982cd279cb62` throughout this work.

Baseline reproduction command:

```sh
cargo test -p plaid-core --test solver_static_identity -- --nocapture
```

Red evidence:

- Reproduction head: `611e74161a9f925d0c34d6592c30e6cfedcabfab`.
- GitHub Actions run: `38109347821`.
- Job: `114381470239`.
- Exact Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` compiled.
- 9 focused tests executed.
- 7 adversarial families failed because the unchanged solver returned `ClosureStatus::Closed` with no relevant blocker.
- 2 negative controls passed, including the requirement that generation labels alone do not invent lifecycle chronology and that missing one-sided physical provenance is not guessed into a conflict.

Reproduced false-`CLOSED` families:

1. exact and partial decoded guest overlap across distinct executable identities, including equal payload with different generations;
2. exact and partial explicit physical-backing overlap across distinct identities, including equal payload with different generations;
3. same-identity overlapping Region ROM/physical affine contradictions, including merge-order laundering;
4. same-identity overlapping `CodeImage` fragments supplying different words at one PC;
5. forged instruction words retaining a stale content-derived image identity;
6. explicit supplied-`CodeImage` ROM/physical provenance contradicting the retained covering `Region`;
7. combinations of the above where equal values would otherwise tempt an unsound provenance equivalence.

## 3. Production invariant implemented

The implementation treats these results as one invariant rather than a pile of branch-specific patches:

> A finite-static closure certificate may use an executable byte only when its execution identity, supplied value, and every simultaneously-known backing/source relation used by the certificate are single-valued and mutually consistent. Unknown provenance remains unknown; equality of values does not prove equality of provenance or lifetime.

`solver.rs` now enforces the following before allowing static closure:

1. **Self-authenticating content identity:** raw 64-hex SHA-256 image IDs and `trace-<sha256>` IDs authenticate the supplied big-endian instruction words. Opaque v0 labels remain compatible because `CodeImage` does not yet carry a mandatory content digest.
2. **Single-valued bytes per execution identity:** every supplied `(image, generation, guest_pc)` has at most one instruction word, independent of fragment boundaries or input ordering.
3. **Unambiguous decoded guest ownership:** decoded block byte ranges belonging to distinct image/generation identities may not overlap in `DeclaredStaticImages` scope without a mapping/lifetime selector.
4. **Consistent same-identity Region provenance:** where two overlapping Regions for one identity both provide ROM and/or physical affine facts, those known facts must agree at the overlap. Missing facts are not invented.
5. **Unambiguous explicit physical ownership:** distinct executable identities may not overlap known physical spans in finite-static scope without a proved alias/lifetime relation.
6. **Selected source agrees with retained Region:** explicit `CodeImage.rom_offset` and `CodeImage.physical_start` must agree affinely with each covering matching Region used for a decoded block.

The implementation does **not** infer lifecycle from generation numbers, virtual-address shape, equal payloads, or missing metadata.

Whole-ROM closure remains fail-closed and `native_complete` remains false.

## 4. Research patches intentionally not adopted

- `research/solver-conflicting-region-mapping-gpt56sol` was not retained as a separate blocker or code path. Its physical-only same-identity case is subsumed by `conflicting_region_provenance`.
- The generation-order/lifetime proposal from `research/solver-static-generation-lifetime-gpt56sol` is intentionally rejected. The consolidated regression suite contains a positive control to prevent that shortcut from returning.
- The proposed cross-fragment direct-edge special case from `research/solver-cross-fragment-edge-gpt56sol` is intentionally rejected because existing `direct_cfg` re-derivation already validates that obligation.
- The strict canonical-ROM source-binding prototype from `research/solver-rom-source-binding-gpt56sol` is intentionally not adopted. `solve()` does not receive canonical ROM bytes or an equivalent source witness; adding a strict check there would manufacture trust rather than verify it.
- Research-specific workflow/docs and branch patch structure were not copied into production. The branch-only workflow on this integration-prep branch is evidence infrastructure, not a required mainline artifact.

## 5. Validation

Focused regression command:

```sh
cargo test -p plaid-core --test solver_static_identity -- --nocapture
```

Full validation commands:

```sh
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --all-targets -- -D warnings
grep -F 'rev = "724a49a5b4dbfb99f1a9e6992e63964fd29c90c8"' crates/plaid-core/Cargo.toml
grep -F 'rev = "724a49a5b4dbfb99f1a9e6992e63964fd29c90c8"' refs.lock.toml
```

Green evidence:

- Validated code/tree head: `6e560a28d3a75f76a715a4ee51cca76784beaa14`.
- Tree: `e0392c9a9546a9a0ba5577f583457aecdc5a56a3`.
- GitHub Actions run: `38109763347`.
- Job: `114382704569`.
- Focused static-identity suite: 9/9 PASS.
- `cargo fmt --all -- --check`: PASS.
- Full `cargo test -p plaid-core`: PASS.
- Strict `cargo clippy -p plaid-core --all-targets -- -D warnings`: PASS.
- Exact Rabbitizer pin checks: PASS.

The clean branch evidence commit `189a28fd33029b7e8e743a66071ffcbb24016006` has the **same tree** `e0392c9a9546a9a0ba5577f583457aecdc5a56a3` as the green validated head above. History was rewritten only to remove temporary lint/format bookkeeping from the production commit range.

## 6. Remaining uncertainty

This candidate deliberately leaves the following proof obligations open rather than weakening them:

- Opaque v0 `CodeImage` labels do not carry a mandatory content digest. Only the currently self-authenticating raw-SHA and `trace-<SHA>` forms can be cryptographically checked at this boundary.
- Canonical ROM-byte/source binding remains a separate certificate/API problem because the solver is not given canonical ROM bytes.
- Missing ROM/physical metadata is still unknown, not equivalent to any known mapping. This patch rejects contradictions among known facts but does not claim completeness from absent facts.
- Dynamic mapping, TLB context, cache residency/staleness, executable lifetime, overlays, mutations, exceptions, RSP execution, and whole-ROM universe closure remain separate obligations and continue to keep broader scopes open.
- The current overlap checks are pairwise (`O(blocks^2 + regions^2)`). This is acceptable for the present finite-static production boundary but should eventually become interval-indexed if ProgramMaps become large enough for it to matter. That is a scalability concern, not permission to weaken the invariant.

## 7. Recommendation to the primary integrator

1. Reconfirm `main` has not changed in a way that alters `solver.rs` or the ProgramMap/CodeImage contracts. If it has, rebase and rerun the same focused matrix before landing.
2. Review and land the two production commits in order:
   - `b1cdab0ac9959dc89693a25d9cb79f0d39eb4ad1`
   - `a94b49c25775d7acf2741985690f67dc813af5f0`
3. Keep `crates/plaid-core/tests/solver_static_identity.rs` as the consolidated regression surface. Do not replace it with the individual research-branch test files.
4. Do not separately land the narrow conflicting-region-mapping, generation-lifetime, cross-fragment-edge, or strict ROM-source prototypes listed above.
5. Treat `189a28fd33029b7e8e743a66071ffcbb24016006` as review/CI evidence only; the branch-specific workflow may be omitted from `main`.
6. Rerun the focused suite, full `plaid-core`, rustfmt, strict Clippy, and exact Rabbitizer pin checks on the integration commit.
7. Keep the unresolved canonical-source, dynamic mapping/cache/lifetime, and whole-ROM obligations OPEN. No flag or equality shortcut should waive them.
