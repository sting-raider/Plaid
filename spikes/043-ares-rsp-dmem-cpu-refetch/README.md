# RSP DMEM -> CPU SP refetch composition

Result: **VALIDATED** for the controlled pinned-ares interpreter scope described below.

Bounded question: can measured RSP DMEM storage effects be carried into a later actual CPU instruction fetch from the SP DMEM aperture without inferring origin from matching values or PCs, while preserving same-value generations, partial stores, vector stores, CPU overwrite boundaries, and unknown/out-of-context mutations?

The exact pinned ares fixture composes the already validated SP word callback shadow (`spikes/039`) with the scoped RSP instruction/DMEM sink shadow (`spikes/042`) under one monotonic event ordinal. The verifier replays concrete bytes and assigns writer identity only at measured completed storage effects.

## Fixture

The deterministic phases are:

1. CPU fetches an explicit initial DMEM instruction word.
2. RSP `SW` replaces the fetched word.
3. CPU refetches that word.
4. RSP repeats the same-value `SW`.
5. CPU refetches; every byte has a new RSP writer generation despite identical payload.
6. CPU `SW` writes the same word through the SP aperture.
7. CPU refetches; all four byte origins are now the completed CPU SP write.
8. RSP writes an equal-valued `SW` to the neighboring word.
9. CPU refetches the original word; its CPU origins are unchanged.
10. RSP scalar `SB` changes byte 3 only.
11. CPU refetches a word split across the CPU writer and the scalar RSP writer.
12. RSP vector `SBV` changes byte 2 only.
13. CPU refetches a word split across CPU, vector-RSP, and scalar-RSP writers.
14. An out-of-instruction-context same-value DMEM byte write touches byte 3.
15. CPU refetches the unchanged payload, but byte 3 lineage is now explicitly unknown rather than falsely retaining the old RSP producer.
16. A decoded same-value RSP `SB` writes byte 3.
17. CPU refetches; byte 3 now has a new known RSP generation.

A useful falsification fell out of the exact run: in this pinned ares revision, RSP `SW` is implemented through `writeUnaligned<Word>`, so the low-level storage sensor observes four ordered primitive byte writes, not one atomic Word sink. The verifier therefore carries four distinct per-byte generations for each `SW`. Treating decoded `SW` as one storage effect would have been the wrong abstraction.

A CPU SP write also reaches the low-level DMEM callback before the higher-level completed SP-word write callback. Such a low-level event is classified as `foreign_sink` unless a decoded RSP instruction context is active. The later matched completed CPU `sp_write` supersedes those four bytes with CPU writer identity. An unmatched/out-of-context sink stays unknown.

## Verification

`run.py` checks:

- exact ares pin `9408cb43d4948fc3ea6e152a307a34348df3fe04` and a clean reference checkout;
- original baseline, sensor-disabled, sensor-enabled, and repeated sensor-enabled final-state equality for the explicit fixture state;
- sensor machine-digest equality between disabled/enabled/repeated sensor builds;
- byte-exact replay of every CPU fetch backing read;
- 15 primitive scoped RSP sinks, including four byte effects for each RSP `SW`, scalar `SB`, and vector `SBV`;
- CPU overwrite replacement of all four byte origins;
- same-value mutations advancing writer generation even when bytes do not change;
- fail-closed unknown lineage for an out-of-context same-value byte sink;
- ten forged histories rejected by the generation-aware verifier.

The deliberately weaker value-only check still accepts three value-preserving provenance forgeries:

- deletion of one same-value RSP byte generation;
- moving an equal-valued neighboring RSP sink onto a fetched byte;
- moving the same-value unknown/foreign sink away from the fetched byte.

That is the point: equal payload is not causal provenance.

Exact passing GitHub Actions execution:

- Plaid research commit: `86b51ec21707a28dff4a630946569bbeecb0b7ec`
- run: `37915637117`
- job: `113771004974`
- result SHA-256: `3bdbf149b3b382fb9fb38c8381a0fee32d4e1045f804f12bebb2ba1066091957`
- uploaded artifact ID: `11609228305`

Reproduce from the repository root with the exact ares pin checked out at `.refs/ares`:

```sh
python3 spikes/043-ares-rsp-dmem-cpu-refetch/run.py
```

## Scope

This is controlled reference evidence. It does **not** prove a complete platform writer census, RSP hardware-level atomicity, producer dataflow behind an RSP register value, DMA provenance, CPU cached-copy/decompression provenance, executable lifetime, all RSP store encodings/alignment cases, interrupt/TLB/cache completeness, or whole-ROM closed-world reachability. The safe integration rule is narrower: compose ordered measured storage effects at byte granularity, preserve same-value generations, let a successfully identified later writer replace only the bytes it actually writes, and degrade unmatched/foreign effects to unknown rather than guessing an origin.
