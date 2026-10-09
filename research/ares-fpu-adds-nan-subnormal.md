# Exact-pinned ares `ADD.S` NaN/subnormal exception behavior

Result: **VALIDATED** for the bounded exact-pinned-ares question below.

This note records a reference-oracle experiment, not a platform-wide hardware proof and not a production implementation decision.

## Question and hypothesis

Can Plaid safely collapse every NaN input to VR4300 `ADD.S` into one generic Invalid Operation case?

Hypothesis: **no**. Exact pinned ares distinguishes at least two raw NaN classes plus subnormal input before destination writeback. One NaN class can complete and mutate the destination when Invalid is masked, while another NaN class and subnormal input raise Unimplemented Operation and suppress destination mutation. Therefore any future Plaid COP1 semantic model must retain raw input class, FCSR cause/enable state, and whether architectural destination writeback actually occurred.

## Exact revisions

- Plaid canonical base inspected: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- Research branch executed head: `15cd2fa41814f40ef8aa58f843ac8fb9413c1206`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`
- Mupen64Plus core: `ba95bab92a76744753bfe61470823a4937850ab0`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`

`refs.lock.toml` pins all four reference revisions above.

## Baseline source behavior

Pinned ares `ares/n64/cpu/interpreter-fpu.cpp` does the following for `FADD_S`:

1. clears the current FPU cause state after checking CU1;
2. classifies both source operands before arithmetic;
3. treats NaN inputs with fraction bit 22 clear as Unimplemented Operation;
4. treats subnormal inputs as Unimplemented Operation;
5. treats NaN inputs with fraction bit 22 set as Invalid Operation;
6. performs the host floating-point addition only if the pre-input check did not trap;
7. canonicalizes a NaN result to raw `0x7fbfffff`;
8. writes the destination FPR only after all checks complete.

The pinned ares helper is named `snan(f32)` but returns raw fraction bit 22. That name is unsafe to reuse as portable terminology.

Pinned `n64-systemtest` uses modern IEEE naming for the raw ranges instead:

- signalling NaN: `0x7f800001..0x7fbfffff` (fraction bit 22 clear);
- quiet NaN: `0x7fc00000..` (fraction bit 22 set).

Its COP1 test comments and vectors record hardware-test expectations that signalling NaNs are unsupported and cause Unimplemented Operation, while quiet NaNs are supported but signal Invalid Operation and produce the COP1 canonical NaN. That is consistent with the raw ares split while using the opposite names from the ares helper.

Pinned Mupen64Plus does **not** provide independent agreement for the same detailed behavior: its accurate FPU helper has TODO subnormal handling and a generic NaN-to-Invalid path. Pinned Gopher64 `ADD.S` is essentially host `f32 + f32` plus destination write and does not expose a matching pre-input FCSR classification path. Emulator consensus must therefore not be invented here.

## Instrumentation / fixture

No ares source was patched.

`spikes/044-ares-fpu-nan-exceptions/driver.cpp` reuses the existing headless ares integration from spike 003 and executes the real instruction word:

```text
0x46041180  ADD.S f6,f2,f4
```

through the interpreter fetch/decode path with:

- CPU and RSP recompilers disabled;
- CU1 enabled;
- FR=1;
- synthetic post-initialization CPU/FPU state;
- PC `0xffffffffa0000000`;
- destination FPR `f6` initialized to sentinel `0xa5a5a5a5deadbeef`.

The fixture records raw source values, initial/final FCSR, destination before/after, CPU exception code, EPC, and PC.

`spikes/044-ares-fpu-nan-exceptions/run.py` asserts the expected matrix, checks exact reference revisions and source markers, executes every case twice, compares the complete observation lists, and hashes the canonical JSON payload.

## Fixture matrix and observations

