# Indirect constant-target certificates versus final delay-slot obligations

Result: **REJECTED** (the proposed certificate-level rejection is not required for closure safety under the current solver contract)

Worker: `gpt56sol-indirect-delay-slot-20261009`

## Revisions

- Plaid baseline: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- Executed experiment head: `e556fd3af9c15229f155b44b21a36e8e748eed8b`
- Pinned Rabbitizer: `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`
- GitHub Actions run: `37921311220`
- Runner: Ubuntu 24.04, Rust `1.99.0 (b940084d7 2026-09-28)`

## Question

Can Plaid's local or cross-block constant `JR`/`JALR` target certificate remain `closed_proof = Some(...)` when the indirect transfer's own delay slot is exceptional or contains nested control, or must the certificate itself be rejected to avoid manufacturing closure?

This is deliberately distinct from the pointer-table guard-delay-slot question. Here the delay slot belongs to the already-recognized indirect transfer itself; the certificate's job is to prove the finite target set for that transfer.

## Falsifiable hypothesis

The initial hypothesis was that `indirect.rs::certificate` and `indirect_chain.rs::certificate` return at the `JR`/`JALR` before checking the final delay slot, so an explicit trap (`TEQ`), `SYSCALL`, `BREAK`, `ERET`, or nested control transfer can coexist with a closed constant-target certificate. If that certificate can discharge or hide the delay-slot obligation in `solve()`, Plaid has a closure hole and the certificate should be rejected. If the solver independently re-derives the delay-slot obligation from instruction bytes and remains OPEN, then certificate-level rejection is unnecessary and would conflate target-set proof with exception/control-effect proof.

## Source inspection

### Plaid

On baseline `ae41bdba...`:

- `crates/plaid-core/src/indirect.rs::certificate` hashes and interprets the value-producing prefix, reaches the indirect site, captures the pre-delay-slot `rs` value, and returns `ConstantCertificate` immediately. The final delay-slot word is intentionally not part of the local certificate prefix.
- `crates/plaid-core/src/indirect_chain.rs::certificate` behaves analogously at the final indirect site. It validates predecessor control-flow delay slots while reconstructing the chain, but returns the final constant target before examining the final `JR`/`JALR` slot.
- Existing test `local_constant_target_is_certified_before_delay_slot_write` already establishes an important semantic clue: a normal delay-slot write to the jump source register does not change the captured jump target.
- `crates/plaid-core/src/discovery.rs::direct_cfg` independently classifies the transfer's delay slot. A slot is rejected when it is invalid, `is_trap()`, `syscall`, `break`, `eret`, or itself has a delay slot. Rejection leaves an explicit `unsupported_delay_slot` unresolved fact.
- `crates/plaid-core/src/solver.rs::solve` does not trust the map's unresolved set alone. It re-runs `direct_cfg` from the supplied instruction bytes and converts every re-derived unresolved item (except the narrow documented `unmapped_target` discharge case) into a blocker. It then also imports the map's unresolved items.

Therefore a target certificate and a delay-slot blocker are separate proof obligations in the current architecture.

### Exact pinned Rabbitizer

At `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`, `tables/tables/instr_id/cpu/cpu_special.inc` defines:

- `jr` and `jalr` with `.isJump=true`;
- `teq` with `.isTrap=true`.

Plaid's `crates/plaid-core/Cargo.toml` points directly at that same revision. The Actions workflow guards both `refs.lock.toml` and `Cargo.toml` before compiling, and the build log shows `rabbitizer v1.16.2 (...#724a49a5)` being compiled.

## Executable experiment

Added `crates/plaid-core/tests/indirect_delay_slot.rs` with four adversarial tests and no production-code changes.

### 1. Local certificate matrix

Fixture prefix:

```text
80000000: LUI t0, 0x8000
80000004: ORI t0, t0, 0
80000008: JR  t0
8000000c: <slot under test>
```

The jump target is therefore the known entry block `0x80000000`. Slot variants:

| case | word | direct-CFG expectation |
| --- | ---: | --- |
| `TEQ` | `0x00000034` | `unsupported_delay_slot` via `is_trap()` |
| `SYSCALL` | `0x0000000c` | `unsupported_delay_slot` |
| `BREAK` | `0x0000000d` | `unsupported_delay_slot` |
| `ERET` | `0x42000018` | `unsupported_delay_slot` |
| nested `J` | `0x08000000` | `unsupported_delay_slot` because the slot has its own delay slot |

For every variant the test requires all of the following simultaneously:

1. `direct_cfg` retains `unsupported_delay_slot`;
2. `analyze_indirect` still emits a constant `closed_proof` for target `0x80000000`;
3. `verify_constant` rechecks that target proof successfully;
4. `solve(..., Scope::DeclaredStaticImages)` reports `OPEN`;
5. the solve report still contains `unsupported_delay_slot`.

