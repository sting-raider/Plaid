# Solver target-dispatch monotonicity

Status: **VALIDATED**

Worker: `gpt56sol-solver-targetlookup-monotonicity-20261010`

Base: `main` at `211176e7a489fecf8331d02915ee982cd279cb62`

Branch: `research/solver-targetlookup-monotonicity-gpt56sol`

## Question

Can `Scope::DeclaredStaticImages` be made to report `CLOSED` by deleting only the importer-derived `uncorrelated_target` diagnostic for a retained trace-origin `TargetLookup` or `RuntimeLink` event?

This composes two existing rules:

- ADR-0009 requires closure to resist deletion of derived blockers/control facts.
- ADR-0012 keeps target lookup/runtime dispatch distinct from source-correlated executed indirect transfers. A target value is not a source-site identity.

The completed raw-indirect solver research was useful precedent, but it covers `IndirectTargetObserved`, which already has source-site correlation. This experiment targets the deliberately weaker `TargetLookup` / `RuntimeLink` primitives instead.

## Result

**Yes on current main.** The importer preserved `IndirectTargetObserved` in a raw ProgramMap collection, but reduced `TargetLookup` and `RuntimeLink` only to an `Unresolved { kind: "uncorrelated_target" }` row. If that derived row was deleted, its trace evidence record remained in the map but nothing structured told the solver what that evidence meant. A finite static image therefore changed from `OPEN` to `CLOSED`.

Baseline Actions run `37998865273`, job `114051729785`, against base `211176e7...`:

- no target-dispatch event control: `CLOSED`, expected;
- `TargetLookup` before edit: `OPEN`;
- delete only `uncorrelated_target`, retain its referenced trace evidence: solver returned `Closed` instead of expected `Open`;
- `RuntimeLink` before edit: `OPEN`;
- delete only `uncorrelated_target`, retain its referenced trace evidence: solver returned `Closed` instead of expected `Open`.

The focused baseline therefore had 1 pass and 2 intentional failures. The exact pinned Rabbitizer revision used by CI was `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` from `refs.lock.toml`.

## Candidate invariant

A source-uncorrelated target-dispatch primitive must survive independently of any importer-derived diagnostic. It must retain:

- target PC;
- import/execution generation;
- event kind (`TargetLookup`, including `delay_slot_entry`, or `RuntimeLink`);
- exact trace provenance.

Neither an equal decoded PC nor an unrelated indirect-target certificate can provide the missing source-site correlation.

## Candidate implementation

Commit `db5d61f8fa84b7fcedeaf072fbc16917e65474dc` adds:

- `TargetDispatchKind` and `ObservedTargetDispatch`;
- `ProgramMap::target_dispatch_observations` with a serde default;
- importer retention for both `TargetLookup` and `RuntimeLink` using the current import epoch as generation;
- merge union/canonicalization for the raw facts;
- validation that the target is aligned, provenance exists, and every provenance record is trace evidence;
- an independent solver blocker, `unresolved_raw_target_dispatch`.

The existing `uncorrelated_target` diagnostic remains present. The raw fact is an independent fail-closed primitive rather than a replacement for the human-readable diagnostic.

## Adversarial validation

`crates/plaid-core/tests/solver_target_dispatch.rs` exercises six cases:

1. deleting only the derived lookup diagnostic cannot manufacture closure;
2. deleting only the derived runtime-link diagnostic cannot manufacture closure;
3. target-PC equality with an already decoded executable block does not synthesize correlation;
4. a separately certified constant `JR` to the same target is a decoy and cannot launder the raw lookup;
5. lookup/link raw facts survive JSON round-trip, merge, merge idempotence, and same-target kind distinction;
6. forged non-trace provenance is rejected, while the no-dispatch control remains `CLOSED`.

Final hardened Actions run `37999472218`, job `114053756431`:

- focused target-dispatch matrix: **6 passed, 0 failed**;
- full `cargo test -p plaid-core`: **109 passed, 0 failed**;
- `cargo fmt --all -- --check`: pass;
- `cargo clippy -p plaid-core --all-targets -- -D warnings`: pass;
- `git diff --check`: pass.

Run `37999378776` also passed the focused matrix, full core suite, fmt and clippy, but its final CI checkpoint command failed because rustfmt had modified only the new test while that temporary auto-commit step staged production files only. That bookkeeping error was corrected; it was not a code/test failure. Run `37999472218` is the clean receipt.

## Reproduction

Baseline false-closure receipt is preserved in Actions run `37998865273`. The focused command is:

```sh
cargo test -p plaid-core --test solver_target_dispatch -- --nocapture
```

On the final research branch, run:

```sh
cargo test -p plaid-core --test solver_target_dispatch -- --nocapture
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --all-targets -- -D warnings
```

The spike under `spikes/060-solver-target-dispatch-monotonicity/` records the baseline and the exact candidate replacement recipe used to checkpoint the production diff through CI.

## Closed-world impact

This closes one deletion-bypass class in declared-static closure: a retained raw `TargetLookup` or `RuntimeLink` can no longer disappear semantically merely because one derived unresolved row is removed. The solver now sees the primitive independently and remains `OPEN`.

This does **not** prove that a target lookup was executed, identify a source indirect site, establish target-set completeness, or make whole-ROM closure possible. A future discharge mechanism would need independently validated source correlation or another sound semantic explanation; matching the target PC is insufficient.

## Remaining gaps

- Completeness of instrumentation that emits target-dispatch events is outside this experiment.
- There is no positive discharge certificate for a raw source-uncorrelated target dispatch; the candidate intentionally fails closed.
- Whole-ROM closure remains `OPEN` for the broader obligations in `docs/NEXT.md`.
- Integration should consider ProgramMap wire-version policy for the new optional field; new readers accept old maps through `#[serde(default)]`, while old readers that deny unknown fields will not accept maps containing the new field.

## Integration recommendation

Integrate the typed raw target-dispatch fact, importer/merge preservation, validation, independent solver gate, and regression matrix. Keep it semantically distinct from `ObservedIndirect`; do not reconcile by target-value equality or borrow an unrelated indirect certificate. When the raw-indirect solver branch is integrated, compose both gates rather than collapsing them into one event type.
