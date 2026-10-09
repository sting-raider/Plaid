# Solver cross-fragment direct-edge deletion attack

Status: **REJECTED** on canonical base `211176e7a489fecf8331d02915ee982cd279cb62`.

## Question

Can `Scope::DeclaredStaticImages` be made to report `CLOSED` by splitting one executable `(image,generation)` across non-overlapping `CodeImage` fragments, arranging a direct control-flow transfer from one fragment into a declared block in another, and then deleting the required `DirectEdge` fact?

The suspected seam was the solver's special handling of `unmapped_target`: `direct_cfg` is rerun separately for each supplied fragment, and an out-of-fragment target is allowed to stop being an unresolved blocker when the global ProgramMap already contains a block start at that exact `CodeAddress`.

If that suppression also erased the edge obligation, a hand-edited ProgramMap could manufacture closure in violation of ADR-0009.

## Canonical inputs

- Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`
- Rabbitizer: `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`
- Rust toolchain: repository `rust-toolchain.toml` (`stable`, `rustfmt`, `clippy`)

No emulator behavior is needed for this bounded solver property. The relevant executable oracle is Plaid's own `direct_cfg` using the exact pinned Rabbitizer revision.

## Adversarial matrix

`crates/plaid-core/tests/solver_cross_fragment.rs` constructs and executes three cases against production `direct_cfg`, `merge_maps`, and `solve`:

1. **Cross-fragment jump, edge deletion.** Fragment A at `0x80000000` executes `j 0x80000010`; fragment B, with the same image/generation, starts a decoded block at `0x80000010`. The intact merged map closes under `DeclaredStaticImages`. Deleting only A's jump edge must make it OPEN even though B's target block still exists.
2. **Equal-payload wrong-generation decoy.** The target fragment has the same guest PC and instruction payload but generation 1 while the source is generation 0. It must not satisfy the generation-0 target identity.
3. **Cross-fragment fallthrough, edge deletion.** Fragment A ends in an ordinary integer instruction whose required fallthrough is the start of fragment B. The intact map closes; deleting the fallthrough edge must make it OPEN.

The controls intentionally make target bytes and/or numeric PCs tempting substitutes. No conclusion is derived from payload equality.

## Result

The false-CLOSED hypothesis was rejected.

The focused matrix passed all three cases in GitHub Actions run `38003697512`, job `114067504231`, at tested commit `600ce0593dc26cd26b6f0736b3d76fcc4b1a02a7`:

- deleted cross-fragment jump -> `OPEN` with `missing_decoded_edge`;
- equal-payload same-PC wrong-generation target -> `OPEN` with `unresolved_direct_target` and `unmapped_target`;
- deleted cross-fragment fallthrough -> `OPEN` with `missing_decoded_edge`.

The same run compiled Rabbitizer from exact revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`, passed `cargo fmt --all -- --check`, the focused 3-test adversarial matrix, the full `plaid-core` suite (106 tests including the new matrix), and `cargo clippy -p plaid-core --tests -- -D warnings`.

The earlier run `38003652728` is **not semantic evidence**. It stopped at `cargo fmt --all -- --check` before the adversarial tests executed. Commit `600ce059...` changes only formatting of the test call; no assertion was weakened.

## Why the attack fails

The important ordering is in `discovery::direct_cfg`:

1. when a branch/jump is decoded, the required `DirectEdge` is inserted immediately;
2. its target is queued for traversal;
3. only later, when traversal reaches a PC outside the current fragment, `direct_cfg` emits `unmapped_target`.

Non-control fallthrough at the end of a fragment follows the same causal shape: the fallthrough `DirectEdge` is inserted before the outside-fragment target becomes unresolved.

`solver::solve` then independently compares every re-derived `expected.direct_edges` fact with the ProgramMap and emits `missing_decoded_edge` before it processes the expected unresolved rows. The later `unmapped_target` suppression therefore removes only a redundant "this fragment has no bytes here" blocker when another declared block supplies the exact target identity. It does **not** remove the edge obligation.

The target check also uses full `CodeAddress` identity. A same-PC/equal-byte block in a different generation does not discharge the source generation's target.

## Closed-world impact

For this bounded static-scope property, split instruction sources do not create the suspected deletion-resistance hole. A target block's existence cannot launder a missing cross-fragment direct jump or fallthrough. This preserves the ADR-0009 invariant that deleting required control-flow facts cannot manufacture finite static closure.

This result does **not** strengthen `WholeRom` closure. It says nothing about dynamic image/generation construction, overlays, executable lifetimes, stale I-cache residency, TLB-context identity, exceptions/interrupts, indirect target exhaustiveness, mutation completeness, or whether the supplied `CodeImage` bytes themselves are authentically bound to their identities. Those remain independent obligations.

## Integration recommendation

No production solver fix is justified for this hypothesis. Retain the focused regression matrix, or an equivalent cross-fragment deletion test, because the behavior relies on a subtle but sound ordering between edge derivation and `unmapped_target` discharge. Do not weaken the edge comparison when future work generalizes fragmented executable sources.

## Reproduction

```sh
cargo fmt --all -- --check
cargo test -p plaid-core --test solver_cross_fragment -- --nocapture
cargo test -p plaid-core
cargo clippy -p plaid-core --tests -- -D warnings
```
