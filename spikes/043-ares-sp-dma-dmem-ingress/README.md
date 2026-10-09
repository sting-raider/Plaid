# Exact SP-DMA DMEM ingress provenance

This spike tests a narrow composition gap left by the validated IMEM provenance work: pinned ares implements an RDRAM -> **DMEM** 8-byte SP-DMA fragment as two successful 32-bit RDRAM reads followed by two 32-bit DMEM writes, rather than the IMEM path's single `Dual` read/write.

That event shape matters. For the first DMEM sink the immediately preceding successful read is the *other* word. The fixture deliberately makes both words equal, so a reducer that joins by adjacency or latest equal payload assigns the wrong RDRAM origin even though final bytes look perfect.

The observer is generated outside the pinned checkout and records only already-completed facts:

- successful ordinary RDRAM reads requested by `RBusDevice::SP_DMA`;
- each completed DMEM `write<Word>` together with the exact `dma.current.dramAddress + lane` used by that source statement;
- direct CPU-visible DMEM Word writes after completion.

The executable cases cover:

- one equal-valued 8-byte fragment, proving the `read0, read4, sink0, sink4` chronology;
- a byte-identical reload from a different RDRAM source, which must mint fresh writer generations;
- count/skip rows where poison source words must never acquire lineage;
- modulo-DMEM wrap from `0xff8` through `0x000`;
- an out-of-range source that writes zero to DMEM but has no successful backing-read witness, so origin remains UNKNOWN;
- a same-value direct CPU DMEM overwrite that must replace only its concrete word lineage;
- forged histories for equal-payload wrong-source joins, missing reads, skip-poison joins, forged CPU identity and broken ordinals.

Reproduce from the repository root with the exact pinned ares checkout at `.refs/ares`:

```sh
python3 spikes/043-ares-sp-dma-dmem-ingress/run.py
```

This result is about concrete DMEM byte-writer provenance in the controlled pinned-ares interpreter/component scope. It does not by itself prove RSP consumer dataflow, reverse DMA egress, CPU SP refetch provenance, whole-game scheduler timing, hardware FIFO overflow policy, or closed-world executable discovery.
