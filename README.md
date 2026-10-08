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

Bootstrap/research scaffold only. No compatibility claim is implied.
