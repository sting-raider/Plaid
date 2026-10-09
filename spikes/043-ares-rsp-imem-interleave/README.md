# Spike 043: RSP IMEM DMA/direct-write interleaving

Question: may one multi-row RDRAM -> IMEM SP-DMA be treated as an atomic installed-microcode generation when another CPU-originated IMEM write occurs between count rows?

Hypothesis: no. Pinned ares executes one count row per `RSP::dmaTransferStep()`, reschedules, and returns. A direct `RSP::writeWord` can therefore mutate IMEM between rows. The current DMA descriptor is still useful as a transfer identity, but final resident provenance must remain per-byte/latest-writer sensitive.

The exact-reference fixture covers:

- CPU overwrite of an already completed row, which survives the DMA completion;
- CPU overwrite of a future row, which is superseded by that later DMA row;
- a same-value direct write whose execution cannot be recovered from content comparison;
- IMEM wrap (`0xff8 -> 0x000`) with one surviving and one superseded direct write;
- a non-overlapping direct write control.

`model.py` also fuzzes 5,000 deterministic histories and compares a correct per-byte latest-writer replay with a deliberately unsound rule that, at transfer completion, assigns every span ever touched by the transfer back to its DMA row. The model is intended to falsify transfer-level residency shortcuts, not to model N64 timing.

Run against the exact ares pin from `refs.lock.toml`:

```bash
python3 spikes/043-ares-rsp-imem-interleave/model.py
python3 spikes/043-ares-rsp-imem-interleave/source_guard.py .refs/ares
python3 spikes/043-ares-rsp-imem-interleave/run.py
```

No ROM or copyrighted asset is required. The ares executable fixture uses the existing headless component builder and no upstream instrumentation.
