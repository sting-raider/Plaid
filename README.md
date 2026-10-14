# Plaid

> Experimental Nintendo 64 ROM-to-native recompilation research.

Plaid analyzes an **untouched N64 ROM** into a closed executable program, lowers it ahead of time through C, and links it into a normal native application. Final gameplay must not contain a MIPS interpreter, a runtime JIT/dynarec, or any hidden instruction fallback; emulators are used only as analysis instruments and differential-test oracles.

[Status](docs/STATUS.md), [next steps](docs/NEXT.md), [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), [development](docs/DEVELOPMENT.md), [progress map](docs/PROGRESS.md), [progress history](docs/HISTORY.md)

## Status

[![VR4300 lowered](docs/badges/isa.svg)](docs/HISTORY.md) [![milestones](docs/badges/milestones.svg)](docs/PROGRESS.md) [![commercial ROMs CLOSED](docs/badges/closed.svg)](docs/STATUS.md)

[![Plaid progress history](docs/history.svg)](docs/HISTORY.md)

[![Plaid engineering progress atlas](docs/progress.svg)](docs/PROGRESS.md)

<sub>* **VR4300 lowered:** instruction forms the VR4300 implements (as decoded by the pinned decoder, pseudo-instructions and non-VR4300 forms excluded) that pass discovery, the guarded-scope solver and native lowering inside a test program, measured by `plaid isa-coverage`. Every lowered form is differential-tested against the pinned ares interpreter in [spike096](spikes/096-native-slice/). **Milestones:** states in [`docs/progress.json`](docs/progress.json); the total grows as milestones are added, so this is not a completion percentage. **Commercial ROMs CLOSED:** whole-ROM closure without assumptions.</sub>

Unproven states fail closed. The solver reports `OPEN` for any unproven control transfer or effect, and assumption-qualified scopes list every assumption they make. Lowered code checks each assumption at run time and aborts with a fault code when one is violated (store into code or a jump table, a return to the wrong caller, an overflowing trapping add, and so on). There is no fallback to emulation.

Current frontier: on a local Ocarina of Time boot window, discovery with declared runtime functions and proven thread-entry callbacks reaches 628 blocks with 6 blockers left under the guarded assumption scope. The runtime declarations are still chosen by a heuristic; identification evidence is next ([`docs/NEXT.md`](docs/NEXT.md)).

## How it works

```text
N64 ROM
  │
  ▼
discover executable code + provenance          (ProgramMap, evidence-backed)
  │
  ▼
prove the executable universe is closed        (fail-closed solver, explicit scopes)
  │
  ▼
lower MIPS → C → native x86-64 / ARM64         (crates/plaid-lower, checked assumptions)
  │
  ▼
link with the N64 runtime                      (N64ModernRuntime + RT64, ADR-0126)
  │
  ▼
native host application
```

Plaid's own contribution is the first two steps: automatic discovery and closure proof from the ROM alone. Below that it reuses existing work. Declared runtime functions (libultra system code) become calls into the host runtime, as in N64Recomp, but each declaration is evidence-backed and checked by the solver.

## Where the project stands

| Area | State | What exists on `main` | What is still missing |
| --- | --- | --- | --- |
| **Discovery & ProgramMap** | strong foundation | ROM normalization, deterministic ProgramMap, trace import, direct CFG, evidence merge, constant and cross-block indirect proofs, return certificates, jump tables, runtime-callback proofs | identification evidence for runtime functions, memory-loaded function pointers, overlays |
| **Executable provenance** | partial, paused | PI/SP/PIF source histories, cache/TLB context, CPU copy and RSP mutation evidence | resumed when a milestone needs it (ADR-0125) |
| **Closed-world proof** | active | fail-closed solver, source rechecking, `DeclaredStaticImages` and `DeclaredStaticImagesGuardedRam` assumption scopes | first commercial ROM `CLOSED` |
| **Native AOT compiler** | working subset | `plaid-lower`: one C function per guest function, checked returns, proven-target and jump-table dispatch, 64-bit integer and COP1 data moves, runtime calls and callback dispatch; differential-tested against ares | FPU arithmetic, unaligned loads/stores, COP0 behind the runtime |
| **Native runtime** | boundary only | declared runtime functions and fail-closed `plaid_enter` callbacks | linking N64ModernRuntime + RT64 |
| **Compatibility** | research | synthetic corpus, pinned Mupen/ares oracles, local OoT measurements | first commercial ROM booting natively |

## Why this is hard

A normal static recompiler starts with a known executable image. An N64 ROM can break that assumption in several ways:

- code can be copied or DMA'd into RAM before execution;
- overlays can be loaded, relocated, replaced, or aliased;
- indirect branches and pointer tables can depend on runtime state;
- cached instructions can outlive current backing bytes;
- CPU, RSP, DMA, decompression, relocation, or patching can produce executable bytes;
- exceptions, interrupts, reset/NMI, and RSP execution add additional roots.

Plaid therefore treats executable discovery as a proof problem, not just a disassembly problem. If an obligation cannot be justified, the result stays `OPEN` instead of quietly falling back to emulation.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`crates/plaid-core/`](crates/plaid-core/) | ProgramMap, discovery, provenance, solver and proof logic |
| [`crates/plaid-lower/`](crates/plaid-lower/) | CLOSED ProgramMap → C lowering and ISA coverage measurement |
| [`apps/plaid/`](apps/plaid/) | command-line interface |
| [`docs/`](docs/) | status, decisions, roadmap, progress data and history |
| [`research/`](research/) | research notes and integration receipts |
| [`spikes/`](spikes/) | bounded reference experiments, including the native differential test (spike096) |
| [`instruments/`](instruments/), [`experiments/`](experiments/) | instrumentation and independent models kept out of production logic |
| [`refs.lock.toml`](refs.lock.toml) | pinned external reference revisions |

## Build and local verification

Plaid is a Rust workspace. The canonical checks run **locally**:

```bash
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python tools/progress.py --check
```

`python spikes/096-native-slice/run.py` runs the native differential test against the pinned ares interpreter (needs a C compiler and WSL Ubuntu). `python tools/progress.py --record` measures the current tree into today's history point. GitHub Actions is manual-only. Setup and CLI details are in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Ground rules

- No ROMs, copyrighted game assets, firmware, keys, or proprietary Nintendo code in git.
- No hidden interpreter/JIT fallback in a claimed native path.
- Unknown provenance stays unknown; finite traces do not prove exhaustive coverage.
- Game-specific hacks do not count as general discovery.
- Every compiler transformation needs an independent verifier.
- `native_complete` stays `false` until the closure obligations are proven.

## Disclaimer

Plaid is intended for interoperability, research, and preservation. It does not include, distribute, or require copyrighted software, firmware, keys, or proprietary libraries. Users are responsible for obtaining and using any ROM in accordance with applicable laws.

## License

No license has been chosen yet. Until one is, all rights are reserved by the author. Linking with N64ModernRuntime (GPL-3.0) will make native game builds GPL-3.0 (ADR-0126).
