# Solver successful raw-store source closure

Status: VALIDATED

Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/solver-raw-store-source-closure-gpt56sol`

Claim: issue #4 comment `6090813124`

## Result

Current main can report `Scope::DeclaredStaticImages == CLOSED` while retaining a
primitive `ObservedWordStore` proving that a successful guest `SW` executed. This
is inconsistent with the declared-static solver's own instruction policy: every
memory opcode is rejected by `allowed_static_effect`, while the trace contract
explicitly defines `CpuWordStoreObserved` as a **successful aligned SW**.

The hole is independent of executable-destination mutation. A retained raw store
whose destination does not overlap executable backing still proves that an effect
excluded by the declared static scope executed. Before this branch,
`solver::solve` never consumed `word_store_observations`, so deleting or omitting
all derived facts could make that primitive execution evidence disappear from the
closure decision.

The smallest candidate fix adds a `dynamic_effect_outside_scope` blocker whenever
`Scope::DeclaredStaticImages` retains any successful word-store observation. The
blocker carries the raw observation evidence. It does not infer image identity,
physical aliasing, source lifetime, or generation from PC/value equality.

## Executable witness

`crates/plaid-core/tests/solver_raw_store_source.rs` builds a finite static image
containing only `J self; NOP`, which normally closes. It then injects a retained
successful store to ordinary cached RDRAM. The image has no explicit physical
backing, deliberately ruling out the separate executable-destination-overlap
mechanism.

Two adversarial positive cases are used:

1. source PC `0x90000000`, outside the declared executable universe, destination
   `0x80001000`;
2. source PC `0x80000000`, numerically equal to the declared block start, with the
   same import epoch/evidence and a stored value `0x08000000` equal to the first
   image word.

The second case actively attacks provenance laundering: PC, epoch, evidence-set
reuse, and payload equality do not turn a retained successful SW into the declared
`J` instruction. No source identity is invented from those equalities.

A no-store control remains CLOSED.

On unmodified main-derived solver code, Actions run `38003140656`, job
`114065718709`, compiled the regression and failed exactly as expected:

```text
running 3 tests
no_raw_store_control_remains_closed ... ok
retained_successful_store_outside_declared_universe_cannot_close_static_scope ... FAILED
pc_epoch_and_equal_payload_cannot_launder_successful_store_execution ... FAILED

left: Closed
right: Open
```

That is the false-CLOSED witness.

## Candidate fix and validation

Candidate solver commit: `03cca29ab0956a01a092bccbf8a20d5b668e7c78`

The fix is intentionally scope-local:

```rust
if scope == Scope::DeclaredStaticImages && !map.word_store_observations.is_empty() {
    add(
        "dynamic_effect_outside_scope",
        None,
        "declared static scope cannot include successful word-store execution",
        map.word_store_observations
            .iter()
            .flat_map(|w| w.evidence.clone())
            .collect(),
    );
}
```

Actions run `38003494204`, job `114066841424`, passed:

```sh
cargo test -p plaid-core --test solver_raw_store_source -- --nocapture
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --all-targets -- -D warnings
```

Focused regression: 3 passed, 0 failed.

Full `plaid-core`: 106 tests passed, 0 failed, including merge/import, solver,
history, fetch, PI-history, and pointer-table suites. Formatting and clippy also
passed.

The run fetched the repository-pinned Rabbitizer revision
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

## Composition and challenge to prior research

This result composes:

- ADR-0009: retained primitive evidence must not become irrelevant merely because
  a derived blocker/control fact is absent;
- ADR-0020: `CpuWordStoreObserved` is a successful aligned SW observation and is
  intentionally retained as a primitive fact;
- the solver's existing `allowed_static_effect` policy, which excludes all memory
  instructions in `DeclaredStaticImages`;
- the completed raw-indirect deletion-attack principle that successful execution
  observations cannot silently disappear from a CLOSED decision.

It also refines the completed `research/solver-raw-store-closure-gpt56sol` result.
That work correctly re-derives **executable-destination physical overlap** and
avoids guessing alias provenance. However, its two negative controls saying a
non-overlapping store or a store with no explicit physical mapping may leave
`DeclaredStaticImages` CLOSED are not valid as whole-scope closure controls: lack
of executable-write overlap only proves that particular mutation blocker is not
justified. The retained successful SW still violates the static execution subset.

The two fixes therefore answer different questions:

- source/effect closure: any retained successful SW keeps
  `DeclaredStaticImages` OPEN;
- destination mutation provenance: explicit physical overlap independently
  derives an executable-write blocker and remains important for broader future
  scopes where memory instructions may be allowed.

## Falsification / adversarial controls

The investigation tried to make the raw store harmless in three ways and failed:

- **non-executable destination:** rules out the prior executable-write-overlap
  mechanism, but current main still falsely closed;
- **same PC / epoch / evidence / equal payload:** cannot reconcile a successful
  SW with supplied `J` bytes or invent source identity;
- **no raw store:** the otherwise identical map remains CLOSED, showing the
  candidate fix does not perturb the baseline finite CFG.

No claim is made that the SW sensor is complete write coverage. Absence of an
observation still proves nothing about absence of stores.

## Closed-world impact

This closes one finite-scope monotonicity hole: a hand-edited or partial
`ProgramMap` can no longer retain concrete successful memory-instruction execution
while `DeclaredStaticImages` claims only its immutable non-memory subset executed.

It does **not** prove whole-ROM store/mutation completeness, establish the raw
store's image/lifetime identity, infer physical aliases, or make `WholeRom`
closable. Those remain separate obligations.

## Integration recommendation

Adopt the small solver blocker plus `solver_raw_store_source.rs` regression.
Preserve the raw observation evidence on the blocker and do not attempt to
"reconcile" it through PC, epoch, generation, or payload equality.

If the earlier executable-destination raw-store patch is integrated too, keep its
physical-overlap re-derivation but revise its two `DeclaredStaticImages == CLOSED`
negative controls: they should assert only that no `unresolved_executable_write`
blocker is invented, while the overall static solve remains OPEN because of
`dynamic_effect_outside_scope`.

The branch-only workflow is research scaffolding and need not be merged. No change
was merged into `main` by this worker.
