# Plaid

> Automatic N64 ROM -> native host application research project.

Plaid is an experimental toolchain whose long-term goal is simple to describe and difficult to earn:

```text
N64 ROM
  -> automatic program discovery
  -> static recompilation
  -> native x86-64 / ARM64 code
  -> small N64 compatibility runtime
  -> normal host application
```

The final gameplay path is **not** intended to contain a MIPS interpreter or a runtime MIPS JIT. Emulators and dynarecs are development tools, behavioral oracles, and discovery instruments only.

## North-star user experience

1. Install Plaid.
2. Select a legally obtained N64 ROM.
3. Plaid analyzes and compiles it.
4. The resulting native package is cached.
5. Future launches run the native package directly.

## What is actually new here?

Most individual ingredients already exist: accurate N64 emulation, MIPS dynarecs, static N64 recompilation, modern N64 rendering, and native N64 runtimes. The research problem is turning **open-ended runtime code discovery** into a **closed, complete executable map** that can be permanently linked without game-specific manual metadata.

See:

- [`docs/PLAN.md`](docs/PLAN.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/SOURCES.md`](docs/SOURCES.md)
- [`AGENTS.md`](AGENTS.md)
- [`SWARM_BACKLOG.md`](SWARM_BACKLOG.md)

## Non-goals

- Shipping ROMs, copyrighted game assets, keys, or proprietary Nintendo code.
- Calling a persistent dynarec cache a native recompilation.
- Claiming universal compatibility from one booting game.
- Reimplementing the whole N64 before reusing existing public research and tests.

## Initial proof target

The first meaningful proof is not "all 388 games." It is:

> Given an untouched ROM and no game-specific symbol/ELF input, recover a closed executable map, emit native host code, link it against the runtime boundary, and prove behavior against a reference implementation.

A simple title comes first. Overlay-heavy and custom-microcode titles come later on purpose, because suffering is more useful when scheduled.

## Repository state

Executable discovery v0 is implemented and verified on synthetic inputs through
the M1–M3 foundation: ProgramMap, pinned Mupen trace instrumentation, ROM
normalization, direct CFG, evidence merging, local indirect certificates,
DMA-backed loads and fail-closed solver reports. Whole-ROM closure and native
execution remain unimplemented. See [`docs/STATUS.md`](docs/STATUS.md) and
[`docs/NEXT.md`](docs/NEXT.md) for the precise scope.

## Build and verification

Rust and a C compiler are required by the pinned Rabbitizer dependency. Python
3.11+ and an x64 GCC toolchain are required by the integration scripts. The current
verification host is Windows/MinGW; portability is not yet verified.

```text
cargo test --workspace
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
python scripts/test_cli.py
python scripts/test_exporter.py
python scripts/test_mupen_hooks.py
python scripts/test_mupen_execution.py
```

The Mupen commands require the pinned checkout in `.refs/`; use
`python scripts/fetch_refs.py` to fetch the reference lab. The hook script prepares
the research patch, compiles actual Mupen routines and tests synthetic inputs. It
does not execute generated host code or validate N64 CPU behavior.
The execution script separately compares synthetic integer/control code on the
pinned x64 dynarec and pure interpreter, with tracing enabled and disabled.
It requires Linux GCC/NASM; Windows uses WSL Ubuntu. Set `PLAID_NASM` in Linux
when NASM is outside PATH. Flat memory and a sentinel stop policy exclude
boot, devices and interrupt timing from this test's scope.

## Discovery commands

```text
plaid rom-info <rom>
plaid check-trace <trace.ndjson>
plaid check-map <map.json>
plaid discover <rom> <rom_offset> <guest_start> <size> <entry> <out.json>
plaid import-trace <rom> <trace.ndjson> <out.json>
plaid merge <left.json> <right.json> <out.json>
plaid solve [rom] <map.json>
```

Numbers accept decimal or `0x` notation. `discover` requires an explicit load
mapping. Trace import compares captured DMA-backed code with the canonical ROM.
Supplying a ROM to `solve` reconstructs hash-checked source witnesses. The CLI
solver always uses whole-ROM scope and currently reports OPEN; a successful exit
means the report was produced. `native_complete` remains false.

Keep local ROMs in ignored `roms/` and derived traces/maps in ignored `artifacts/`.
No commercial ROM assets are needed by the tests.