This deliberately tries to falsify the claim that a target certificate can waive the slot obligation.

### 2. Stale-certificate laundering attack

A clean `JR` + `NOP` image is analyzed first and closes under `DeclaredStaticImages`. Only the delay-slot word is then mutated, first to `TEQ` and then to nested `J`, while the old analyzed `ProgramMap` and old closed-target certificate are retained.

This is the strongest counterexample attempt because the local certificate hash does not cover the final slot. As expected for a target-only certificate, `verify_constant` still returns true: the jump target did not change.

The important result is that `solve()` re-derives control flow from the mutated bytes, rediscovers `unsupported_delay_slot`, and remains `OPEN` in both cases. A stale map cannot launder the changed slot into closure.

### 3. Cross-block certificate

Fixture:

```text
80000000: LUI t0, 0x8000
80000004: J   0x80000010
80000008: ORI t0, t0, 0       # predecessor J delay slot
8000000c: NOP
80000010: JR  t0
80000014: TEQ zero, zero      # final JR delay slot
```

The unique predecessor chain establishes `t0 = 0x80000000`. The test confirms the producer is `plaid-cross-block-constant/v0`, the target certificate verifies, and the solver nevertheless remains `OPEN` with `unsupported_delay_slot`.

### 4. Normal-slot control and decoder guard

A `JR` + `NOP` control fixture must still close under `DeclaredStaticImages`; this protects against "fixing" the experiment by globally invalidating indirect delay slots. The same test confirms the pinned decoder reports `TEQ` as a trap and nested `J` as an instruction with a delay slot.

## Commands

The branch-only workflow `.github/workflows/research-indirect-delay-slot.yml` executes:

```sh
grep -F 'rev = "724a49a5b4dbfb99f1a9e6992e63964fd29c90c8"' refs.lock.toml
grep -F 'rev = "724a49a5b4dbfb99f1a9e6992e63964fd29c90c8"' crates/plaid-core/Cargo.toml
cargo test -p plaid-core --test indirect_delay_slot -- --nocapture
cargo test -p plaid-core
```

Reproduction from the isolated branch:

```sh
git checkout research/indirect-delay-slot-gpt56sol
cargo test -p plaid-core --test indirect_delay_slot -- --nocapture
cargo test -p plaid-core
```

## Deterministic observations

Actions run `37921311220` at `e556fd3af9c15229f155b44b21a36e8e748eed8b`:

- exact Rabbitizer pin guards: PASS;
- bounded experiment: **4 passed, 0 failed**;
- stale-certificate laundering case: PASS (solver remained OPEN after slot mutation);
- local exceptional/nested matrix: PASS;
- cross-block final-slot case: PASS;
- normal `NOP` control: PASS;
- full `cargo test -p plaid-core`: **107 passed, 0 failed** including the four new tests.

No Plaid production source was modified, so instrumentation-neutrality is trivial: the experiment observes existing behavior through public analysis/solver APIs.

## Result

**REJECTED**: the proposed certificate-level rejection is not required for the tested closure-safety property.

The source-level suspicion was half correct: local and cross-block constant-target certificates really can remain closed when the final indirect delay slot is exceptional or nested control. But that does **not** manufacture a closed executable CFG. Under the current contract, `closed_proof` proves the indirect target set, not that the transfer completes without a delay-slot exception/control complication. The solver independently re-derives and preserves the delay-slot obligation from bytes.

Changing `verify_constant` merely to make `closed_proof` disappear for these cases would duplicate the CFG/effect obligation and erase a still-valid fact: if the indirect transfer completes, its register-derived target is the certified constant. More importantly, such a change is unnecessary for the tested fail-closed property.

## Limitations

This experiment does **not** prove:

- that all possible MIPS delay-slot exceptions are modeled; `direct_cfg` currently covers its explicit unsupported classification, not arbitrary runtime faults such as TLB/address/load/store exceptions;
- exception-vector reachability or exception-state semantics;
- correctness of arbitrary nested-control behavior on real R4300 hardware;
- that future solvers will preserve this obligation split;
- whole-ROM closure or native completeness;
- that a target-only certificate should be accepted by every future consumer without also checking the relevant CFG/effect obligations.

The regression specifically protects the present solver contract: a consumer that uses `closed_proof` outside `solve()` must not reinterpret it as "this indirect transfer and its delay slot are fully modeled."

## Integration recommendation

**ADOPT** the regression/contract test (or equivalent) if the primary integrator wants this separation permanently executable. **REJECT** a production change that simply invalidates otherwise-correct constant-target certificates solely because the final slot has an independently represented `unsupported_delay_slot` obligation.
