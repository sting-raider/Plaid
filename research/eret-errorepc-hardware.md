# VR4300 ERL / ErrorEPC ERET contract

Status: **VALIDATED**

Worker: `gpt56sol-eret-errorepc-hardware-20261010`

Canonical base inspected: `211176e7a489fecf8331d02915ee982cd279cb62`

Exact pins from `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Result

The remaining ERL=1 ERET uncertainty from `research/eret-target-provenance-gpt56sol` is resolved for the declared VR4300 architectural scope:

- when Status.ERL=1, ERET selects the current ErrorEPC value as the return PC and clears ERL;
- when ERL=0, ERET selects the current EPC value and clears EXL;
- ErrorEPC is software-writable, so an ERL=1 ERET target is not soundly recoverable only from the most recent reset/NMI capture;
- same-value ErrorEPC rewrites are still distinct writer generations and must not be coalesced by value equality.

Exact pinned Mupen64Plus pure-interpreter behavior disagrees with this architecture contract by stopping on ERL=1 ERET. That disagreement is preserved below rather than treated as hardware truth.

## Target-hardware documentation

NEC VR4300 User's Manual `U10504EJ7V0UM00` supplies the decisive architectural evidence:

- the ErrorEPC register is documented as read/write and as the restart/resume virtual address for reset/NMI error-level handling;
- the CP0 writer/user timing table lists ERET as consuming `EPC or ErrorEPC` and Status;
- the ERET description specifies ErrorEPC/ERL return for error level and EPC/EXL return otherwise, with LLbit cleared.

This is the target processor specification, not an emulator-majority inference.

## Independent hardware-facing test evidence

Exact pinned `n64-systemtest` contains `ErrorEPCNoMasking` in `src/tests/cop0/mod.rs`. The test writes several 64-bit patterns through `set_errorepc`, reads ErrorEPC back, and expects exact equality. This independently supports software programmability/full-width storage of ErrorEPC.

This worker did not execute a new physical-console run, so no fresh hardware execution receipt is claimed. The test source is used as independent hardware-facing evidence, not as a substitute for a console result.

## Exact pinned reference comparison

`experiments/eret-errorepc-hardware/source_guard.py` rejects revision drift and guards the relevant exact-source anchors. Successful CI source hashes:

- ares `interpreter-scc.cpp`: `df7252d14f532e9fa44a39147be05afeb9851196a7d5249ab325900cee2aa722`
- Gopher64 `cop0.rs`: `bf40a5ee9667d93a3819c7745d23a2d3743eb7a63c29ab3888771d77141aa464`
- Mupen64Plus `mips_instructions.def`: `c0f7e42835386ecd8bc623fe6115bc1b2d7facd93799c0308a76bef138622a7d`
- n64-systemtest `tests/cop0/mod.rs`: `ae28a0e9241d666545e819ba65b2a6be18b4023fe5d77ac657084434d0f84c89`

Guarded facts:

- **ares:** CP0 register 30 writes `scc.epcError`; ERL=1 ERET loads PC from it and clears errorLevel.
- **Gopher64:** ErrorEPC has a full `u64::MAX` write mask; ERL=1 ERET selects ErrorEPC and clears ERL.
- **Mupen64Plus pure interpreter:** MTC0 writes `CP0_ERROREPC_REG`, but ERL=1 ERET logs `error in ERET` and sets the stop flag instead of returning through ErrorEPC.
- **n64-systemtest:** `ErrorEPCNoMasking` expects exact 64-bit ErrorEPC write/readback behavior.

The Mupen stop therefore remains a pinned-reference implementation disagreement with the target VR4300 contract. Plaid should preserve it as such and must not infer hardware behavior from that one path.

## Executable exact-pinned ares matrix

`experiments/eret-errorepc-hardware/driver.cpp` runs the real pinned ares CPU interpreter path with both recompilers disabled. It executes guest `DMTC0 $t0,$30`, four hazard NOPs, and the real ERET opcode, then executes a distinct marker at the selected ErrorEPC or EPC target.

CI run `38002411925`, job `114063350741`, at tested code head `4b373ecf09c726e11b7100f223bae12a7029e9a7` passed all six cases. Every case was executed twice and required byte-identical output.

Observed cases:

- `erl_guest_new`: guest changes ErrorEPC from a decoy to `0xffffffffa0000100`; ERET lands there, clears ERL, preserves EXL=1, and executes the ErrorEPC marker `0x1111`.
- `erl_guest_same`: guest rewrites ErrorEPC with the same numeric value; ERET still lands on the ErrorEPC target. The operation remains a distinct provenance event even though visible value equality cannot expose it.
- `erl_capture_control`: no guest write; ERL=1 returns through the existing ErrorEPC value.
- `erl_exl0_guest`: ERL=1 selects ErrorEPC even with EXL=0.
- `erl0_epc_control`: ERL=0 selects EPC, clears EXL, and executes the EPC marker `0x2222`, despite a guest ErrorEPC write.
- `erl0_exl0_control`: ERL=0 selects EPC with EXL already clear.

Executable result SHA-256: `78bb817e06c75e0d055bb40600a081b25a2a92b35fdaa4fd5970835eb9431161`.

Evidence artifact: Actions artifact `11649793589`, ZIP digest `sha256:9ad3f5a94d13e0602cd6930074b77982be351810e7e4a105ea1b48f572d5d6c5`.

## Adversarial provenance model

`experiments/eret-errorepc-hardware/model.py` models EPC and ErrorEPC as `(value, writer_generation, writer_kind)` rather than values alone. Fixed adversaries cover:

- ERL=1 selecting ErrorEPC while preserving EXL;
- ERL=0 selecting EPC and clearing EXL;
- NMI-captured ErrorEPC overwritten by guest DMTC0;
- same-value guest ErrorEPC rewrite advancing the writer generation;
- unknown restore replacing a previously known ErrorEPC;
- explicit rejection of a capture-only target policy.

A deterministic 100,000-history replay produced 300,789 ERET events. The intentionally unsound capture-only policy produced:

- 34,292 wrong targets;
- 43,379 missing targets;
- 572 numeric-equality provenance substitutions.

The replay included 2,456 same-value register writes, all retained as operations. Generation-aware replay kept 157,042 selected targets known and conservatively left 143,747 unresolved after unknown state.

Canonical model report SHA-256: `3312d5fe709b56c690446ba72f5bd1ec5e5e63ac2174ae613e18a594efb6d5b5`.

CI model stdout SHA-256: `76991cd7f7a9bfcf7b2ecf128b9f124bd02d66a18bf8f08092bcf0081c33853e`.

## First-run falsification / harness correction

Actions run `38002342766`, job `114063122837`, failed before the executable matrix because the source guard required the text `let expected = value;` to occur exactly once in the entire n64-systemtest COP0 test file. It legitimately occurs twice in that file. This was a guard-scoping bug, not semantic evidence.

The correction scopes the assertion to the `ErrorEPCNoMasking` struct block and additionally requires the ErrorEPC readback call. No semantic expectation was weakened. The corrected exact-pin guard passed in run `38002411925` before the executable matrix was built and run.

## Closed-world impact

A reachable ERET is a CP0-register-indirect transfer whose selected source depends on the current ERL state:

- ERL=1: current **ErrorEPC generation**;
- ERL=0: current **EPC generation**.

A closure certificate cannot discharge an ERL=1 ERET edge from the most recent NMI/reset capture alone. It must account for the current selected register generation and all in-scope writers, including guest MTC0/DMTC0, reset/NMI capture, save/restore or other state restoration, debugger/out-of-band mutation if admitted by the scope, and same-value rewrites. Unknown current selected-register provenance/value keeps the indirect edge OPEN.

This composes directly with the prior ERET target-provenance result and NMI/ErrorEPC capture research: capture establishes one writer generation, not permanent ownership of the return target.

The current Plaid discovery path already treats ERET as unsupported/fail-closed. No production patch is required merely to stay sound today. This result defines the proof obligation a future bounded ERET closer must satisfy.

## Reproduction

After checking out the exact pins from `refs.lock.toml`:

```bash
python3 -m py_compile experiments/eret-errorepc-hardware/{model.py,run.py,source_guard.py}
python3 experiments/eret-errorepc-hardware/model.py
python3 experiments/eret-errorepc-hardware/source_guard.py \
  --ares .refs/ares \
  --gopher64 .refs/gopher64 \
  --mupen .refs/mupen64plus-core \
  --systemtest .refs/n64-systemtest \
  --out target/eret-errorepc-hardware/source_guard.json
python3 experiments/eret-errorepc-hardware/run.py
```

## Limitations

This result does not prove arbitrary-ROM reachability of any ERET site, implement production CP0 dataflow, prove every reset/restore/debugger writer lifetime, or close a whole ROM by itself. No fresh physical-N64 execution was performed. The Mupen pure-interpreter disagreement is preserved and should remain a regression/reference note rather than being silently normalized.

## Integration recommendation

**ADOPT** the VR4300 selector/provenance rule as a proof invariant:

1. select ErrorEPC when ERL=1 and EPC otherwise;
2. prove the current selected register generation/value, not merely a historical capture or equal numeric value;
3. keep unknown selected-register state OPEN;
4. preserve the exact pinned Mupen ERL stop as an emulator-reference deviation for this architectural question;
5. do not loosen Plaid's current fail-closed ERET behavior until production CP0 generation/value-flow tracking can discharge these obligations.
