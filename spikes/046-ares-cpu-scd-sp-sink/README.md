# Spike 046: exact ares CPU SCD -> SP sink

Status: IN PROGRESS

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Reference pins:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Falsifiable hypothesis

If interpreted VR4300 `SCD` actually reaches CPU-visible SP DMEM/IMEM in exact pinned ares, the RCP `Dual` adapter completes exactly one 32-bit SP `writeWord` using the upper source Word. `llbit=0` and misaligned SCD must execute no completed SP sink. A successful same-value SCD must remain a fresh storage generation even when the bytes do not change.

This is deliberately phrased around the **completed sink**, not around nominal opcode width or register equality. The result is reference-scoped: pinned Gopher64 performs two `data_write` calls in `SCD`, while pinned n64-systemtest has hardware-facing tests for ordinary SCD and SP `SD` but no direct SCD-to-SP fixture.

## Important exact-ares control

The first executable attempts exposed a separate ares behavior that the final fixture keeps as an explicit control: a non-RDRAM `Dual` read is intercepted by `Bus::read<Dual>` before RSP dispatch, calls `freezeDualRead`, returns zero, and sets `cpu.scc.sysadFrozen`. Therefore a direct SP `LLD` cannot be used to drive a following SCD in this exact reference. The fixture records this for both DMEM and IMEM.

For the SCD sink matrix, a real decoded `LLD` establishes `llbit` from uncached RDRAM and loads the known 64-bit source; the following decoded SCD targets SP memory. This is a reference experiment, not a claim that such a mismatched LL/SCD pair is architecturally valid: exact pinned ares' `SCD` implementation gates on `llbit` and does not compare the linked physical address.

## Cases

For DMEM and IMEM independently the corrected fixture runs:

1. direct SP `LLD` freeze control;
2. SCD with `llbit=0`;
3. real RDRAM `LLD` followed by misaligned SP SCD;
4. real RDRAM `LLD`, decoded `DADDIU` carrying across low `0xffffffff`, then aligned SP SCD;
5. real RDRAM `LLD` followed by aligned same-value SP SCD.

The initial 64-bit payload is `0x11223344ffffffff`. The transformed source is `0x1122334500000000`. If ares forwards only the high Word, the changed case must finish as `0x11223345ffffffff`, proving that the source value and the decoded 64-bit opcode do not by themselves describe the completed SP storage effect.

An equal-value out-of-context `CPU::write<Dual>` decoy tests attribution. The verifier also forges histories to ensure it rejects missing same-value sinks, fabricated failed sinks, erased SCD/reservation context, a forged lower-Word sink value, and suppression of the SP-LLD freeze control.

## Reproduction

```bash
python3 -m py_compile spikes/046-ares-cpu-scd-sp-sink/*.py
python3 spikes/046-ares-cpu-scd-sp-sink/model.py
python3 spikes/046-ares-cpu-scd-sp-sink/run.py
```

`run.py` requires the exact pinned repositories at `.refs/ares`, `.refs/gopher64`, and `.refs/n64-systemtest`; the branch workflow checks them out and builds the unmodified ares core using the existing `spikes/003-ares-oracle` builder. It compares an observer-free baseline against the SP-sink observer build, persists observations before hypothesis verification, and requires byte-identical repeated instrumented output.
