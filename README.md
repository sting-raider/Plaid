# About

Plaid is a research tool for automatic Nintendo 64 ROM-to-native recompilation. It analyzes an untouched ROM into a closed executable program, lowers it to C, and links it into a native x86-64 or ARM64 application. No emulation, interpreter, or JIT in the final build; emulators are used only as analysis instruments and test oracles.

[Status](docs/STATUS.md), [next steps](docs/NEXT.md), [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), [development](docs/DEVELOPMENT.md), [milestone details](docs/PROGRESS.md)

## Status

[![VR4300](docs/badges/isa.svg)](docs/HISTORY.md) [![milestones](docs/badges/milestones.svg)](docs/PROGRESS.md) [![ROMs CLOSED](docs/badges/closed.svg)](docs/STATUS.md)

[![coverage maps](docs/coverage.svg)](docs/PROGRESS.md)

[Progress history](docs/HISTORY.md)

<sub>* VR4300 instructions: forms the VR4300 implements that pass discovery, the closure solver and native lowering in a test program (`plaid isa-coverage`), each differential-tested against the pinned ares interpreter in [spike096](spikes/096-native-slice/). Milestones: states in [`docs/progress.json`](docs/progress.json); the total grows as milestones are added. ROMs CLOSED: commercial ROMs with whole-ROM closure and no assumptions.</sub>

Unproven states fail closed: the solver reports `OPEN`, and lowered code checks every declared assumption at run time and aborts with a fault code when one is violated. There is no fallback to emulation.

Libultra system functions are declared as runtime functions and become calls into Plaid's own C runtime ([`runtime/`](runtime/), ADR-0158/0159): threads, message queues, events, timers, PI DMA, controllers and EEPROM. Graphics go through [RT64](https://github.com/rt64/rt64) (MIT, [`runtime/rt64/`](runtime/rt64/)). Thread entries and other callbacks are proven per call site.

## Real ROMs

On a local Ocarina of Time boot window, 39 libultra functions are identified by n64sym signature and discovery reaches 320 blocks with 16 blockers under the guarded assumption scope. Declaring the Yaz0-compressed `code` segment as a load, checked by content in the native artifact, and identifying the libultra functions inside it as well leaves 29 blockers over 7684 blocks: function-pointer calls not yet proven, and calls into the 64DD driver segment. Super Mario 64 (USA) solves `CLOSED` under a declared assumption scope: its main, engine and goddard segments, with calls through function pointers restricted to address-taken functions. That covers 45419 blocks. Every assumption is listed in the report, and most are checked by the native artifact. No commercial ROM is `CLOSED` whole-ROM without assumptions yet. Per-ROM numbers and how to reproduce them are in [`docs/STATUS.md`](docs/STATUS.md).

## Native runs: finding and fixing what breaks

Milestone 4 is running Super Mario 64 natively to its title screen. The lowered game is linked with the runtime and run until it stops. Because nothing falls back to emulation, every stop is a fail-closed fault with an exact guest PC. Each fault points at a missing piece of the hardware model or of the runtime, and fixing one usually gets the game further. Each fix is a decision record with a differential test against ares. So far:

| Stop | Cause | Fix |
| --- | --- | --- |
| First graphics task took 397 frames | every store scanned 45k code ranges | per-word protection map (ADR-0159) |
| `mtxf_lookat` fault 7 | libultra runs COP1 with Status.FR = 0 | FR = 0 register pairs (ADR-0160) |
| goddard reload, fault 2 | a reloaded segment was protected for good | loads re-verify after a write (ADR-0161) |
| goddard dynlists, fault 1 | data read through `osMapTLB` mappings | TLB-mapped data, with D-cache index aliasing (ADR-0162) |
| No picture | graphics tasks were only reported | RT64 bridge (ADR-0163) |
| Stuck at "PRESS START" | controller always idle | keyboard and scripted input (ADR-0164) |
| Half speed (33 VI/s) | Windows rounds 1 ms sleeps up to 15.6 ms | high-resolution timer and fixed VI deadlines (ADR-0166) |

**SM64 now runs natively at full speed into gameplay** (59.9 VI/s, 30 fps): RT64 draws it (ADR-0163), the keyboard or a `--press` script controls it (ADR-0164), and `--save` keeps the EEPROM (ADR-0165). Audio is still to come. The latest run is in [`research/sm64-first-measurement.md`](research/sm64-first-measurement.md), and what comes next is in [`docs/NEXT.md`](docs/NEXT.md).

## Build

```bash
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

The full local gate, the native differential test and reference-lab setup are in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Disclaimer

This project is intended for interoperability, research, and preservation purposes. It does not include, distribute, or require copyrighted software, firmware, keys, or proprietary libraries. Users are responsible for obtaining and using any ROM in accordance with applicable laws.

## License

Plaid is licensed under either of [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option. The Mupen64Plus instrumentation in `instruments/mupen/` is a separately licensed GPL research instrument (see its `COPYING`) and is not part of Plaid's compiler or runtime. Reused third-party logic is credited where it is used.
