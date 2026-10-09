# Spike 046: exact ares CPU SCD -> SP sink

Status: **VALIDATED** for exact pinned ares behavior.

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Passing fixture commit: `d70a15e840cfb89c85f34a550697844a1926a33a`

Reference pins:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Falsifiable hypothesis

If interpreted VR4300 `SCD` actually reaches CPU-visible SP DMEM/IMEM in exact pinned ares, the RCP `Dual` adapter completes exactly one 32-bit SP `writeWord` using the upper source Word. `llbit=0` and misaligned SCD must execute no completed SP sink. A successful same-value SCD must remain a fresh storage generation even when the bytes do not change.

This is deliberately phrased around the **completed sink**, not around nominal opcode width or register equality. The result is reference-scoped: pinned Gopher64 performs two `data_write` calls in `SCD`, while pinned n64-systemtest has hardware-facing tests for ordinary RDRAM SCD and SP `SD` but no direct SCD-to-SP fixture.

## Important exact-ares control discovered while debugging

A non-RDRAM `Dual` read is intercepted by `Bus::read<Dual>` before RSP dispatch, calls `freezeDualRead`, returns zero, and sets `cpu.scc.sysadFrozen`. Therefore a direct SP `LLD` cannot drive a following SCD in this exact reference: once frozen, `CPU::instruction()` advances time but does not execute another guest instruction.

The final SCD sink matrix consequently uses a real decoded uncached RDRAM `LLD` solely to establish `llbit` and load the known 64-bit source; the following decoded `SCD` targets SP memory. This is a reference experiment, not a claim that a mismatched LL/SCD address pair is architecturally valid. Exact pinned ares' `SCD` implementation gates on `llbit` and does not compare the linked physical address.

The failed SP-LLD attempt is retained in `research/cpu-scd-sp-sink.md` as a negative result because it demonstrates both the non-RDRAM Dual-read freeze and the danger of reasoning from intended later instructions after a bus-side CPU freeze.

## Cases

For DMEM and IMEM independently the passing fixture runs:

1. aligned SCD with `llbit=0`;
2. real RDRAM `LLD` followed by misaligned SP SCD;
3. real RDRAM `LLD`, decoded `DADDIU` carrying across low `0xffffffff`, then aligned SP SCD;
4. real RDRAM `LLD` followed by aligned same-value SP SCD.

The initial 64-bit payload is `0x11223344ffffffff`. The transformed source is `0x1122334500000000`. The changed case finishes SP storage as `0x11223345ffffffff`: the upper Word reaches the sink, while the lower source Word `0x00000000` does not.

An equal-value out-of-context `CPU::write<Dual>` decoy tests attribution. The verifier also forges histories to ensure it rejects a missing same-value sink, a fabricated failed-store sink, theft of the equal-value decoy, erased decoded-SCD context, erased reservation context, and a forged lower-Word sink.

## Passing observations

GitHub Actions run `37921332005` passed at fixture commit `d70a15e840cfb89c85f34a550697844a1926a33a`:

- four successful decoded SCDs -> four completed SP Word sinks;
- zero successful second-word sinks;
- two transformed successes truncate the low half of the 64-bit source;
- two same-value successes still emit completed writer generations;
- two `llbit=0` failures -> no sink;
- two misaligned AddressStore faults -> no sink;
- one out-of-context equal-value decoy kept separate;
- six forged histories rejected;
- observer-free baseline facts equal instrumented facts;
- repeated instrumented traces are byte-identical.

Hashes:

- model: `2d4ec0edb50baaae1b8df361c5cf97b3f42bd73681ac58c4865926e04c727442`
- trace: `fcc09349905df6065728333dc26427e3ca9fc574f811fb3e962120c9e70db963`
- verified result: `5bd6bdd7752bd752daa53b30d90625f24f71c642430f9f9ceff16d26b7ff71eb`

## Reproduction

```bash
python3 -m py_compile spikes/046-ares-cpu-scd-sp-sink/*.py
python3 spikes/046-ares-cpu-scd-sp-sink/model.py
python3 spikes/046-ares-cpu-scd-sp-sink/run.py
```

`run.py` requires the exact pinned repositories at `.refs/ares`, `.refs/gopher64`, and `.refs/n64-systemtest`; the branch workflow checks them out and builds the unmodified ares core using the existing `spikes/003-ares-oracle` builder. It compares an observer-free baseline against the SP-sink observer build, persists observations before hypothesis verification, and requires byte-identical repeated instrumented output.
