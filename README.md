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
python scripts/test_fetch.py
python scripts/test_boot_fetch.py
python scripts/test_cache_fetch.py
python scripts/test_history.py
python scripts/test_pi_history.py
python scripts/test_pi_queue_history.py
python scripts/test_mupen_hooks.py
python scripts/test_mupen_execution.py
python scripts/test_mupen_session.py
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

The session script builds the full pinned core separately under ignored `target/`
and runs an original synthetic bootstrap through real PI DMA, RAM and IS64 MMIO.
It compares interpreter/traced/untraced CPU state and deterministic traces, then
imports the DMA-backed code and checks OPEN solver output. Linux GCC/make/NASM,
Python 3.12+, SDL2/zlib/libpng development headers and runtime libraries are needed.
Windows uses WSL Ubuntu. `PLAID_REF_DEPS` can point to an extracted x64 Linux
dependency prefix instead of system headers. Bundled dummy plugins exclude
rendering, audio and RSP execution; this establishes no game compatibility.

## Discovery commands

```text
plaid rom-info <rom>
plaid check-trace <trace.ndjson>
plaid check-map <map.json>
plaid discover <rom> <rom_offset> <guest_start> <size> <entry> <out.json>
plaid import-trace <rom> <trace.ndjson> <out.json>
plaid import-fetch <rom> <fetch.ndjson> <out.json>
plaid verify-fetch <rom> <fetch.ndjson> <map.json>
plaid import-boot-fetch <rom> <firmware> <fetch.ndjson> <out.json>
plaid verify-boot-fetch <rom> <firmware> <fetch.ndjson> <map.json>
plaid inspect-boot-history <rom> <firmware> <fetch.ndjson> <history.ndjson> <report.json>
plaid verify-boot-history <rom> <firmware> <fetch.ndjson> <history.ndjson> <report.json>
plaid inspect-pi-boot-history <rom> <firmware> <fetch.ndjson> <history-v1.ndjson> <report.json>
plaid verify-pi-boot-history <rom> <firmware> <fetch.ndjson> <history-v1.ndjson> <report.json>
plaid inspect-pi-queue-boot-history <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json>
plaid verify-pi-queue-boot-history <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json>
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

`import-fetch` streams the pinned ares observer's separate format into raw 64-bit
PC/word/slot summaries. `verify-fetch` regenerates them from the complete source.
Research v1 additionally retains effective physical address and cache policy;
remapped/cache variants stay distinct. V0 remains compatible and byte-identical.
V2 retains actual cartridge-read or unknown source, requiring canonical word,
mapped-capacity and access checks. A source witness supplies no image lifetime.
They have no established image generation, code lifetime or retirement identity;
the solver keeps them OPEN. After spike 004 creates the ignored broad capture,
`python scripts/test_fetch_corpus.py` checks full-source provenance, self-merge and
OPEN output and records one-host import cost. The raw stream remains required.
After spike 005, add `--physical` to recheck its complete v1 capture.
After spike 007, use `--source` to recheck canonical v2 source witnesses.
V4/v5 require `import-boot-fetch`/`verify-boot-fetch` with the actual local firmware
input. The complete fixed boot profile and firmware hash/size are checked.
V5 additionally retains the selected cache slot/tag/index/eight words for cached
fetches and verifies the effective fetched lane; other lanes have no execution
claim. Resident context does not establish fill origins or executable lifetimes.
After spikes 009/011, use corpus `--boot`/`--cache`, optionally
`--budget 10000000`, for the corresponding complete sources. V3 remains unsupported.

`inspect-boot-history` checks a bounded spike-027 access sidecar against every
corresponding v5 fetch and the supplied ROM/firmware. Its independent report
retains both complete source hashes, event counts and unambiguous scalar/fill
witness counts. `verify-boot-history` reconstructs the complete report, including
unused payloads, and rejects source/input/report changes. Ambiguous reads and
unsupported backing stay unknown; no ProgramMap images, generations, lifetimes
or closure rules are created. `python scripts/test_history.py` exercises CLI
input/rechecking/overwrite gates with original synthetic inputs.

`inspect-pi-boot-history` separately checks the spike-030 v1 protocol, buffered
canonical ROM byte origins and successful identity-RAM effects. Its report binds
both complete sources, the exact v0 projection and finite writer effects.
`verify-pi-boot-history` reconstructs the entire report from supplied inputs.
Observed busy/interrupt contexts do not certify transfer completion; executable
identities and lifetimes remain open. The original history commands reject v1.
`python scripts/test_pi_history.py` checks byte orders, source/report tampering,
version separation and input-overwrite protection with original synthetic data.

`inspect-pi-queue-boot-history` checks the separate spike-037 v2 request, queue
outcome and actual dispatch/status scopes before complete nested v1/v0/v5
verification. Its report distinguishes rejected insertions, unknown/unbound
statuses and requests without observed status. These are finite observations;
requests without status are not a live-queue census or transfer timing proof.
`verify-pi-queue-boot-history` rebuilds the entire report from complete sources.
The older consumers reject v2, and guest/native completion remains false.
`python scripts/test_pi_queue_history.py` tests canonical byte orders, forged
identities, complete-source/report changes and input-overwrite protection.

Additional disposable reference experiments are documented under `spikes/`.
`python spikes/003-ares-oracle/run.py` builds the pinned ares core separately and
checks original cartridge, linked-memory and exception cases plus eight independent
Mupen CPU comparisons. It requires Linux G++ C++20 (Windows uses WSL Ubuntu).
Its explicit synthetic initial state excludes boot and full hardware validation.
