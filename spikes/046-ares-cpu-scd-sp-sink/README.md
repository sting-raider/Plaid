# Spike 046: exact ares CPU SCD -> SP sink

Status: **VALIDATED** for exact pinned ares behavior.

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Strict passing fixture commit: `0b3732691fc5f40d2999553fc142cfb941dd3d54`

Reference pins:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Falsifiable hypothesis

If interpreted VR4300 `SCD` actually reaches CPU-visible SP DMEM/IMEM in exact pinned ares, the RCP `Dual` adapter completes exactly one 32-bit SP `writeWord` using the upper source Word. `llbit=0` and misaligned SCD must execute no completed SP sink. A successful same-value SCD must remain a fresh storage generation even when the bytes do not change.

This is deliberately phrased around the **completed sink**, not around nominal opcode width or register equality. The result is reference-scoped: pinned Gopher64 performs two `data_write` calls in `SCD`, while pinned n64-systemtest has hardware-facing tests for ordinary RDRAM SCD and SP `SD` but no direct SCD-to-SP fixture.

## Important exact-ares control

A non-RDRAM `Dual` read is intercepted by `Bus::read<Dual>` before RSP dispatch, calls `freezeDualRead`, returns zero, and sets `cpu.scc.sysadFrozen`. The strict fixture therefore records one direct decoded `LLD` control for each SP bank. Both controls produce `loaded=0`, `llbit_after=true`, and `sysad_frozen=true`. Once frozen, `CPU::instruction()` advances time but does not execute another guest instruction.

The SCD sink matrix consequently uses a real decoded uncached RDRAM `LLD` solely to establish `llbit` and load the known 64-bit source; the following decoded `SCD` targets SP memory. This is a reference experiment, not a claim that a mismatched LL/SCD address pair is architecturally valid. Exact pinned ares' `SCD` implementation gates on `llbit` and does not compare the linked physical address.

The direct SP-LLD freeze is preserved as a deterministic negative control because it demonstrates both the non-RDRAM Dual-read restriction and the danger of reasoning from intended later instructions after a bus-side CPU freeze.

## Cases

For DMEM and IMEM independently the strict fixture runs:

1. direct SP `LLD` freeze control;
2. aligned SCD with `llbit=0`;
3. real RDRAM `LLD` followed by misaligned SP SCD;
4. real RDRAM `LLD`, decoded `DADDIU` carrying across low `0xffffffff`, then aligned SP SCD;
5. real RDRAM `LLD` followed by aligned same-value SP SCD.

The initial 64-bit payload is `0x11223344ffffffff`. The transformed source is `0x1122334500000000`. The changed case finishes SP storage as `0x11223345ffffffff`: the upper Word reaches the sink, while the lower source Word `0x00000000` does not.

An equal-value out-of-context `CPU::write<Dual>` decoy tests attribution. The verifier forges histories to ensure it rejects a missing same-value sink, a fabricated failed-store sink, theft of the equal-value decoy, erased decoded-SCD context, erased reservation context, a forged lower-Word sink, and suppression of the SP-LLD freeze control.

## Strict passing observations

GitHub Actions run `37921610783`, job `113790612930`, passed at fixture commit `0b3732691fc5f40d2999553fc142cfb941dd3d54`:

- two direct SP `LLD` controls -> zero loaded value, `llbit=true`, `sysadFrozen=true`;
- four successful decoded SCDs -> four completed SP Word sinks;
- zero successful second-word sinks;
- two transformed successes truncate the low half of the 64-bit source;
- two same-value successes still emit completed writer generations;
- two `llbit=0` failures -> no sink;
- two misaligned AddressStore faults -> no sink;
- one out-of-context equal-value decoy kept separate;
- seven forged histories rejected;
- observer-free baseline facts and freeze controls equal instrumented facts and controls;
- repeated instrumented traces are byte-identical.

Reference comparison retained by the runner:

- ares RCP `Dual` write -> one `writeWord`;
- Gopher64 `SCD` -> two `data_write` calls and clears `llbit`;
- n64-systemtest tests upper-word-only plain `SD` to SPMEM and full 64-bit `SCD` to RDRAM, but has no direct SCD-to-SPMEM oracle.

Hashes from the strict run:

- model: `2d4ec0edb50baaae1b8df361c5cf97b3f42bd73681ac58c4865926e04c727442`
- observed record: `96db3107d5f6e836d8f4c0758c45665a6dfb81fa9c3c4a4550c11e3d60501da0`
- trace: `36abff3d44d1a4339df0cb96aec3f98adeaffa893cdd064dbf0abe37f0378bdb`
- verified result: `201b70c18199300f5cc2a7cacd8ad8229ad0575ed4ff00ec90bec4c48314f729`
- uploaded artifact ZIP: `59476e735d1e3fb3138507260561135d225e048e27aac39841602afe4af26e3f`

## Reproduction

```bash
python3 -m py_compile spikes/046-ares-cpu-scd-sp-sink/*.py
python3 spikes/046-ares-cpu-scd-sp-sink/model.py
python3 spikes/046-ares-cpu-scd-sp-sink/run.py
```

`run.py` requires the exact pinned repositories at `.refs/ares`, `.refs/gopher64`, and `.refs/n64-systemtest`; the branch workflow checks them out and builds the unmodified ares core using the existing `spikes/003-ares-oracle` builder. It compares an observer-free baseline against the SP-sink observer build, persists observations before hypothesis verification, checks exact source structure, rejects forged histories, and requires byte-identical repeated instrumented output.

For implications and limitations, see `research/cpu-scd-sp-sink.md`.
