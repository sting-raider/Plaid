# ERET target provenance

Result: **PARTIAL**

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Exact upstream pins:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Question

May a whole-ROM closure certificate infer every reachable `ERET` target solely from PCs previously captured by exception/NMI entry, or can guest code independently program the return target through CP0?

## Hypothesis

The original hypothesis had two parts:

1. Guest writes to EPC make ordinary `ERET` an independently programmable control transfer, so capture-only target provenance is unsound.
2. All three pinned emulator references select ErrorEPC when ERL is set, making the same rule apply uniformly to the error-return path.

Part 1 is supported. Part 2 is rejected by the pinned Mupen pure interpreter.

## Baseline Plaid behavior

At the tested Plaid base, `crates/plaid-core/src/discovery.rs` classifies `eret` with `syscall` and `break` as unsupported. `crates/plaid-core/src/indirect.rs` likewise refuses to analyze through `eret`. That current fail-closed behavior is compatible with this result; this research does not propose making `ERET` statically closed by default.

## Exact-source observations

### ares

`ares/n64/cpu/interpreter-scc.cpp` at the exact pin:

- `setControlRegister` case 14 assigns `scc.epc = data`.
- case 30 assigns `scc.epcError = data`.
- `MTC0`/`DMTC0` feed `setControlRegister` after the privilege/COP0 checks.
- `ERET()` uses `epcError` while `status.errorLevel` is set and otherwise uses `epc`, then clears the corresponding status level.

Therefore an ordinary ERL=0 `ERET` target is the current EPC value, not necessarily the EPC value last written by exception entry.

### Gopher64

`src/device/cop0.rs` at the exact pin:

- CP0 write masks make both EPC and ErrorEPC fully writable (`u64::MAX`).
- `mtc0` and `dmtc0` route through the masked CP0 write helper.
- `eret` selects ErrorEPC while ERL is set and otherwise EPC.

This independently agrees with ares for both guest-writable EPC and the ErrorEPC selector.

### Mupen64Plus Core

`src/device/r4300/mips_instructions.def` at the exact pin:

- `MTC0` case `CP0_EPC_REG` assigns `cp0_regs[CP0_EPC_REG] = rrt32`.
- case `CP0_ERROREPC_REG` assigns `cp0_regs[CP0_ERROREPC_REG] = rrt32`.
- ordinary ERL=0 `ERET` clears EXL and executes `generic_jump_to(... CP0_EPC_REG)`.
- **counterexample to the original uniform-selector hypothesis:** if ERL is set, this pinned pure-interpreter path emits `error in ERET` and stops instead of jumping to ErrorEPC.

Thus Mupen supports the common guest-EPC conclusion but is not an oracle for ErrorEPC-return behavior at this pin.

### n64-systemtest

The exact pinned `src/tests/privilege/mod.rs` provides independent hardware-facing test intent: `run_mode_program_with_cop0` constructs a status with EXL set, executes `mtc0 {entry}, $14`, waits the required nops, then executes `eret`. The supplied `entry` is a variable test-program address. Many privilege/segment tests use this helper.

That fixture would be nonsensical if `ERET` were restricted to a previously exception-captured EPC. It is strong independent evidence for guest-programmed EPC as an architecturally meaningful `ERET` target source, although this worker did not run the suite on physical hardware.

## Executable adversarial model

`experiments/eret-target-provenance/model.py` models versioned EPC/ErrorEPC writes and compares:

- an intentionally unsound policy that remembers only the last exception/error capture; and
- a generation-aware policy that uses the currently selected return-register generation and fails closed after unknown writes.

Fixed adversaries cover:

- exception-captured EPC overwritten to a different guest target;
- guest-written EPC with no prior capture;
- same-value EPC overwrite, where value equality hides a provenance-generation change;
- unknown EPC mutation;
- the disputed ERL/ErrorEPC behavior across the three exact reference profiles.

A deterministic 100,000-history common-EPC fuzz generated 624,838 `ERET` events. The capture-only policy produced:

- 136,420 wrong targets;
- 127,590 missing targets;
- 67,605 same-value provenance substitutions.

The generation-aware policy retained 396,023 known targets and left 228,815 selected-register states unresolved after unknown writes.

Repeated execution produced byte-identical stdout.

Hashes:

- `model.py`: `23350e13ccfa6df122aa25a829471ce688c4dd1afbc3556fe7e2aae0ab2189b1`
- stdout: `7d94d6f6c7692ef39ff288b2656123d7678e1a7eb3f7e6fea883cb5fcc8a462e`
- canonical report: `994d5fa3a83c7ced1ad2ebc40c4fbf9b1c95f1b298fe2f4d94b243a41969b530`

## Reproduction

Local model:

```bash
python3 -m py_compile experiments/eret-target-provenance/model.py
python3 experiments/eret-target-provenance/model.py
```

Exact-source recheck after preparing the pinned reference checkouts:

```bash
python3 experiments/eret-target-provenance/verify_sources.py \
  --plaid . \
  --ares /tmp/refs/ares \
  --gopher64 /tmp/refs/gopher64 \
  --mupen /tmp/refs/mupen64plus-core \
  --systemtest /tmp/refs/n64-systemtest
```

`verify_sources.py` rejects revision drift before checking the semantic source anchors.

## Consequence for Plaid

A reachable ordinary `ERET` must be treated as a CP0-register-indirect control transfer unless Plaid can prove the current EPC value at that site. Exception-entry evidence alone is insufficient because guest `MTC0` can replace EPC, including with the same numeric value but a different provenance generation.

A future bounded ERET certificate should therefore:

1. prove the `ERET` itself is reachable in a mode where it can execute;
2. identify which architectural return source is selected for the declared semantic scope;
3. track every mutation source for that CP0 register over the relevant lifetime, including exception capture, guest CP0 writes, reset/restore and any other state restoration;
4. carry value-flow/provenance for the current register generation, not merely a value match;
5. add the proven finite target set to control-flow closure, or remain unresolved if the current value cannot be bounded;
6. keep the ERL/ErrorEPC rule open until a stronger oracle resolves the ares/Gopher versus pinned-Mupen disagreement.

A statically proven constant `MTC0 EPC` may eventually permit a finite target certificate. The finding does **not** require every ERET to remain permanently unresolved; it requires the proof to flow through the current CP0 register generation rather than through exception-entry history alone.

## Instrumentation neutrality

No emulator source was patched for this bounded result. The local executable is a standalone replay model, so guest timing/state neutrality is not applicable. The exact-source guard is read-only.

## Limitations / not proved

This result does not prove:

- physical-N64 ErrorEPC/ERL `ERET` behavior;
- which emulator is correct for the disputed ERL case;
- arbitrary-ROM reachability of any ERET site;
- a production EPC/ErrorEPC dataflow analyzer;
- complete CP0 mutation provenance through save-state restore, reset, debugger intervention or every execution mode;
- exception-handler byte provenance or whole-ROM closure by itself.

The worker environment could execute the standalone model but could not clone/build the exact emulator pins locally because outbound GitHub DNS was unavailable. The branch includes an exact-pin source guard/workflow so the source contract is reproducible independently.

## Integration recommendation

**ADOPT** the common-EPC invariant: do not derive an ERET target from exception-capture history alone; require current EPC generation/value provenance or keep the edge unresolved.

**INVESTIGATE** ErrorEPC/ERL hardware semantics separately. Do not turn the ares/Gopher behavior into a platform-wide rule while the exact pinned Mupen reference disagrees.
