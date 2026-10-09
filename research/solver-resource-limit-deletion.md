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
than a MIPS opcode semantic. It exercised direct-CFG instruction-budget
exhaustion, an inferred-but-untraversed target, the real outer 512-pass fixed-point
exhaustion path, and an equal-byte wrong-generation decoy.

## Result

The false-CLOSED hypothesis was rejected for all reproduced exhaustion paths. No
production solver patch is warranted.

When a direct CFG pass is truncated, deleting only `resource_limit` does not make
that partial map CLOSED. `solve()` independently re-runs `direct_cfg` from the
supplied image with `image.words.len()` as its budget and detects the omitted
block/edge/extent facts. The retained diagnostic is useful reporting, but it is
not the only thing preventing closure.

A stronger case first infers a constant JR target at `0x80000020`, then exhausts
the next direct pass before that target is fully represented. Removing the
`resource_limit` row still leaves the map OPEN through independently reconstructed
CFG/target obligations.

The outer fixed-point exhaustion path is also deletion-resistant in a concrete
reproducer. `discover_image` clamps the outer pass count to 512 but passes the raw
caller budget to `direct_cfg`. A 520-stage LUI/ORI/JR chain with `budget=2048`
therefore completes 512 direct traversals without reaching the direct instruction
limit, adds stage 512 as the next root, then emits the genuine fixed-point
`resource_limit` with `site=None`. After deleting that diagnostic, the retained
last constant-JR candidate still points to `0x80002000`, which has not been
traversed into a block. The solver remains OPEN with
`unresolved_indirect_target` at the last retained JR site (`0x80001ff8`).

An equal-payload generation-1 decoy was also unable to cover a truncated
generation-0 image. The generation-1 map is independently CLOSED, but merging it
with the edited generation-0 map still leaves the generation-0 omissions OPEN.
Content equality therefore did not substitute for execution identity.

## Executable adversarial matrix

`crates/plaid-core/tests/solver_resource_limit_deletion.rs` contains five cases:

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

4. `small_chained_indirect_roots_hit_direct_budget_before_outer_limit`
   - an eight-stage chain successively synthesizes indirect roots;
   - budgets 1 through 32 exercise both exhausted and converged runs;
   - every observed limit in this small-budget matrix is the direct-CFG form with
     a concrete site, demonstrating that the direct bound dominates this pattern
     before the outer clamp matters.

5. `deleting_actual_outer_fixed_point_limit_still_cannot_close`
   - 520 chained indirect stages and raw budget 2048 cross the outer 512-pass cap;
   - the produced map has exactly the real outer `resource_limit { site: None }`;
   - 512 stage blocks are retained and the next candidate target is not;
   - deleting the limit row still leaves `DeclaredStaticImages` OPEN through the
     retained candidate's `unresolved_indirect_target` obligation.

The fifth fixture closes the original experiment's main remaining gap: the
outer-loop row was produced by the real pipeline rather than forged by the test.
It does not prove every future candidate producer is safe under arbitrary schema
changes, but it does cover current local-constant fixed-point exhaustion as
implemented on the baseline.

## Validation

The branch-only workflow checks the exact Rabbitizer revision from both
`crates/plaid-core/Cargo.toml` and `refs.lock.toml`:

`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

Clean semantic run `38005840211`, job `114074311001`, at commit
`aa4fcea1d33c48b0624ef0724ce1f68f31200e39` produced:

- focused matrix: 5 passed / 0 failed; the concrete 512-pass outer exhaustion case
  completed successfully;
- full `cargo test -p plaid-core`: 108 tests passed / 0 failed, plus doc tests;
- `cargo fmt --all -- --check`: passed;
- `cargo clippy -p plaid-core --tests -- -D warnings`: passed.

Earlier runs `38005304742`, `38005439540`, and `38005789469` stopped at formatting
before semantic execution and are not evidence. Run `38005359840` was an earlier
clean 3-case matrix, and `38005543484` was a clean 4-case matrix before the real
outer fixed-point reproducer was added.

## Composition with prior research

This attacks the same deletion-resistance invariant as ADR-0009 while composing
ADR-0008/0011's bounded indirect certificates and fixed-point rediscovery. It is
distinct from prior raw-indirect, raw-store, target-dispatch, code-image binding,
entry-verification, and cross-fragment-edge lanes: the questioned fact here is the
pipeline's own resource-exhaustion diagnostic.

The result supports the current separation between diagnostic facts and
independently re-derived instruction/control-flow obligations. In the direct
budget case, solver CFG reconstruction catches what discovery omitted. In the
outer fixed-point case, the retained certified target itself exposes the missing
next executable root. A removable `Unresolved` row was not acting as an accidental
capability token for CLOSED.

## Closed-world impact

For the declared immutable integer-image scope covered by these fixtures, neither
direct instruction-budget exhaustion nor current local-constant outer fixed-point
exhaustion can be laundered into CLOSED merely by deleting the corresponding
`resource_limit` diagnostic. Equal bytes in another generation also do not
satisfy the omitted generation's obligations.

This says nothing about whole-ROM completeness. It does not establish complete
execution roots, overlay/write lifetimes, cache/TLB history, exception roots, RSP
identity, dynamic-code production, pointer-table immutability, or the absence of
unobserved runtime behavior. `WholeRom` must remain OPEN under its independent
obligations.

## Remaining gap

This result is specific to current `discover_image` candidate production and
`DeclaredStaticImages` solver rechecks. A future candidate producer that discards
its frontier instead of retaining it in typed `IndirectSite` state, or a schema
change that weakens candidate identity, could reopen the deletion attack. Table-
derived roots and other producer-specific fixed-point frontiers were not
separately forced through 512 iterations here.

The 520-stage fixture is intentionally adversarial and takes tens of seconds in a
debug test build. It is useful as a research regression, but integration may want
a cheaper equivalent if the same 512-pass boundary can be preserved without
weakening the assertion.

## Reproduction

```sh
git checkout research/solver-resource-limit-deletion-gpt56sol
cargo fmt --all -- --check
cargo test -p plaid-core --test solver_resource_limit_deletion -- --nocapture
cargo test -p plaid-core
cargo clippy -p plaid-core --tests -- -D warnings
```

## Integration recommendation

Do not change production solver logic for this hypothesis. Preserve or selectively
transplant the deletion-resistance tests, especially the equal-payload generation
case and the real outer fixed-point case. If the 512-pass fixture is too expensive
for routine CI, keep it as a bounded research regression or derive a cheaper way
to parameterize the outer-pass cap in test-only code rather than weakening the
proof obligation.
