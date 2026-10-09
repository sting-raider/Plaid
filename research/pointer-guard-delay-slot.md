# Pointer-table guard delay-slot completeness

Result: **VALIDATED** for one bounded guard-path gap in the current scalar pointer-table recognizer.

## Scope and exact revisions

- Plaid integration base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.
- Pre-fix `crates/plaid-core/src/tables.rs` blob: `8be332e607ab3b20e36704a0d8acc09812030c7d`.
- `crates/plaid-core/src/discovery.rs` blob: `05bed1002b3f447d6ef1ee1de6d19ab9faf1bedf`.
- Pinned Rabbitizer: `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` from `refs.lock.toml`.
- Research branch: `research/pointer-guard-trap-gpt56sol`.

This work is deliberately separate from the completed pointer-table backing/alias immutability research. It only asks whether the recognized local guard path can actually reach the dispatch without an exceptional delay-slot instruction invalidating that local proof.

## Hypothesis

The table recognizer can accept a guarded dispatch even when the selected guard edge executes an exceptional branch delay slot, because `direct_cfg` conservatively records the edge after flagging `unsupported_delay_slot`, while `tables.rs` did not independently reject `Instruction::is_trap()` or Plaid's separately unsupported `syscall`, `break`, and `eret` opcodes in that selected-edge slot.

For branch-likely fallthrough where the slot is annulled, the physical slot must not be rejected merely because it is exceptional: the selected edge carries `DelaySlot::None` and does not execute it.

## Source-derived baseline

`discovery.rs` defines an unsupported instruction as invalid, a Rabbitizer trap, or opcode name `syscall`, `break`, or `eret`. For a control transfer with a delay slot, it computes `ds_valid` using that predicate and records `unsupported_delay_slot` when false. It nevertheless emits the branch/fallthrough CFG edges and continues recursive discovery.

Pre-fix `tables.rs` re-read a selected guard edge's delay slot when `edge.delay_slot != DelaySlot::None`, but rejected only invalid instructions, nested control transfers, or writes to the dispatch index. It did **not** reject traps or `syscall`/`break`/`eret`. The later straight-line prefix loop already rejected Rabbitizer traps, making the guard-slot omission especially visible.

At the exact pinned Rabbitizer revision, CPU `teq` is descriptor-marked `.isTrap=true`. `syscall`, `break`, and `eret` are valid decoded opcodes; Plaid's direct CFG treats them separately as unsupported.

## Fixture

`crates/plaid-core/tests/pointer_guard_trap.rs` starts from the existing guarded pointer-table synthetic shape:

- `SLTIU $t1,$a0,3` at `0x80000000`;
- guard branch at `0x80000004`;
- delay slot at `0x80000008`;
- scalar base construction, `SLL` by two, `ADDU`, `LW`, and `JR` dispatch;
- snapshot entries `0x80000040`, `0x80000050`, `0x80000040`.

Adversarial executed-slot cases use ordinary `BEQ $t1,$zero` (`0x11200016`) and replace the slot with:

| case | word | classification relevant to Plaid |
| --- | ---: | --- |
| `teq $zero,$zero` | `00000034` | Rabbitizer `isTrap=true`; deterministically traps |
| `syscall` | `0000000c` | Plaid direct-CFG unsupported opcode |
| `break` | `0000000d` | Plaid direct-CFG unsupported opcode |
| `eret` | `42000018` | Plaid direct-CFG unsupported opcode |

The control uses `BEQL $t1,$zero` (`0x51200016`) with physical `TEQ` in the slot. On the selected successful guard fallthrough, branch-likely semantics annul the slot and `direct_cfg` labels that selected edge `DelaySlot::None`.

## Executed observations

### 1. Unmodified recognizer reproduces the gap

Commit `ec458cd46a1f5b7e35d5e2c1ad8ecbe0a6b4a394` added a regression that intentionally asserted the observed pre-fix behavior. GitHub Actions run `37914945269`, job `113768726530`, passed on the unmodified recognizer.

For each of TEQ, SYSCALL, BREAK, and ERET:

