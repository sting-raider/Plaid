# Spike 044: CPU SDL/SDR into SP memory

Question: when decoded VR4300 `SDL`/`SDR` (plus aligned `SD` control) target CPU-visible RSP DMEM or IMEM, what completed storage effects does exact pinned ares actually produce?

This is intentionally separate from the earlier uncached-RDRAM SDL/SDR experiment. The SP window sits behind a device adapter whose concrete sink width need not equal the architectural store width.

## Exact scope

- Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- CPU and RSP recompilers disabled
- real encoded VR4300 opcodes executed through `cpu.instruction()`
- direct uncached KSEG1 SP DMEM and IMEM targets
- both big- and forced little-endian CPU contexts
- all eight offsets for `SDL` and `SDR`
- aligned `SD` controls
- endian-correct `SDL`+`SDR` pairs at all eight starting offsets

The driver is unmodified upstream ares code linked with a synthetic headless fixture. `model.py` independently transcribes the exact pinned CPU decomposition, reverse-endian physical lane mapping, RCP adapter normalization, and final `RSP::writeWord` sink.

## Run

With exact ares checked out at `.refs/ares`:

```bash
python3 -m py_compile spikes/044-ares-cpu-sp-sdl-sdr/*.py
python3 spikes/044-ares-cpu-sp-sdl-sdr/model.py
python3 spikes/044-ares-cpu-sp-sdl-sdr/run.py
```

`run.py` executes 100 cases and runs every case twice, requiring byte-identical output. It also source-hash guards all exact implementation files that make the causal sink model valid.

## Important guard

At the pinned ares revision, `Memory::RCP::write<Dual>` forwards only one `writeWord(address, data >> 32, ...)`. The fixture treats that as a falsifiable reference behavior, not as N64 hardware truth. If this source shape changes, the experiment must fail closed and be re-established.
