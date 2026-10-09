# RSP IMEM installation lifetime composition

This bounded spike composes the already-validated SP-DMA request lifecycle with completed RSP IMEM storage sinks.

It builds exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, with CPU/RSP recompilers disabled, and observes only four completed lifecycle facts: promoted current request, completed DMA IMEM write, completed CPU IMEM Word write, and request completion.

Cases deliberately attack value/range shortcuts:

1. one count/skip request with a same-value CPU IMEM Word write between its two DMA rows;
2. two distinct promoted requests reloading byte-identical payloads to the same IMEM addresses;
3. one 16-byte request wrapping from IMEM `0xff8` to `0x000`;
4. current-to-pending handoff with completion and promotion inside one `dmaTransferStep()` and no externally sampled BUSY-low boundary.

`verify.py` replays the completed sinks into per-byte writer generations and rejects wrong active-request attribution, reused request generations and missing completion.

Reproduce:

```bash
python3 spikes/043-ares-rsp-imem-install-lifetime-gpt56sol/run.py
```

Generated evidence is written under `target/ares-rsp-imem-install-lifetime/` and is intentionally not committed.
