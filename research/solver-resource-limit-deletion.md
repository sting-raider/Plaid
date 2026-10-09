# Resource-limit deletion does not manufacture static closure in the tested solver paths

Status: REJECTED false-CLOSED hypothesis on `research/solver-resource-limit-deletion-gpt56sol`.

Baseline: canonical `main` at `211176e7a489fecf8331d02915ee982cd279cb62`.

## Question

Can a bounded discovery result be made to report
`Scope::DeclaredStaticImages == CLOSED` merely by deleting its
`resource_limit` diagnostic?

The dangerous shape is a `discover_image` run that has retained enough local
indirect evidence to look plausible, but has not yet traversed every inferred
root. `pipeline::discover_image` records exhaustion as an `Unresolved` fact, and
ADR-0009 requires closure to resist removal of blocker rows rather than trusting
them as the sole proof boundary.

This experiment targeted the current bounded discovery/solver composition rather
than a MIPS opcode semantic. It tested both direct-CFG instruction-budget
exhaustion and the outer indirect-target fixed-point loop, including an equal-byte
wrong-generation decoy.

## Result

The false-CLOSED hypothesis was rejected for the tested paths. No production
solver patch is warranted.

When a direct CFG pass is truncated, deleting only `resource_limit` does not make
that partial map CLOSED. `solve()` independently re-runs `direct_cfg` from the
supplied image with `image.words.len()` as its budget and detects the omitted
block/edge/extent facts. The retained diagnostic is useful reporting, but it is
not the only thing preventing closure.

A stronger case first infers a constant JR target at `0x80000020`, then exhausts
the next direct pass before that target is fully represented. Removing the
`resource_limit` row still leaves the map OPEN through independently reconstructed
CFG/target obligations.

An equal-payload generation-1 decoy was also unable to cover a truncated
generation-0 image. The generation-1 map is independently CLOSED, but merging it
with the edited generation-0 map still leaves the generation-0 omissions OPEN.
Content equality therefore did not substitute for execution identity.

## Executable adversarial matrix

`crates/plaid-core/tests/solver_resource_limit_deletion.rs` contains four cases:

1. `deleting_direct_cfg_resource_limit_cannot_manufacture_closure`
   - input: `NOP; J 0x80000004; NOP`;
   - `discover_image(..., budget=1)` emits a direct-CFG `resource_limit`;
   - the test deletes every `resource_limit` row;
   - solver remains OPEN from re-derived missing/contradictory CFG facts;
   - a complete `budget=16` control is CLOSED.

2. `equal_payload_other_generation_cannot_cover_limited_generation`
   - generation 0 is the edited truncated map;
   - generation 1 has byte-identical code and independently closes;
   - merging both does not discharge the generation-0 missing CFG facts.

3. `inferred_target_survives_direct_limit_and_keeps_deleted_limit_open`
   - LUI/ORI/JR yields a retained candidate at `0x80000020`;
   - the next pass reaches the direct instruction limit;
   - deletion of the limit row still leaves the inferred target/CFG incompleteness
     visible to the solver.

4. `chained_indirect_roots_hit_direct_budget_before_outer_fixed_point_limit`
   - an eight-stage chain successively synthesizes indirect roots;
   - budgets 1 through 32 exercise both exhausted and converged runs;
   - every observed `resource_limit` in this matrix is the direct-CFG form with a
     concrete site; the outer-loop `site=None` fixed-point exhaustion was not
     reached.

The fourth result is deliberately bounded evidence, not a theorem that the outer
fixed-point limit is unreachable for every future candidate producer or CFG
repartitioning pattern. The current source uses the same `budget` for the outer
iteration count and each direct traversal, which makes the direct instruction
bound dominate this external-root chain, but broader table/repartition patterns
remain outside this experiment.

## Validation

The branch-only workflow checks the exact Rabbitizer revision from both
`crates/plaid-core/Cargo.toml` and `refs.lock.toml`:

`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

Clean semantic run `38005543484`, job `114073364104`, at commit
`75dc0e3c48d8a1d3b776f39631ba757a945cd11b` produced:

- focused matrix: 4 passed / 0 failed;
- full `cargo test -p plaid-core`: 107 tests passed / 0 failed, plus doc tests;
- `cargo fmt --all -- --check`: passed;
- `cargo clippy -p plaid-core --tests -- -D warnings`: passed.

Earlier runs `38005304742` and `38005439540` stopped at formatting before semantic
execution and are not evidence. Run `38005359840` was an earlier clean 3-case
matrix before the equal-payload generation adversary was added.

## Composition with prior research

This attacks the same deletion-resistance invariant as ADR-0009 while composing
ADR-0008/0011's bounded indirect certificates and fixed-point rediscovery. It is
distinct from prior raw-indirect, raw-store, target-dispatch, code-image binding,
entry-verification, and cross-fragment-edge lanes: the questioned fact here is the
pipeline's own resource-exhaustion diagnostic.

The result supports the current separation between diagnostic facts and
independently re-derived instruction control flow. In particular, a removable
`Unresolved` row was not acting as an accidental capability token for CLOSED.

## Closed-world impact

For the declared immutable integer-image scope covered by these fixtures, direct
instruction-budget exhaustion cannot be laundered into CLOSED merely by deleting
its `resource_limit` diagnostic, even when a later generation supplies identical
bytes or an inferred indirect target is already present.

This says nothing about whole-ROM completeness. It does not establish complete
execution roots, overlay/write lifetimes, cache/TLB history, exception roots, RSP
identity, dynamic-code production, pointer-table immutability, or the absence of
unobserved runtime behavior. `WholeRom` must remain OPEN under its independent
obligations.

## Remaining gap

The experiment did not construct an outer fixed-point `resource_limit` with
`site=None`; the adversarial external-root chain always encountered the direct
instruction budget first. Future candidate producers, table-derived roots, or
repartitioning changes could alter that relationship. If such a real map is ever
produced, repeat the same diagnostic-deletion attack against that concrete
history rather than assuming this bounded rejection covers it.

## Reproduction

```sh
git checkout research/solver-resource-limit-deletion-gpt56sol
cargo fmt --all -- --check
cargo test -p plaid-core --test solver_resource_limit_deletion -- --nocapture
cargo test -p plaid-core
cargo clippy -p plaid-core --tests -- -D warnings
```

## Integration recommendation

Do not change production solver logic for this hypothesis. The focused regression
matrix is worth preserving or selectively transplanting because it makes the
ADR-0009 deletion-resistance property executable, including the equal-payload
wrong-generation case. Keep the outer fixed-point `site=None` case explicitly
open for a future concrete reproducer instead of claiming universal safety from
this bounded experiment.
