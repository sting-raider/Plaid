# ares COP1 `ADD.S` NaN/subnormal exception spike

Status: research-only exact-pin experiment.

Question: does exact pinned ares treat every NaN input to VR4300 `ADD.S` as the same Invalid Operation case, or are raw NaN encodings and subnormal inputs observably distinct before destination writeback?

The fixture executes the real instruction word `0x46041180` (`ADD.S f6,f2,f4`) through the pinned ares interpreter with recompiler disabled. It records raw FPR state, FCSR, CPU exception code, EPC, and PC for a finite control plus four adversarial inputs.

NaN cases are deliberately named by raw fraction bit 22 rather than `sNaN`/`qNaN`. Pinned `n64-systemtest` follows modern IEEE naming (`0x7f800001..0x7fbfffff` signalling, `0x7fc00000..` quiet), while pinned ares' helper named `snan(f32)` returns bit 22. The raw encodings and observed state transitions are the durable identity; source-local naming is not.

## Reproduce

The runner reuses the build machinery from `spikes/003-ares-oracle/run.py` and requires `.refs/ares` at the revision pinned by `refs.lock.toml`. Pinned `n64-systemtest`, Mupen64Plus and Gopher64 checkouts add source guards for the hardware-test expectations and reference disagreements described by the research note.

```sh
mkdir -p .refs
git clone https://github.com/ares-emulator/ares.git .refs/ares
git -C .refs/ares checkout 9408cb43d4948fc3ea6e152a307a34348df3fe04
python3 spikes/044-ares-fpu-nan-exceptions/run.py
```

For the full four-reference source guards used in CI:

```sh
git clone https://github.com/lemmy-64/n64-systemtest.git .refs/n64-systemtest
git -C .refs/n64-systemtest checkout 196f5421173220eb2f63a7a99c64795dc0ea0698
git clone https://github.com/mupen64plus/mupen64plus-core.git .refs/mupen64plus-core
git -C .refs/mupen64plus-core checkout ba95bab92a76744753bfe61470823a4937850ab0
git clone https://github.com/gopher64/gopher64.git .refs/gopher64
git -C .refs/gopher64 checkout e96debac941a26ba4961e5145056c0821d3a56f7
python3 spikes/044-ares-fpu-nan-exceptions/run.py
```

Generated results live under `target/ares-fpu-nan-exceptions/` and are intentionally not committed.
