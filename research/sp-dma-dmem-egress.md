# SP DMEM -> RDRAM DMA egress provenance

Verdict: **VALIDATED** for the controlled exact-pinned ares identity-RDRAM fixture. The cross-reference comparison is deliberately narrower: transfer-lane identity is the portable lesson, while event adjacency, transfer granularity and out-of-range DRAM behavior are **not** platform invariants.

Tested Plaid research head: `b30dc8d6d67fc530b5d89f9b2804e32eb3b080f0`, based on canonical `main` `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.

Reference revisions:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` (executed oracle / instrumented component fixture);
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7` (independent source comparison);
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0` (independent source comparison).

## Question and hypothesis

Can a successful SP write-DMA RDRAM storage effect inherit current DMEM writer ancestry from the exact measured DMEM source read/lane, while rejecting equal-payload, descriptor-proximity and current-memory shortcuts?

For the controlled ares identity-mapped path, the hypothesis was that equal-valued source Words, byte-identical reload generations, count/skip rows, modulo-DMEM wrap, same-value writer replacement and an out-of-range destination would either retain their exact measured source generation or fail closed to UNKNOWN/no successful sink. A latest-equal-payload / nearest-read reducer was expected to misattribute at least one real transfer.

## Instrumentation and fixture

The research-only source shadow observes one monotonic chronology without changing reference object layout:

1. completed CPU-visible DMEM Word storage effects;
2. one explicit measured foreign same-value DMEM effect used to test the UNKNOWN cut;
3. the actual DMEM Word read results inside ares write-DMA, tagged with both DMEM and DRAM lane addresses;
4. only successful RDRAM writes after ares mapping/bounds checks and after backing plus hidden-RAM updates.

No observer callback performs a guest access, clock step, reset, serialization or reference-state mutation. The workflow separately builds an unchanged-reference fixture, an observer-disabled patched fixture, then two observer-enabled repetitions.

The fixture covers:

- two equal `0x11223344` source Words whose reads both precede the first RDRAM sink;
- a byte-identical reload to the same DMEM offsets with fresh source writer generations;
- two count/skip rows with `0x3008/0x300c` poison destinations that must remain untouched;
- 16 bytes beginning at DMEM `0xff8`, wrapping to `0x000`;
- a same-value CPU overwrite of DMEM `0x020` before a later DMA;
- a measured same-value foreign overwrite at DMEM `0x070`, forcing only that Word's ancestry to UNKNOWN;
- an identity-RDRAM destination at `rdram.ram.size`, where ares consumes the DMEM reads but exposes no successful backing-write witness.

## Executed result

GitHub Actions run `37917972710`, job `113778715290`, checked out the exact ares pin, passed Python syntax, compiled both component binaries and executed the complete experiment. The measured result was:

- 52 ordered events;
- unchanged-reference == observer-disabled == observer-enabled machine state (`neutrality: true`);
- byte-identical repeated enabled trace (`repeat_deterministic: true`);
- the real equal-payload case falsified latest-payload matching: sink sequence 5 belongs to DMEM `0x000`, while the nearest equal-valued read was DMEM `0x004`;
- all six forged histories were rejected: `equal_payload_wrong_lane`, `missing_source_read`, `skip_poison_sink`, `same_value_overwrite_removed`, `foreign_same_value_mutation_removed`, `duplicate_ordinal`;
- result JSON SHA-256: `d55251b2ef9a591c4f2aa484cb93cd89584c7e87d8231347723f3968176ceb0b`;
- retained Actions artifact ID `11611276902`; uploaded ZIP SHA-256 `397121cebb62024edc8ae161b6042f78c44d3be1f3a6fb9375c321a4299c54bf`.

The controlled ares result therefore supports this causal rule: a successful egress sink may inherit DMEM lineage from the current writer-generation snapshot at its **explicit measured transfer lane/source read**, not from payload equality, nearest-event proximity, a descriptor alone or later/current DMEM contents. A measured intervening same-value mutation changes lineage even when bytes do not change. A missing/foreign writer must remain UNKNOWN.

## Independent-reference comparison and counterexamples to over-generalization

Pinned ares reads two DMEM Words before issuing their two RDRAM Word writes. That exact ordering is what makes the equal-payload nearest-read adversary especially sharp, but it is not a hardware invariant.

Pinned Gopher64 `src/device/rsp_interface.rs::do_dma` independently models SP-to-RDRAM egress as 4-byte transfer units, but each RSP-memory read is immediately followed by its RDRAM copy before the next source read. It preserves the same address progression/count/skip idea but not ares's two-reads-then-two-writes adjacency. Its out-of-range destination uses `get_mut(...).unwrap_or(&mut [0; 4])`, so the source read can occur without mutating RDRAM.

Pinned Mupen64Plus Core `src/device/rcp/rsp/rsp_core.c::do_sp_dma` is different again: the SP-to-RDRAM path copies byte-by-byte and indexes RDRAM with `(dramaddr ^ S8) & 0x7fffff`. Thus an address beyond the nominal 8 MiB range wraps through that mask instead of matching ares/Gopher's no-backing-write behavior.

These disagreements are useful negative evidence. Plaid must not encode ares's Word grouping, paired-read chronology or OOB behavior as N64-wide truth. If a provenance representation needs a common granularity, bytes plus explicit transfer identity are the conservative choice. Out-of-range SP DMA requires separate reference/hardware resolution before certification.

## Reproduction

With the Plaid research branch checked out and exact ares revision present at `.refs/ares`:

```sh
python3 -m py_compile spikes/044-ares-sp-dma-dmem-egress/run.py
python3 spikes/044-ares-sp-dma-dmem-egress/run.py
```

The branch-only workflow `.github/workflows/research-sp-dma-dmem-egress.yml` performs the same checkout/build/run and retains `target/ares-sp-dma-dmem-egress/results.json`.

## Limits / explicitly not proved

This does not establish hardware DMA atomicity or timing, translated/degraded RDRAM behavior, the correct hardware behavior for out-of-range DRAM addresses, complete DMEM mutation sensing, RSP register/data producer lineage, queued-DMA contention, reset/save/restore continuity, executable lifetime closure or whole-ROM closure. The explicit foreign mutation is a controlled effect-boundary witness, not a production-complete foreign-sink sensor. No runtime MIPS dependency or production Plaid architecture is changed by this spike.
