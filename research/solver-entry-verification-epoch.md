# Solver deletion resistance for dirty-entry verification epochs

Result: **VALIDATED**

Worker: `gpt56sol-solver-entry-verification-epoch-20261010`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/solver-entry-verification-epoch-gpt56sol`

## Question

Can `Scope::DeclaredStaticImages` report `CLOSED` after a ProgramMap retains an
`ObservedEntryVerification` from a later invalidation epoch, but the
`ExecutableWrite` / invalidation fact that advanced that epoch has been deleted?

This is a deletion-resistance question, not a claim that byte equality proves a
write or a restored executable lifetime.

## Prior contracts composed

- ADR-0009 requires the finite solver to resist hand-edited deletion of blockers
  and control facts. Removing a derived row must not manufacture closure.
- ADR-0022 deliberately preserves a dirty-entry byte verification as a typed
  ProgramMap fact whose `generation` is the **verification epoch**, separate from
  the compiled entry's code generation.
- `merge.rs` initializes the import epoch at zero and advances it on
  `TraceEvent::Invalidate`; `EntryBytesVerified` records the current epoch in
  `ObservedEntryVerification`.
- The existing
  `verified_old_entry_explains_only_pending_targets_before_invalidation` test
  demonstrates the intended chronology: an old generation-0 entry can be
  verified in epoch 1 and used only for a pending target before another
  invalidation.

## Current-main counterexample

A minimal finite static map contains one normal entry/block for:

```text
0x80000000: J 0x80000000
0x80000004: NOP
```

The adversarial matrix adds a typed trace-provenance entry verification without
changing the instruction bytes.

1. Verification epoch 0, no executable write: `CLOSED` (control).
2. Verification epoch 1 plus a retained global Unknown `ExecutableWrite`: `OPEN`
   with `unresolved_executable_write` (control).
3. Delete only that write while preserving the independently typed epoch-1
   verification: `ProgramMap::validate()` accepts the map and current-main solver
   returns `CLOSED`.

The third case violates ADR-0009. The surviving typed fact already proves that
this trace session had advanced past epoch zero; byte equality does not erase the
ordered invalidation history.

### Baseline executable receipt

Regression head (solver unchanged from canonical base):
`7687e1f3654dbf88506e84d58c96b6c4fb7ea0e0`

GitHub Actions run `38003585288`, job `114067133066`:

```text
thread 'deleting_invalidation_cannot_launder_post_epoch_entry_verification' panicked
assertion `left == right` failed
  left: Closed
 right: Open
```

The build used the pinned Rabbitizer revision
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` from `refs.lock.toml`.

## Candidate fix

`solver.rs` now treats every retained `ObservedEntryVerification` with
`generation != 0` as a blocker under `Scope::DeclaredStaticImages`:

`entry_verification_after_invalidation`

The rule intentionally does **not** compare the verification epoch to the entry's
code generation. They are different identity domains. Numeric equality such as
`code generation = 1` and `verification epoch = 1` cannot reconcile them.

Epoch-zero verification stays accepted because it does not by itself prove prior
invalidation chronology. Whole-ROM closure remains independently OPEN under its
existing obligations.

The blocker is conservative: it does not reconstruct deleted invalidation ranges,
number of invalidations, mutations, copies, restored lifetimes, or causality from
payload equality. A future lifecycle certificate may discharge richer history;
this patch only prevents a currently demonstrated false-CLOSED path.

## Adversarial controls

The focused regression covers:

- epoch-zero verification remains CLOSED in the finite immutable scope;
- epoch-one verification with the write retained is OPEN;
- deleting only the write still remains OPEN after the candidate fix;
- unchanged/same instruction bytes do not launder the epoch;
- numeric equality between code generation and verification epoch does not merge
  the domains;
- changing the `source_unit` evidence from `Trace` to `Static` is rejected by
  `ProgramMap::validate()`.

No provenance is inferred from equal values or before/after byte equality.

## Fixed executable receipts

Candidate fix commit:
`929cf8023e5d15684c40528f2eb8b9adb4a4a807`

GitHub Actions run `38003719656` passed both:

```text
cargo test -p plaid-core --test solver_entry_verification_epoch -- --nocapture
cargo test -p plaid-core
```

Hardened adversarial test head:
`1801e02520c2663b5ee917e1ccb71ae4f886268d`

GitHub Actions run `38003770040` also passed both the focused regression and the
full `plaid-core` suite.

## Reproduction

```bash
cargo test -p plaid-core --test solver_entry_verification_epoch -- --nocapture
cargo test -p plaid-core
```

To reproduce the original bug, run the focused test at regression head
`7687e1f3654dbf88506e84d58c96b6c4fb7ea0e0`. To verify the fix and adversarial
controls, run it at `1801e02520c2663b5ee917e1ccb71ae4f886268d` or later on this
research branch.

## Closed-world impact

A finite static certificate cannot claim immutable executable closure while
retaining typed evidence that its trace session already crossed an invalidation
epoch, merely because the separately derived write row was removed. The primitive
verification epoch must remain proof-relevant.

This closes one solver deletion-resistance hole only. It does not prove complete
invalidation sensing, restored-entry lifetime, overlay/cache lifetime, write
coverage, or whole-ROM executable closure.

## Integration recommendation

Adopt the 12-line solver guard plus focused regression. Keep the epoch domains
separate and do not generalize this into equality-based generation reconciliation.
A later explicit lifecycle verifier can replace this conservative blocker when it
can prove the full invalidation/restore chronology rather than suppressing it.