| Case | `fs` raw | Initial FCSR | Destination after | Final FCSR | CPU exception | Observation |
| --- | --- | --- | --- | --- | --- | --- |
| finite | `0x3f800000` (1.0) | `0x00000000` | `0x0000000040400000` (3.0) | `0x00000000` | 0 | control completes normally |
| NaN bit22 set, Invalid masked | `0x7fc00001` | `0x00000000` | `0x000000007fbfffff` | `0x00010040` | 0 | Invalid cause + sticky flag; canonical NaN is written |
| NaN bit22 set, Invalid enabled | `0x7fc00001` | `0x00000800` | sentinel unchanged | `0x00010800` | 15 (FPE) | Invalid cause + enable; trap suppresses destination writeback |
| NaN bit22 clear | `0x7fa00001` | `0x00000000` | sentinel unchanged | `0x00020000` | 15 (FPE) | Unimplemented Operation; destination not written |
| positive minimum subnormal | `0x00000001` | `0x00000000` | sentinel unchanged | `0x00020000` | 15 (FPE) | Unimplemented Operation; destination not written |

For every trapping case, EPC was `0xffffffffa0000000`, the address of the tested instruction.

The bit22-set masked case is the adversarial counterexample to `NaN -> always trap` as well as to `NaN -> no architectural write`: the operation completes, sets Invalid cause/sticky state, canonicalizes the result and mutates `f6`.

The bit22-clear case is the adversarial counterexample to `NaN -> generic Invalid`: it follows the Unimplemented Operation path instead.

## Commands and deterministic evidence

CI reproduction:

```sh
python3 -m py_compile \
  spikes/044-ares-fpu-nan-exceptions/run.py \
  spikes/003-ares-oracle/run.py
python3 spikes/044-ares-fpu-nan-exceptions/run.py
python3 spikes/044-ares-fpu-nan-exceptions/run.py
```

The exact-pinned CI checkout also cloned all four references at the revisions above before running.

Successful GitHub Actions run:

- run: `37915789882`
- job: `113771509628`
- generated result artifact: `11608993610`
- canonical result JSON SHA-256: `ab5df57e7fa9469b52aa225c8545a4cb4a95a54956ff19bc5a6432c89377ccbe`
- uploaded artifact ZIP SHA-256: `d39f2b1e2db7672600ed7c1627e4271bafffccdd5202c5b2fe842badb7575f29`

The runner executes the entire matrix twice internally and the workflow invokes the runner a second time, requiring the two reported result hashes to match. All checks passed.

## Instrumentation-neutrality check

The experiment does not modify the ares implementation. It uses a project-owned driver that initializes state and invokes the normal interpreter instruction path. The finite control verifies ordinary `ADD.S` execution and destination writeback in the same harness. Repeated executions produced byte-for-byte-equivalent canonical observation payloads.

This is stronger than source reading alone but remains an emulator/reference observation rather than a fresh hardware run.

## Result

**VALIDATED**: for exact pinned ares `ADD.S`, raw NaN classes and subnormal input are not semantically interchangeable, and exception enable state changes whether a bit22-set NaN reaches destination writeback.

For a future Plaid AOT/runtime COP1 model, it is unsafe to encode a single generic rule such as:

```text
if input_is_nan: invalid_operation
```

The model/test contract needs, at minimum for this instruction family:

- raw NaN-class discrimination consistent with VR4300 behavior;
- Unimplemented Operation as a distinct FCSR cause and unconditional FPE path;
- Invalid cause versus sticky Invalid flag distinction;
- Invalid-enable-dependent trap behavior;
- destination writeback suppression on raised FPE;
- canonical result behavior when the Invalid condition is masked and execution completes.

## Limitations / what this does not prove

- Only `ADD.S` was executed.
- Only FR=1 was exercised.
- Only one positive raw value from each NaN class and one positive subnormal input were executed.
- Negative NaNs, infinities, output subnormal handling, rounding modes, overflow/underflow/inexact interactions, double precision and conversions remain outside this experiment.
- ares was executed; Mupen64Plus and Gopher64 were source-compared only.
- `n64-systemtest` supplies pinned hardware-test expectations, but this worker did not run its ROM on physical N64 hardware.
- Agreement between ares and the pinned hardware-test corpus for these raw classes is useful evidence, not a proof that every ares FPU detail is hardware-correct.
- Nothing here establishes timing, pipeline coprocessor-index quirks, or recompiler behavior.

## Integration recommendation

**ADOPT** the raw-bit/FCSR/writeback cases as semantic test obligations when Plaid grows CPU COP1 arithmetic semantics. Do not adopt the source-local `snan`/`qnan` names, and do not use Mupen/Gopher agreement as a substitute for hardware-derived evidence where they currently disagree or omit the behavior.
