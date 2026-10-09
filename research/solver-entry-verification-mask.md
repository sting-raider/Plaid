# Solver deletion resistance for verified restricted entries

Result: VALIDATED.

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/solver-entry-verification-mask-gpt56sol`

## Question

Can a hand-edited/imported ProgramMap manufacture `DeclaredStaticImages` closure by deleting the derived `restricted_entry` unresolved fact while retaining an `ObservedEntryVerification` whose `register_mask` is nonzero?

This matters because ADR-0009 requires the finite solver to re-derive closure obligations rather than trusting removable diagnostics.

## Source contract composed

The existing discovery path already carries two representations of this condition:

1. `TraceEvent::EntryInstalled { unit, pc, register_mask }` records the dynarec entry and its register-state mask.
2. `TraceEvent::EntryBytesVerified { unit, pc, register_mask, words }` is accepted by `DiscoveryTrace::validate()` only when the same `(pc, register_mask)` is present in that unit's installed-entry set and the verified words equal the completed unit words.
3. `import_trace` emits `Unresolved { kind: "restricted_entry", ... }` for an installed entry whose mask is nonzero.
4. The same import retains `ObservedEntryVerification { entry, register_mask, source_unit, generation, evidence }`.
5. `ProgramMap::validate()` requires the verification entry to exist and its `source_unit` to name Trace evidence.

This composes the earlier `research/mupen-verified-dirty-entries.md` result, which deliberately retained entry masks and existing modeling blockers while treating byte verification as a snapshot fact rather than execution/lifecycle proof. The existing merge regression `verified_entry_requires_exact_completed_words_and_installed_mask` independently exercises the exact completed-word and installed-mask coupling.

Before this branch, `solver::solve()` consumed `map.unresolved` but ignored `map.entry_verifications`. Thus deleting only the derived unresolved item erased the closure blocker even though the retained verification still recorded the unsupported nonzero mask.

## Reproduction

Commit `a10eae657cd36e80eecec559f37467eb8c815ac8` adds two solver regressions on otherwise closed immutable integer code:

- nonzero-mask retained verification: must remain OPEN with `restricted_entry`;
- zero-mask retained verification: must remain CLOSED and must not invent a blocker.

GitHub Actions run `38003554656`, job `114067036436`, executed the tests on the current-main implementation before the candidate fix. Result: **FAILED as expected**. Eight of nine solver tests passed; only `retained_nonzero_entry_verification_cannot_be_closed_by_deleting_derived_blocker` failed because the solver returned `Closed` where the test required `Open`. The zero-mask control passed.

The decisive failure was:

```text
assertion `left == right` failed
  left: Closed
 right: Open
```

This directly falsifies deletion resistance for this retained fact class.

## Candidate fix

Commit `3406e7f76d4e2718f6b03b1a7876b2a61a9dec6a` adds one fail-closed loop to `solver::solve()`:

- each retained `ObservedEntryVerification` with `register_mask != 0` contributes a `restricted_entry` blocker at the verified entry;
- blocker evidence retains the verification event evidence plus the source-unit trace evidence;
- `register_mask == 0` remains neutral.

No ProgramMap schema, importer, trace format, reference instrumentation, or native path changes are required.

## Validation

The focused solver suite first went green with the candidate fix in Actions run `38003742113`.

Expanded Actions run `38003937745` then passed:

- `cargo test --locked -p plaid-core --test solver -- --nocapture`;
- `cargo test --locked -p plaid-core`;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`.

An intermediate expanded run also showed that the complete `plaid-core` test suite was already green before a rustfmt-only correction to the new regression.

## Adversarial interpretation

This deliberately attacks a same-map deletion, not value equality. The mask value is retained as an explicit raw fact; deleting a separately derived diagnostic must not make that fact disappear semantically.

The regression also protects the opposite direction: merely having an entry verification is not enough to block closure. A zero mask remains admissible for this particular obligation.

## Closed-world impact

A finite static solver must not report CLOSED when retained trace-derived evidence itself says an entry requires register-state assumptions that Plaid does not model. Re-deriving the blocker makes closure monotonic against deletion of the importer-generated diagnostic for this evidence class.

This does **not** make a whole-ROM result native-complete, prove that the trace evidence is authentic, model the meaning of individual Mupen register-mask bits, prove arbitrary entry-state reachability, or establish that `entry_verifications` is a complete census. Those are separate obligations.

## Reproduction commands

```bash
cargo test --locked -p plaid-core --test solver -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

The branch-only workflow is `.github/workflows/research-solver-entry-verification-mask.yml`.
