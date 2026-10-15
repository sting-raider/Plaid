# About

Plaid is a research tool for automatic Nintendo 64 ROM-to-native recompilation. It analyzes an untouched ROM into a closed executable program, lowers it to C, and links it into a native x86-64 or ARM64 application. No emulation, interpreter, or JIT in the final build; emulators are used only as analysis instruments and test oracles.

[Status](docs/STATUS.md), [next steps](docs/NEXT.md), [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), [development](docs/DEVELOPMENT.md), [milestone details](docs/PROGRESS.md)

## Status

[![VR4300](docs/badges/isa.svg)](docs/HISTORY.md) [![milestones](docs/badges/milestones.svg)](docs/PROGRESS.md) [![ROMs CLOSED](docs/badges/closed.svg)](docs/STATUS.md)

[![coverage maps](docs/coverage.svg)](docs/PROGRESS.md)

[Progress history](docs/HISTORY.md)

<sub>* VR4300 instructions: forms the VR4300 implements that pass discovery, the closure solver and native lowering in a test program (`plaid isa-coverage`), each differential-tested against the pinned ares interpreter in [spike096](spikes/096-native-slice/). RSP instructions: every instruction in the RSP manual, lowered to C by `plaid rsp-coverage` and checked against ares in [spike097](spikes/097-rsp-slice/). Milestones: states in [`docs/progress.json`](docs/progress.json); the total grows as milestones are added. ROMs CLOSED: commercial ROMs with whole-ROM closure and no assumptions.</sub>

## Milestones

| # | Milestone | State |
| --- | --- | --- |
| 1 | Synthetic ROM to C to native, matching ares exactly | **done** (spike096) |
| 2 | SM64 discovery finds at least 99% of its functions | **done**: 99.03%, scored against a local decomp map (ADR-0152) |
| 3 | SM64 `CLOSED` under declared assumptions | **done**: 45419 blocks, every assumption listed (ADR-0153..0156) |
| 4 | SM64 boots natively to its title screen | **done**, and further: gameplay at full speed, with input, saves and native audio (ADR-0159..0169) |
| 5 | Retire the assumptions one by one, then Ocarina of Time | next |

## How it works

```mermaid
flowchart TD
  rom[Untouched ROM] --> discover["discover<br/>CFG, indirect proofs, libultra identification, declared loads"]
  discover --> solve["solve<br/>closure proof in a declared scope"]
  solve -->|OPEN| stop[blockers report]
  solve -->|CLOSED| lower["plaid-lower<br/>one C function per guest function"]
  snaps[IMEM snapshots from running the game] --> rsplower["lower-rsp<br/>RSP microcode to C"]
  subgraph exe[native executable]
    game[lowered game code]
    rsp[lowered RSP microcode]
    rt[Plaid runtime: libultra on the host]
    rt64[RT64: graphics]
  end
  lower --> game
  rsplower --> rsp
  oracle[ares and Mupen64Plus: oracles only] -.->|differential tests| lower
  oracle -.-> rsplower
```

Unproven states fail closed: the solver reports `OPEN`, and lowered code checks every declared assumption at run time and aborts with a fault code when one is violated. There is no fallback to emulation.

Libultra system functions are declared as runtime functions and become calls into Plaid's own C runtime ([`runtime/`](runtime/), ADR-0158/0159): threads, message queues, events, timers, PI DMA, controllers, EEPROM and RSP tasks. Graphics go through [RT64](https://github.com/rt64/rt64) (MIT, [`runtime/rt64/`](runtime/rt64/)). Other RSP tasks, such as audio, run the game's own microcode lowered to C (ADR-0167..0169). Thread entries and other callbacks are proven per call site. How to build and run a game is in [`runtime/README.md`](runtime/README.md).

## Real ROMs

ROMs stay local and are never committed. Per-ROM numbers and how to reproduce them are in [`docs/STATUS.md`](docs/STATUS.md).

| ROM | Result |
| --- | --- |
| Super Mario 64 (USA) | 99.03% discovery recall. `CLOSED` over 45419 blocks under a declared scope: its main, engine and goddard segments, with calls through function pointers restricted to address-taken functions. Runs natively at full speed (59.9 VI/s), with graphics, input, EEPROM saves and audio. |
| Ocarina of Time (USA 1.2) | Boot plus the Yaz0-compressed `code` segment: 7684 blocks and 28 blockers under the guarded scope. 21 are function-pointer calls not yet provable (ADR-0142); 7 are calls into the 64DD driver, which ships on the disk. |
| Mario Party 2 (USA) | Boot window: 712 blocks and 29 blockers. 27 sit behind an `osInitialize` whose SDK build n64sym lacks; 2 are function-pointer calls. |