1. `direct_cfg` contained `unsupported_delay_slot` at guard PC `0x80000004`;
2. the selected fallthrough edge still reached the dispatch block;
3. `analyze_indirect` still added table candidates `{0x80000040, 0x80000050}`.

The BEQL annulled-slot control also retained those candidates.

### 2. Desired regression fails before the fix

Commit `990b30754022a3e5d3650fc533e078e80c30bb93` inverted the adversarial assertions: executed exceptional slots must produce no table candidates, while the ordinary and annulled controls remain recognizable.

As expected, Actions run `37915126731`, job `113769321206`, failed in `Run adversarial pointer guard tests` against the still-unmodified recognizer. This is a direct red-to-green reproduction rather than an inference from source alone.

### 3. Minimal candidate fix turns the regression green

Commit `3a612623103e48ba1e19321644d08c5e2bdac008` changed only the selected-edge delay-slot validation in `tables.rs` to additionally reject:

```text
instruction.is_trap()
OR opcode_name in {syscall, break, eret}
```

No CFG edge semantics were changed. The check remains conditional on `edge.delay_slot != DelaySlot::None`, so an annulled branch-likely fallthrough does not inspect/reject the physical slot.

The final verification workflow at commit `9d7dbde5b11098166bd4e5c2297a2889d64350fb` passed in Actions run `37915267873`, job `113769787268`:

```sh
python3 experiments/pointer_guard_delay_slots.py
cargo test -p plaid-core --test pointer_guard_trap -- --nocapture
cargo test -p plaid-core
```

All three workflow steps passed. The deterministic reducer's JSON payload SHA-256 is:

`bb73eaff5f0555840e53dade7bc82374bf77e2882fcf191712dad1a9cc65839c`

The reducer records six selected-edge cases: ordinary BEQ/NOP, four executed exceptional BEQ slots, and the BEQL/TEQ annulled control.

## Instrumentation neutrality

No emulator or runtime reference implementation was instrumented. The experiment is a pure Plaid synthetic-CFG analysis using the exact pinned Rabbitizer dependency. The candidate patch changes only pointer-table candidate recognition. The full `plaid-core` test suite passed after the change.

## Result

**VALIDATED.** The pre-fix recognizer could attach pointer-table candidates to a local guarded-dispatch pattern whose selected edge necessarily encounters an instruction that Plaid's own direct CFG classifies as exceptional/unsupported before the dispatch. For this restricted recognizer, selected-edge delay-slot exceptionality is therefore a required guard-path completeness check.

The minimal branch patch rejects Rabbitizer traps and Plaid's `syscall`/`break`/`eret` unsupported set only when the selected edge executes the slot. It preserves the branch-likely annulled-fallthrough case.

## Limitations / what this does not prove

- This is **not** a pointer-table immutability proof and does not change `pointer_table_immutability_unproven`.
- This is **not** an exhaustive indirect-target or closed-world proof.
- It does not prove all guard shapes, cross-block guard propagation, joins, loops, call/return interactions, or exception-handler reachability.
- It does not claim that `direct_cfg` should globally suppress edges after unsupported delay slots. Conservative CFG reachability and local guard certification are different obligations; an exception handler may alter later control flow.
- The executed adversarial matrix uses the BEQ-selected fallthrough shape plus a BEQL annulment control. The code check applies to any recognized selected edge with a non-`None` delay slot, but every branch opcode/direction combination was not separately fixture-tested here.
- Rabbitizer metadata plus Plaid's direct-CFG unsupported policy are the oracle for this static-analysis consistency check. No physical N64 hardware behavior was measured.
- Conditional trap instructions that can be proven non-trapping by stronger value analysis could theoretically be accepted by a future recognizer; this restricted pass has no such proof and should remain conservative.

## Integration recommendation

**ADOPT** the semantic fix and regression after rebasing/rechecking current `main`.

The primary integrator should prefer keeping the table pass's selected-edge notion of "exceptional/unsupported" synchronized with `discovery.rs`. A future cleanup may centralize the shared predicate, but that refactor is not required to adopt this bounded fix and should not be bundled with broader CFG semantics changes.
