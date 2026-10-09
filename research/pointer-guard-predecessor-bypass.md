# Pointer-table guard predecessor bypass

Result: **VALIDATED** on canonical base `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.

This note is an isolated research-worker result. It is not merged into `main` and does not claim pointer-table immutability or whole-ROM indirect closure.

## Question

The current guarded pointer-table recognizer accepts the sequence

```text
SLTIU flag,index,count
BEQ/BNE flag,zero,...
<delay slot>
...
SLL / ADDU / LW / JR
```

when one selected branch edge reaches the dispatch block. Existing work already found two different local hazards:

- exceptional/trapping selected guard delay slots (`research/pointer-guard-delay-slot.md`), and
- alternate executable reachability **inside** the dispatch prefix after `block.start` (`research/pointer-prefix-bypass.md`).

The remaining question here is predecessor dominance: does the recognized `SLTIU` actually dominate the branch which is being used as proof of the index bound?

## Hypothesis

A valid executable root/edge at the guard branch can skip `SLTIU`, reuse an unconstrained old value in the flag GPR, and still take the selected dispatch edge. For a selected sequential fallthrough, entering the physical branch delay-slot word can likewise skip both compare and branch and then fall directly into the dispatch block.

If Plaid still emits bounded table candidates in either history, the candidate set is not justified by the recognized guard.

## Fixture

The existing synthetic table fixture was retained deliberately:

```text
80000000: 2c890003  sltiu t1,a0,3
80000004: 11200016  beq   t1,zero,exit
80000008: 00000000  nop
8000000c: 3c088000  dispatch block begins
...
80000020: 01000008  jr    t0
```

The snapshot contains `0x80000040`, `0x80000050`, `0x80000040`, so the intended finite candidate set is `{0x80000040, 0x80000050}`.

Normal execution reaches the dispatch only when `a0 < 3`. Entering at `0x80000004` with stale `t1=1`, however, falls through regardless of `a0`. Entering at `0x80000008` executes the word as an ordinary instruction and then reaches `0x8000000c` without either the compare or branch.

## Current-main counterexample

The red regression is `crates/plaid-core/tests/pointer_guard_predecessor_bypass.rs`.

Actions run `37969716423`, job `113952930173`, tested branch head `f91eba6b8b6ce5bcc044419c33e7e429fb7301fd` against unmodified `tables.rs`. Four of five tests failed as intended: an entry, direct edge, indirect candidate, and fixed-point discovery root at the guard branch all retained one `plaid-pointer-table-candidates/v0` record. The safe compare-entry/different-generation control passed.

The expanded red matrix at `11d9cc956c98056a33a69a81df92341f4715ffb1` ran in Actions `37969898503`, job `113953547622`. Its failures are especially useful because the complete observed values are printed:

- entries at `0x80000004` and `0x80000008` each retained evidence count `1` and table targets `[0x80000040,0x80000050]`;
- direct edges to both predecessor PCs did the same;
- indirect **candidate and observed** targets to both predecessor PCs did the same;
- fixed-point `discover_image` with an explicit root at `0x80000004` still retained the table certificate, while an explicit root at `0x80000008` happened to repartition enough state to suppress it;
- compare-entry and other-generation controls remained accepted.

Therefore this is not merely a locally malformed post-processing map. At least the guard-branch-root case survives Plaid's normal fixed-point discovery pipeline.

The build compiled the exact pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

## Independent semantic adversary

`experiments/pointer_guard_predecessor_bypass.py` does not invoke the Rust recognizer. It models only the causal fact the certificate needs:

```text
flag = (index < 3)
dispatch = (flag != 0)
```

For `index=3` and `index=0xffffffff`, normal execution does not dispatch. Starting at the branch with stale flag `1`, or at the sequential delay-slot instruction, does dispatch. The model also checks that compare entry, a different image/generation, an unrelated PC, and a delay-slot PC for a non-sequential remote branch target are not rejected by the proposed predicate.

Expected deterministic report SHA-256: `efde847c2abb489f786a1c143bfc079f6d32227ef1a5bfc8dfa0cfee53bf5c78`.

## Candidate fix

Candidate implementation commit: `0d257e8d500edbe8f0e813e06882c9d490782d07`.

The recognizer now rejects alternate executable reachability, in the same image and generation, to:

1. the recognized guard branch PC; and
2. the physical delay-slot PC only when the selected dispatch block is exactly the sequential `branch_pc + 8` path.

The second qualification is intentional. If a selected taken branch targets a non-sequential remote dispatch block, entering the delay-slot instruction by itself does not reproduce that taken transfer, so rejecting it merely because its address is nearby would be an unsound over-approximation of the guard dependency.

Sources checked are ProgramMap entries, direct-edge targets, and indirect candidate/observed targets. The selected guard edge itself targets `block.start`, so it does not self-reject.

Focused Actions run `37970010327` passes the expanded five-test matrix at the candidate-fix commit. A separate final workflow runs formatting, Clippy, the semantic reducer, focused regression, and the full `plaid-core` suite.

## Composition with prior work

This finding is complementary to, not a replacement for:

- `research/pointer-prefix-bypass.md`: alternate reachability in `(block.start, jr_site]`;
- `research/pointer-guard-delay-slot.md`: trapping/exceptional behavior on the selected guard delay-slot path;
- pointer-table physical/cache/TLB immutability research: whether the snapshotted data remains the same backing bytes for the relevant lifetime.

A future integrated guard certificate needs all applicable conditions. Passing one does not waive the others.

## Closed-world impact

A finite pointer-table target set cannot support indirect closure merely because bytes contain an `SLTIU` immediately before the branch. The proof must also establish that execution cannot enter after the compare while still reaching the dispatch under unconstrained predecessor state.

Without that dominance/reachability fact, the table's runtime index is not bounded by the recognized count, so treating the snapshot candidates as exhaustive would be unsound. The correct behavior is to withhold the table-derived exhaustive evidence and keep the indirect site OPEN unless another proof closes it.

## Limitations

- This is a synthetic ProgramMap/CFG regression, not a commercial-ROM prevalence measurement or a hardware behavior claim.
- The fixture directly exercises a BEQ selected fallthrough. The implementation's branch-PC rule is shape-independent, but every branch opcode/direction has not been separately fixture-tested.
- The delay-slot predecessor rejection is deliberately limited to a sequential selected dispatch. More complex predecessor paths require explicit CFG/dominance reasoning, not numeric address guessing.
- Raw indirect observations which have not been promoted into ProgramMap reachability are a separate solver/import obligation.
- This does not prove pointer-table immutability, aliases, cache visibility, executable lifetimes, exception-root completeness, or whole-ROM closure.

## Reproduction

On branch `research/pointer-guard-predecessor-bypass-gpt56sol`:

```bash
python3 experiments/pointer_guard_predecessor_bypass.py
cargo test -p plaid-core --test pointer_guard_predecessor_bypass -- --nocapture
cargo test -p plaid-core
```

To reproduce the current-main failure, check out red head `11d9cc956c98056a33a69a81df92341f4715ffb1` and run the focused test.
