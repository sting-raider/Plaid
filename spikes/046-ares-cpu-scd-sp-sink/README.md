# Spike 046: exact ares CPU SCD -> SP sink

Status: IN PROGRESS

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Reference pins:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

## Falsifiable hypothesis

A successful interpreted VR4300 `SCD` to CPU-visible SP DMEM/IMEM in exact pinned ares reaches the RCP `Dual` adapter and completes exactly one 32-bit SP `writeWord` using the upper source Word. Failed-reservation and misaligned SCD execute no SP sink. A successful same-value SCD remains a fresh storage generation even when the bytes do not change.

The result is reference-scoped. Pinned Gopher64 source is checked separately because its `SCD` path performs two `data_write` calls, so an ares result must not be promoted into N64 hardware truth.

## Cases

For DMEM and IMEM independently the fixture runs:

1. SCD with `llbit=0`;
2. real `LLD` followed by misaligned SCD;
3. real `LLD`, decoded `DADDIU` carrying across the low `0xffffffff`, then aligned SCD;
4. real `LLD` followed by aligned same-value SCD.

The initial 64-bit SP payload is `0x11223344ffffffff`. The transformed source is `0x1122334500000000`. If ares forwards only the high Word, the changed case must finish as `0x11223345ffffffff`, proving that source-register equality and the opcode width do not describe the actual storage sink.

An equal-value out-of-context `CPU::write<Dual>` decoy tests attribution, and the verifier mutates histories to ensure it rejects missing same-value sinks, fabricated failed sinks, erased SCD/reservation context, and a forged lower-Word sink value.

## Reproduction

```bash
python3 -m py_compile spikes/046-ares-cpu-scd-sp-sink/*.py
python3 spikes/046-ares-cpu-scd-sp-sink/run.py
```

`run.py` requires the exact pinned repositories at `.refs/ares` and `.refs/gopher64`; the branch workflow checks them out and builds the unmodified ares core using the existing `spikes/003-ares-oracle` builder. It compares an observer-free baseline against the SP-sink observer build and requires byte-identical repeated instrumented output.
