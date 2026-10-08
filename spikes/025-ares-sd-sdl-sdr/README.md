# Spike 025: ares SD/SDL/SDR executable-mutation matrix

This spike asks a narrow question needed by executable provenance: can VR4300 `SD`, `SDL`, or `SDR` mutate executable RDRAM bytes in ways missed by Plaid's current successful-`SW` sensor, and what exact byte effect must a future mutation witness preserve?

It runs guest instructions through the interpreter of the exact ares revision pinned by `refs.lock.toml` (`9408cb43d4948fc3ea6e152a307a34348df3fe04`). The fixture uses uncached direct RDRAM for successful stores so the post-state is actual RDRAM backing, not merely a dirty D-cache line. It also exercises TLB-store-miss failure cases. Both big- and little-endian CPU contexts are tested; the latter deliberately forces the pinned core's context endianness so lane reversal is covered without claiming that an N64 title normally changes the hardware's configured base endianness.

The matrix covers:

- `SDL` offsets 0..7 in both endian contexts;
- `SDR` offsets 0..7 in both endian contexts;
- `SD` offsets 0..7, proving aligned success and misalignment failure;
- endian-correct unaligned pairs at all eight starting offsets: big-endian uses `SDL addr` + `SDR addr+7`, while little-endian uses `SDL addr+7` + `SDR addr`;
- unmapped-TLB failure for every `SDL`/`SDR` offset and aligned `SD` in both endian contexts;
- two byte-identical repetitions of every case.

The harness snapshots both guest-visible bytes and physical RDRAM bytes. Expected results are derived independently from byte semantics rather than by copying ares' switch tables.

## Run

```bash
python scripts/fetch_refs.py
python spikes/025-ares-sd-sdl-sdr/run.py
```

The run writes `target/ares-sd-sdl-sdr/results.json` and prints its SHA-256. Generated binaries/results stay out of git.

## Reference cross-check

Pinned Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0` is used as an independent source oracle for the normal big-endian N64 path. Its `mips_instructions.def` expresses `SDL`/`SDR` as masks passed to `r4300_write_aligned_dword`, while `r4300_core.c` emits two masked 32-bit memory writes. This differs structurally from ares' subwrite decomposition but agrees on the big-endian architectural byte masks. Reverse-endian lane behavior is validated against pinned ares source plus execution, not claimed as a Mupen cross-check.