No commercial ROM is `CLOSED` whole-ROM without assumptions yet.

## Native runs: finding and fixing what breaks

Milestone 4 ran Super Mario 64 natively: the lowered game is linked with the runtime and run until it stops. Because nothing falls back to emulation, every stop is a fail-closed fault with an exact guest PC. Each fault points at a missing piece of the hardware model or of the runtime, and fixing one usually gets the game further. Each fix is a decision record with a differential test against ares:

| Stop | Cause | Fix |
| --- | --- | --- |
| First graphics task took 397 frames | every store scanned 45k code ranges | per-word protection map (ADR-0159) |
| `mtxf_lookat` fault 7 | libultra runs COP1 with Status.FR = 0 | FR = 0 register pairs (ADR-0160) |
| goddard reload, fault 2 | a reloaded segment was protected for good | loads re-verify after a write (ADR-0161) |
| goddard dynlists, fault 1 | data read through `osMapTLB` mappings | TLB-mapped data, with D-cache index aliasing (ADR-0162) |
| No picture | graphics tasks were only reported | RT64 bridge (ADR-0163) |
| Stuck at "PRESS START" | controller always idle | keyboard and scripted input (ADR-0164) |
| Half speed (33 VI/s) | Windows rounds 1 ms sleeps up to 15.6 ms | high-resolution timer and fixed VI deadlines (ADR-0166) |
| Silence | audio tasks completed without running | RSP scalar and vector microcode lowered to C (ADR-0167/0168) |
| "unlowered RSP code" | the boot microcode loads the audio microcode at run time | lowered IMEM snapshots, saved by running the game (ADR-0169) |
| Audio microcode, fault 4 | it reads the RDP status register | an idle-RDP read, checked against ares (ADR-0169) |

**SM64 now runs natively at full speed into gameplay** (59.9 VI/s, 30 fps): RT64 draws it (ADR-0163), the keyboard or a `--press` script controls it (ADR-0164), and `--save` keeps the EEPROM (ADR-0165). Its audio comes from the game's own RSP microcode, lowered to C; on real audio tasks it matches ares in every byte (ADR-0169). `--wav` records the audio; live playback is next (ADR-0170). The latest run is in [`research/sm64-first-measurement.md`](research/sm64-first-measurement.md), and what comes next is in [`docs/NEXT.md`](docs/NEXT.md).

## Per-game inputs and known gaps

Nothing in the compiler or the runtime is keyed to SM64: no game names, addresses or patches. The runtime implements libultra functions by name, and RT64 draws any game's display lists. A game does need a few inputs, given on the command line or in JSON:

- **Where its code is**: the main segment's ROM offset, address, size and entry point.
- **Executable loads** (`--loads`): code segments copied at run time, such as SM64's engine and goddard segments, with their ROM ranges and addresses. They are declared by hand today. The native build checks their bytes when they are loaded and faults on a mismatch.
- **Which functions are libultra** (`plaid identify`): n64sym signatures, or a symbol map with `--symbols` when the game's SDK build is missing from n64sym's database. SM64 uses its decomp symbol map, which stays local. The map only names functions; it is not used to find code.
- **The assumption scope**: for example `--address-taken` and `--fr0`. Every assumption is listed in the solver's report.

Known gaps for other games:

- Compressed or relocated code segments, as in Ocarina of Time (Yaz0 and overlay relocations), are not lowered yet. Load discovery is manual.
- The runtime covers the libultra functions that SM64 calls. A game that calls a declared function the runtime lacks fails to link.
- Saves are 4 Kbit EEPROM only (no 16 Kbit EEPROM, SRAM, Flash or Controller Pak). Only controller 1 works, and there is no rumble.
- RSP microcode comes from running the game, not from ROM offsets: `--rsp-dump` saves each IMEM image no lowered code holds, and `runtime/rsp_texts.py` lowers it for the next build. A new game needs one or more of these runs. Graphics tasks go to RT64, not lowered microcode. Audio is written to a WAV file; it does not play live yet.
- Only Windows has been tested with RT64.

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
