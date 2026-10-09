# Exact-pin RSP IMEM reverse-DMA egress fixture

This standalone research spike tests one bounded question: whether executable
RSP IMEM writer generations can be carried through a completed SP write-DMA to
RDRAM without selecting provenance by matching payload values.

It intentionally includes:

- a successful same-value CPU-visible IMEM Word rewrite;
- changed IMEM Word rewrites;
- a newer 8-byte equal-payload IMEM decoy at a different offset;
- a two-row `count=1`, `skip=8` reverse DMA;
- a 16-byte source wrap from IMEM `0xff8` to IMEM `0x000`;
- deliberately different DMEM `0x000..0x007` bytes at that wrap boundary;
- baseline, sensor-disabled, sensor-enabled and repeated-enabled state checks;
- fail-closed replay mutations for source offset, source bank, chronology,
  same-value writer deletion, payload corruption and skipped-RDRAM placement.

The exact ares source contract is independently guarded against pinned Gopher64.
Both references carry the SP bank separately from the 12-bit offset that wraps.
That is reference evidence, not a hardware invariant.

Reproduce after fetching the exact pins in `refs.lock.toml` into `.refs/ares` and
`.refs/gopher64`:

```bash
python3 spikes/047-ares-rsp-imem-dma-egress/source_guard.py
python3 spikes/047-ares-rsp-imem-dma-egress/run.py
```

Generated reference shadows, binaries and raw evidence remain under `target/`
and are not production dependencies.
