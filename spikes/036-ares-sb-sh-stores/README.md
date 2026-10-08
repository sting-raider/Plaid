# Spike 036: pinned-ares SB/SH executable mutation

Status: in-progress research spike. Branch-only; no Plaid production files are modified.

## Question

Can ordinary VR4300 `SB` and `SH` stores mutate executable RDRAM in ways that an SW-oriented executable-write sensor would miss, and what exact byte/cache/fault contract is safe to normalize?

## Scope

Exact pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`, CPU and RSP recompilers disabled. The driver invokes the real pinned CPU `SB`/`SH` handlers against identity-mapped RDRAM. It tests big- and controlled little-endian contexts, cached KSEG0, uncached KSEG1, missing-TLB destinations, all offsets 0..7, and repeats each execution byte-for-byte.

This is an emulator-behavior/provenance experiment, not a claim about prevalence in commercial ROMs or about hardware cache timing.

## Reproduce

```bash
# .refs/ares must be the exact refs.lock.toml revision.
python3 spikes/036-ares-sb-sh-stores/source_guard.py
python3 spikes/036-ares-sb-sh-stores/model.py
python3 spikes/036-ares-sb-sh-stores/run.py
```

`run.py` reuses the established `spikes/003-ares-oracle` exact-pin headless build recipe. No ares source instrumentation is required for this experiment.

## Intended falsifiers

The run fails if any of these occur:

- `SB` changes more than one physical backing byte;
- aligned `SH` changes more than two physical backing bytes;
- cached success changes backing before writeback;
- reverse-endian mode disagrees with the Byte `paddr ^ 7` / Half `paddr ^ 6` mapping;
- odd-address `SH` commits any cache/backing mutation before Address Store Error;
- missing-TLB `SB` or aligned `SH` commits any mutation before TLB Store Miss;
- D-cache dirty coverage widens beyond the exact successful store lanes.

The independent Python model describes logical guest-byte effects and physical lane selection without importing emulator code.
