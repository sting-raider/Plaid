# RSP reset / NMI executable-lifetime experiment

This experiment composes Plaid's RSP IMEM provenance and microcode-installation work with the reset/NMI lifetime work.

It asks one narrow question: which reset-like transitions are actually RSP executable-storage transitions?

## Exact pins

Read from `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

## Components

- `driver.cpp` executes unmodified pinned ares component code. It seeds nonzero RSP IMEM plus a busy+full SP-DMA state, applies CPU NMI, `System::power(true)`, an equal-payload reset, and cold power, then asserts exact RSP storage/state outcomes.
- `source_guard.py` checks the exact source paths in all three pinned references. It intentionally preserves their disagreement instead of selecting a favorite emulator as hardware truth.
- `model.py` rejects two unsound generic policies: retire every reset-like transition and preserve every reset-like transition.
- `run.py` reuses Plaid's existing exact-pinned ares build harness and requires byte-identical repeated reference output.

## Reproduce

With exact refs checked out beneath `.refs/`:

```sh
python3 experiments/rsp-reset-imem-lifetime/source_guard.py
python3 experiments/rsp-reset-imem-lifetime/model.py
python3 experiments/rsp-reset-imem-lifetime/run.py
```

The experiment does not claim physical-N64 reset-button semantics from emulator agreement. Where exact pinned references disagree, the portable hardware-facing conclusion remains UNKNOWN until stronger system-test/hardware evidence exists.
