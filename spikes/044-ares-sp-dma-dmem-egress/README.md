# Ares SP DMEM -> RDRAM DMA egress provenance

Verdict is determined by `run.py`; this spike is research-only and changes no Plaid production code.

Hypothesis: for exact pinned ares write-DMA, a successful identity-RDRAM sink can inherit DMEM ancestry only from the exact measured source read for that transfer lane. Equal payloads, descriptor proximity or current-memory equality are insufficient.

The fixture executes:

- two equal-valued DMEM Words whose reads both precede the first RDRAM write;
- a byte-identical reload with fresh source writer generations;
- two count/skip rows with poison destination words in the skipped gap;
- modulo-DMEM wrap from `0xff8` to `0x000`;
- a same-value CPU DMEM overwrite before a later DMA;
- a measured same-value foreign DMEM write that must cut known ancestry to UNKNOWN;
- an out-of-bounds RDRAM destination, which consumes DMEM reads but has no successful backing-write witness.

`run.py` builds the unchanged reference fixture, an observer-disabled patched build and two observer-enabled repetitions against ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`. It requires semantic-state neutrality, byte-identical repeated traces, strict source/sink lane replay and six forged-history rejections.

Reproduce from the Plaid repository with the exact ares pin checked out at `.refs/ares`:

```sh
python3 -m py_compile spikes/044-ares-sp-dma-dmem-egress/run.py
python3 spikes/044-ares-sp-dma-dmem-egress/run.py
```

This does not prove hardware DMA atomicity/timing, translated/degraded RDRAM behavior, complete DMEM mutation sensing, RSP register producer dataflow, reset/save/restore continuity, executable lifetimes or whole-ROM closure.
