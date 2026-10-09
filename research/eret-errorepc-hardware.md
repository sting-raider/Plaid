# VR4300 ERL / ErrorEPC ERET contract

Status: **IN PROGRESS**

Worker: `gpt56sol-eret-errorepc-hardware-20261010`

Canonical base inspected: `211176e7a489fecf8331d02915ee982cd279cb62`

Exact pins from `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Question

The prior `research/eret-target-provenance-gpt56sol` result proved that ordinary ERL=0 ERET cannot be derived only from exception-captured EPC because guest MTC0 may replace EPC. It deliberately left ERL=1 open: exact pinned ares and Gopher64 select ErrorEPC, while pinned Mupen's pure interpreter logs `error in ERET` and stops.

This worker asks which behavior is the VR4300 contract and what whole-ROM control-flow proof follows.

## Hardware evidence

NEC VR4300 User's Manual `U10504EJ7V0UM00` resolves the architectural selector directly:

- Chapter 16, ERET instruction (p. 434 in the 7th-edition PDF): when Status.ERL is 1, ERET loads PC from ErrorEPC and clears ERL; otherwise it loads PC from EPC and clears EXL. ERET also clears LLbit.
- Section 6.3.12, Error Exception Program Counter register (p. 179): ErrorEPC is explicitly a read/write register holding the resume virtual address for reset/NMI error-level handling.
- The VR4300 CP0 hazard table independently lists ERET as consuming `EPC or ErrorEPC` and Status.

This is target-hardware documentation, not emulator-majority inference.

## Independent hardware-facing test evidence

Exact pinned `n64-systemtest` contains `ErrorEPCNoMasking` in `src/tests/cop0/mod.rs`. It writes several 64-bit values with `set_errorepc`, reads ErrorEPC back, and expects the exact value. This independently supports software programmability/full-width storage of ErrorEPC. The test corpus is hardware-facing; this worker has not yet claimed a fresh physical-console execution receipt.

## Exact reference disagreement

Read-only exact-pin inspection currently confirms:

- ares: CP0 register 30 writes `scc.epcError`; ERET with `status.errorLevel` calls `pipeline.setPc(scc.epcError)` and clears errorLevel.
- Gopher64: ErrorEPC has a full `u64::MAX` write mask; ERET with ERL selects `COP0_ERROREPC_REG` and clears ERL.
- Mupen64Plus pure interpreter: MTC0 can write `CP0_ERROREPC_REG`, but ERL=1 ERET logs `error in ERET` and sets the core stop flag instead of returning through ErrorEPC.

Therefore the Mupen path disagrees with both the target manual and the other two pinned references. The working interpretation is that this Mupen path is an implementation limitation for the declared VR4300 semantics, but executable/source-guard receipts are still being produced before closeout.

## Adversarial provenance model

`experiments/eret-errorepc-hardware/model.py` models EPC and ErrorEPC as `(value, writer_generation, writer_kind)` rather than values alone. Fixed adversaries cover:

- ERL=1 selecting ErrorEPC while preserving EXL;
- ERL=0 selecting EPC and clearing EXL;
- NMI-captured ErrorEPC overwritten by guest DMTC0;
- same-value guest ErrorEPC rewrite advancing the writer generation;
- unknown restore replacing a previously known ErrorEPC;
- explicit rejection of a capture-only target policy.

The deterministic 100,000-history local replay produced 300,789 ERET events. The intentionally unsound capture-only policy had 34,292 wrong targets, 43,379 missing targets and 572 numeric-equality provenance substitutions. The replay included 2,456 same-value register writes, all retained as operations. Canonical model report SHA-256: `3312d5fe709b56c690446ba72f5bd1ec5e5e63ac2174ae613e18a594efb6d5b5`.

## Closed-world consequence under test

If the executable fixture/source guards confirm the exact-pin contract, a reachable ERL=1 ERET must be treated as a CP0-register-indirect transfer from the **current ErrorEPC generation**, not as a return to the most recent NMI/reset capture. A sound certificate must account for all relevant ErrorEPC writers, including guest MTC0/DMTC0, reset/NMI capture, restore/debugger/out-of-band state, and same-value rewrites. Unknown current generation keeps the edge OPEN.

The existing Plaid discovery behavior already treats ERET as unsupported/fail-closed; this worker is not proposing an automatic closure shortcut.

## Remaining work

- execute the exact-pinned ares guest DMTC0 + hazard + ERET matrix twice deterministically;
- run exact source guards over all four pins;
- preserve the Mupen disagreement explicitly;
- checkpoint hashes/CI receipt and convert this note to final result status.
