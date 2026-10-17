<div align="center">

# Plaid

**Turn an untouched Nintendo 64 ROM into a native program, with no emulator inside.**

[![VR4300](docs/badges/isa.svg)](docs/HISTORY.md) [![milestones](docs/badges/milestones.svg)](docs/PROGRESS.md) [![ROMs CLOSED](docs/badges/closed.svg)](docs/STATUS.md)

[Status](docs/STATUS.md) · [Next steps](docs/NEXT.md) · [Architecture](docs/ARCHITECTURE.md) · [Decisions](docs/DECISIONS.md) · [Development](docs/DEVELOPMENT.md) · [Milestones](docs/PROGRESS.md)

</div>

Plaid is a research tool for automatic Nintendo 64 ROM-to-native recompilation. It analyzes a ROM into a closed executable program, lowers it to C, and links it into a native x86-64 or ARM64 application. There is no emulator, interpreter or JIT in the final build. Emulators are used only as analysis instruments and test oracles.

## Progress report

*As of main `a5e3eb9`, 2026-10-17. Every row traces to [`docs/STATUS.md`](docs/STATUS.md) or an ADR in [`docs/DECISIONS.md`](docs/DECISIONS.md). "Natively" means the lowered game linked with Plaid's runtime: no interpreter, no JIT, and every unproven state is a fail-closed fault.*

**Two finish lines.**
1. **ROM in, game runs:** you supply only a ROM. Plaid discovers the code, proves it closed under a declared assumption scope, lowers it to C and builds the executable. **Reached for Majora's Mask and F-Zero X** (the build needs no hand input beyond the scope flags), not yet for SM64 or OoT, and no game has been played to the end.
2. **ROM in, provably complete with zero assumptions:** the whole ROM is `CLOSED` with no assumption. **Not reached: 0 of 16 assumptions retired, no ROM is whole-ROM `CLOSED`.**

### Per game

| | Super Mario 64 (USA) | Ocarina of Time (USA 1.2) | Majora's Mask (USA) | F-Zero X (USA) |
| --- | --- | --- | --- | --- |
| Inputs by hand | code segment, 2 `--loads`, local decomp map for 3 runtime names | code segment, 2 `--loads` (earlier builds) | **none**: loads and runtime inferred from the ROM (ADR-0183) | **none**: inferred from the ROM (ADR-0184/0185) |
| Closure, scope `--address-taken` | ✅ `CLOSED`, 45,419 blocks (ADR-0153..0156) | ✅ `CLOSED`: fixed image 29,542 blocks (ADR-0175); with 468 overlays 154,414 blocks (ADR-0180) | ✅ `CLOSED` with overlays (ADR-0183) | ✅ `CLOSED`, 27,621 blocks, 0 scoped blockers (ADR-0185) |
| Whole-ROM, no assumptions | OPEN, 4,820 blockers | OPEN, 16,338 with overlays | OPEN, 21,313 | OPEN, 2,995 |
| How far it runs natively | 59.9 VI/s gameplay with input and saves | boot logo, title screen, file select (ADR-0182) | intro and Clock Town attract scene; erased-FlashRAM run passes the old heap-overlay fault and reaches VI 5358 at the 90 s limit, fault 0 (ADR-0187) | visible 65 s races, vehicle markings and shading, no fault (ADR-0186) |
| Graphics | RT64 display-list HLE | RT64 display-list HLE | RT64 display-list HLE | compiled graphics microcode, raw RDP to RT64 (`--rsp-gfx`, ADR-0186) |
| RSP microcode source | from the ROM; 20 s run, fault 0, nonzero PCM (ADR-0188) | ROM-only run refuses at VI 2 on a protected RSP DMA write, so the title and file select above predate it (ADR-0188) | from the ROM; 60 s run, fault 0, nonzero PCM (ADR-0188) | from the ROM, with `--rsp-gfx`; 20 s run, fault 0, nonzero PCM (ADR-0188) |
| Audio | native: the game's own RSP microcode lowered to C, played via SDL (ADR-0169/0170) | native, lowered microcode (ADR-0182) | restored, PCM peak 32569 in a 60 s run; a real audio task matches ares (ADR-0189) | native, in the same race runs (ADR-0186) |
| Saves | EEPROM | SRAM | FlashRAM | in the race runs (ADR-0186) |
| Known stop points | none recorded in a 90 s run | beyond file select is untested | none since ADR-0187; the earlier stop (heap overlay at VI 3188) is fixed. This is finite execution, not a loader-lifetime proof | none in 65 s runs |

### Distance to "ROM in, game runs"

| Remaining hand input | Status | What retires it |
| --- | --- | --- |
| **RSP microcode** is derived from the ROM by default; IMEM snapshots are oracle-only (ADR-0188) | 🟨 partial: SM64, MM and F-Zero X run with ROM-derived microcode; OoT refuses at VI 2 on a protected RSP DMA write (ADR-0188) | resolve OoT's bootstrap path without a game exception, broaden task, overlay and DMA coverage, and prove the solver's general RSP policy |
| Code segment address and entry point (SM64, OoT) | inferred for MM and F-Zero X (ADR-0183/0184) | run the same inference on SM64 and OoT, which lack a usable file table for it |
| `--loads` files (SM64: 2, OoT: 2) | inferred for MM and F-Zero X; SM64's inference finds the engine segment but not goddard (ADR-0184). On unseen ROMs, Banjo-Kazooie is scoped OPEN with 1 blocker (ADR-0190..0192) and five others stop earlier ([`research/rom-sweep.md`](research/rom-sweep.md)) | broader load inference |
| SM64 decomp map for three runtime names (ADR-0171) | local, never used to find code | identify them from the ROM's bytes (assumption 14) |
| Scope flags (`--address-taken`, `--fr0`) | chosen by the user; `native.py` refuses to build unless the scope is `CLOSED` | none: the scope is the declared assumption set |
| libultra as host runtime (HLE) | covers the functions SM64, OoT and MM call; a game calling another fails to link | differential-test each function (assumption 13) |

Only Windows has been tested with RT64. Only controller 1 works, with no rumble.

### Distance to "zero assumptions"

**0 of 16 assumptions retired.** No ROM is whole-ROM `CLOSED`; every commercial ROM still has thousands of blockers, most of them unresolved indirect sites. Recent work (ADR-0180, ADR-0181, ADR-0187) shrank the scoped proofs and the run-time failures, and retired none. The full ledger and blocker table are generated below; the largest items are code immutability and overlay lifetimes (1, 12), the excluded interrupts, DMA and RSP (2), and per-site proofs of indirect targets (4..6).

### Recent landings

| ADR | Commit | What |
| --- | --- | --- |
| 0194 | `a5e3eb9` | Identification retains verified per-copy SDK scalar address bindings |
| 0193 | `b6006cb` | Restoring a saved zero interrupt bit keeps an enabled one enabled |
| 0192 | `37399f3` | Paired-stream executable slots derived and verified; Banjo-Kazooie 29 to 1 scoped blocker |
| 0191 | `6d846df` | Independent SDK copies identified across disconnected images (partial) |
| 0190 | `8a35ad3`, `40dde18` | Boot-produced executable images recovered, the second with pinned ares (partial) |
| 0188 | `6758817` | RSP microcode derived from the ROM, with fetch-verified dispatch |
| 0189 | `8139af6` | Lowered RSP code shares the host's state layout; Majora's Mask has sound |
| 0187 | `32408f6` | Inactive heap overlays rebind under native-frame pins; MM passes its heap-overlay fault |
| 0186 | `64fe72b` | Compiled graphics microcode feeds RT64 raw RDP; verified build packaged; F-Zero X races |
| 0185 | `39ed3cc` | Executable files sharing a RAM slot are verified and lowered; F-Zero X `CLOSED` |
| 0184 | `583f07c` | Boot image and segments inferred from the ROM alone |
| 0183 | `edb3ca0` | ROM in, native out; Majora's Mask plays its intro |
| 0182 | `3cd1b2b` | OoT reaches its title and file select with RT64 |
| 0181 | `00cb683` | Relocatable overlays run natively through a verified binding |
| 0180 | `42513ef` | Jump-table bounds proven over every path; OoT + overlays `CLOSED` |
| 0179 | `9e652ab` | Discovery places relocatable overlays at their link addresses |

### How to play

You supply the ROM; ROMs are never committed. `python scripts/native.py <rom> --rt64 [--rsp-gfx]` builds the executable and writes a `Play <name>.cmd` launcher beside it. Built executables live in `target/rt64-shim/Release/` next to `plaid_rt64.dll` and `SDL2.dll`. For example, Majora's Mask is `target/rt64-shim/Release/mm-rt64.exe`; from the repo root:

```powershell
.\target\rt64-shim\Release\mm-rt64.exe --rom <your mm.z64> --flash <save.fla> --stop-at none
```

Keyboard controls (RT64 window; `--press` scripts are ORed with it):

| Key | Button |
| --- | --- |
| X / C / Z | A / B / Z |
| Enter | START |
| Q / E | L / R |
| I / K / J / L | C-up / C-down / C-left / C-right |
| W / S / A / D | D-pad |
| Arrow keys | Control stick |

The save flag depends on the game: `--flash` (Majora's Mask), `--save` (EEPROM games). Build details: [`runtime/README.md`](runtime/README.md).

## Status

[![instruction coverage and assumptions](docs/coverage.svg)](docs/PROGRESS.md)

[Progress history](docs/HISTORY.md)

<sub>* **These percentages do not mean a game works or is proven.** Colors: green means the form matches ares and depends on no run-time assumption; amber means it matches ares but native code checks an assumption and aborts when it fails (loads and stores, indirect jumps and returns, overflow-trapping arithmetic, traps, `BREAK`); orange means it relies on an assumption nothing checks (all COP1 depends on `Status.FR = 0`); grey means not lowered. VR4300 instructions: instruction semantics only. A form counts when it passes discovery, the closure solver and native lowering in a test program (`plaid isa-coverage`) and matches the pinned ares interpreter in [spike096](spikes/096-native-slice/). Exceptions and interrupts are not modelled. The unfilled cells are COP0 moves, TLB instructions, `ERET`, `SYSCALL` and `CACHE`: they are not lowered in guest code, and libultra's uses of them are replaced by Plaid's own runtime (an assumption, listed below). RSP instructions: 100% means every RSP instruction lowers to C and matches ares in [spike097](spikes/097-rsp-slice/). The orange "In a real game" bar is the other half: it does not mean a game's RSP side is proven: microcode is derived from the ROM with every fetch checked (ADR-0188), but the candidate registry is incomplete and the solver's RSP policy is unproven; graphics microcode runs natively with `--rsp-gfx`, while the default RT64 path interprets display lists at a high level; and RSP tasks complete synchronously. Milestones: states in [`docs/progress.json`](docs/progress.json); the total grows as milestones are added. ROMs CLOSED: commercial ROMs with whole-ROM closure and no assumptions.</sub>

## Distance to no-assumption CLOSED

<!-- assumptions:begin -->

### Distance to no-assumption CLOSED

[![whole-ROM blockers by class](docs/assumptions.svg)](docs/assumptions.json)

No commercial ROM is `CLOSED` whole-ROM without assumptions. Assumptions retired: **0/16**. Measured 2026-10-17 with `plaid solve <rom> <map> [scope]`; data in [`docs/assumptions.json`](docs/assumptions.json), generated by `tools/progress.py`.

| ROM | Blocks | Indirect sites closed with no assumption | Whole-ROM blockers | Scoped results |
| --- | --- | --- | --- | --- |
| Super Mario 64 (USA) | 45,419 | 1 of 4,385 | OPEN, 4,820 | `--guarded-ram` **OPEN** (91 blockers), 14 assumptions; `--address-taken` **CLOSED**, 15 assumptions |
| Ocarina of Time (USA 1.2), fixed image | 29,613 | 2 of 2,574 | OPEN, 3,120 | `--guarded-ram` **OPEN** (122 blockers), 12 assumptions; `--address-taken` **CLOSED**, 13 assumptions |
| OoT + 468 overlays at link addresses | 155,770 | 6 of 14,869 | OPEN, 16,338 | `--guarded-ram` **OPEN** (711 blockers), 13 assumptions; `--address-taken` **CLOSED**, 14 assumptions |
| Majora's Mask (USA) + overlays, inferred loads | 214,963 | 10 of 19,138 | OPEN, 21,313 | `--guarded-ram` **OPEN** (891 blockers), 13 assumptions; `--address-taken` **CLOSED**, 14 assumptions |
| F-Zero X (USA), inferred shared-slot alternates | 27,621 | 1 of 1,974 | OPEN, 2,995 | `--guarded-ram` **OPEN** (44 blockers), 13 assumptions; `--address-taken` **CLOSED**, 14 assumptions |

Whole-ROM blockers by class:

| Class | sm64 | oot | oot-overlays | mm | fzerox |
| --- | ---: | ---: | ---: | ---: | ---: |
| `unresolved_indirect_site` | 4,384 | 2,572 | 14,863 | 19,128 | 1,973 |
| `exception_or_unsupported_instruction` | 78 | 284 | 651 | 955 | 422 |
| `pointer_table_immutability_unproven` | 147 | 96 | 376 | 571 | 120 |
| `pointer_table_target_identity_unproven` | 147 | 96 | 376 | 571 | 120 |
| `unresolved_direct_target` | 0 | 0 | 0 | 0 | 162 |
| `unmapped_target` | 0 | 0 | 0 | 0 | 131 |
| `runtime_boundary_outside_scope` | 57 | 65 | 65 | 81 | 60 |
| `dynamic_effect_outside_scope` | 1 | 1 | 1 | 1 | 1 |
| `unmodeled_exception_paths` | 1 | 1 | 1 | 1 | 1 |
| `unproven_executable_universe` | 1 | 1 | 1 | 1 | 1 |
| `unproven_executable_write_policy` | 1 | 1 | 1 | 1 | 1 |
| `unproven_load_overlay_policy` | 1 | 1 | 1 | 1 | 1 |
| `unproven_rsp_policy` | 1 | 1 | 1 | 1 | 1 |
| `unsupported_execution_modes` | 1 | 1 | 1 | 1 | 1 |

Assumptions behind the SM64 `--address-taken` result. "Fault n" means the native artifact tests it at run time and aborts with that code; **unchecked** ones are trusted.

| # | Assumption | Run-time check | State | Retired when |
| ---: | --- | --- | --- | --- |
| 1 | Only declared image entries execute; code is immutable | fault 2/3 | assumed | model code writes (self-modifying code, overlay loads) and prove every executable byte's origin |
| 2 | Interrupts, exceptions, DMA, MMIO, overlays, RSP and external entries are excluded from analysis | **unchecked** | assumed | model them in the closure proof, or prove the HLE runtime equivalent; the runtime stands in for them today |
| 3 | 32-bit address model | fault 1 | assumed | model 64-bit addressing and the full TLB, or prove the game never leaves the 32-bit subset |
| 4 | Register calls reach only address-taken functions (1,341 in SM64) | fault 3 | assumed | prove each indirect site's target set by data flow, jump-table shape or points-to |
| 5 | Forwarded runtime-callback wrappers are entered only by their direct callers (ADR-0149) | fault 3 | assumed | prove the callback target at each wrapper call site |
| 6 | Return closure: each jr ra returns to its caller's continuation | fault 5 | assumed | prove return targets per function, including tail calls and stack-slot integrity |
| 7 | Guarded RAM data access: aligned RDRAM through KSEG0/KSEG1 or runtime-written TLB entries, no stores into code | fault 1/2/4 | assumed | prove each load and store address range |
| 8 | Jump tables are read-only | fault 2 | assumed | prove table immutability and target identity (pointer_table blockers) |
| 9 | COP1 usable with FR=0 (declared with --fr0) | **unchecked** | assumed | model Status.CU1 and Status.FR, or prove them from the game's own writes |
| 10 | COP1 stays in the modelled subset: no NaN, subnormal, out-of-range conversion or FPU exception | fault 7 | assumed | model FPU exceptions and the remaining operand classes |
| 11 | Declared loads place their bytes before the code runs | fault 8 | assumed | derive the loads from the ROM instead of declaring them by hand |
| 12 | Relocatable overlays run only where their relocated bytes verify; native frames pin each binding (ADR-0181/0187) | fault 2/3/8 | assumed | prove each overlay's load base and lifetime from the game's own loader |
| 13 | libultra runtime functions are host-provided (HLE) | **unchecked** | assumed | differential-test each HLE function against the game's own libultra; only scenario tests exist today |
| 14 | Three runtime names come only from a reference symbol map (osInitialize, osContInit, osEepromLongRead; ADR-0171) | **unchecked** | assumed | identify them from the ROM's own bytes |
| 15 | Trapping arithmetic never overflows | fault 6 | assumed | model the Overflow exception |
| 16 | BREAK is never executed | fault 9 | assumed | model the Breakpoint exception |

Inputs given by hand, outside the solver:

- Code segment ROM offset, address, size and entry point, given by hand for SM64 and OoT; inferred from the ROM for Majora's Mask and F-Zero X (boot address from the CIC, size from the entry stub's BSS clear; ADR-0183, ADR-0184)
- --loads files for executable loads, written by hand (SM64: 2, OoT: 2; Majora's Mask and F-Zero X: none). Without a file table, infer-loads finds segments from ROM ranges named in code; on SM64 it finds the engine segment but not goddard (ADR-0184)
- SM64 function identification uses a local decomp map
- Graphics use RT64 display-list HLE by default; --rsp-gfx executes compiled graphics microcode and gives its raw RDP commands to RT64 (ADR-0186)
- libultra runs as a host runtime (HLE)

<!-- assumptions:end -->

## Milestones

| # | Milestone | State |
| --- | --- | --- |
| 1 | Synthetic ROM to C to native, matching ares exactly | ✅ **done** (spike096) |
| 2 | SM64 discovery finds at least 99% of its functions | ✅ **done**: 99.03%, scored against a local decomp map (ADR-0152) |
| 3 | SM64 `CLOSED` under declared assumptions | ✅ **done**: 45,419 blocks, every assumption listed (ADR-0153..0156) |
| 4 | SM64 boots natively to its title screen | ✅ **done**, and further: gameplay at full speed, with input, saves and native audio (ADR-0159..0170) |
| 5 | Retire the assumptions one by one, then Ocarina of Time | 🟨 **in progress**: OoT `CLOSED` under the address-taken scope, first the fixed code (ADR-0175), then with all 468 overlays at their link addresses (ADR-0179/0180); boots natively through a hardware RCP I/O model and a lowered RSP task (ADR-0176/0177), runs relocated overlays through a verified binding (ADR-0181), and with RT64 draws its boot logo, title and file select (ADR-0182) |

## How it works

```mermaid
flowchart TD
  rom[Untouched ROM] --> discover["discover<br/>CFG, indirect proofs, libultra identification, declared loads"]
  discover --> solve["solve<br/>closure proof in a declared scope"]
  solve -->|OPEN| stop[blockers report]
  solve -->|CLOSED| lower["plaid-lower<br/>one C function per guest function"]
  romtexts[RSP microcode found in the ROM's images] --> rsplower["lower-rsp<br/>RSP microcode to C"]
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

Libultra system functions are declared as runtime functions and become calls into Plaid's own C runtime ([`runtime/`](runtime/), ADR-0158/0159): threads, message queues, events, timers, PI DMA, controllers, EEPROM and RSP tasks. Graphics go through [RT64](https://github.com/rt64/rt64). With `--rsp-gfx`, graphics microcode also runs as compiled native code and RT64 draws its raw RDP output (ADR-0186). Other RSP tasks, such as audio, run the game's own microcode lowered to C (ADR-0167..0169). Thread entries and other callbacks are proven per call site. How to build and run a game is in [`runtime/README.md`](runtime/README.md).

## Real ROMs

ROMs stay local and are never committed. Per-ROM numbers and how to reproduce them are in [`docs/STATUS.md`](docs/STATUS.md).

| ROM | Result |
| --- | --- |
| Super Mario 64 (USA) | 99.03% discovery recall. `CLOSED` over 45,419 blocks under a declared scope: its main, engine and goddard segments, with calls through function pointers restricted to address-taken functions. Runs natively at full speed (59.9 VI/s), with graphics, input, EEPROM saves and audio. |
| Ocarina of Time (USA 1.2) | Boot, the Yaz0-compressed `code` segment and the cartridge's 64DD driver segment: `CLOSED` over 29,542 blocks under the address-taken scope (ADR-0175). With its 468 overlays at link addresses (ADR-0172, ADR-0179), it is `CLOSED` over 154,414 blocks under the address-taken scope (ADR-0180). Natively, with RT64, its own audio microcode and SRAM saves, it runs through its relocated overlays to the title screen and file select (ADR-0181, ADR-0182). |
| Majora's Mask (USA) | No hand-written input: `scripts/native.py` infers its loads and runtime, and it is `CLOSED` with its overlays under the address-taken scope (ADR-0183). Natively with RT64 it plays the mask intro and the Clock Town attract scene, and, since ADR-0187, passes its former heap-overlay stop and runs 90 s with no fault. Audio is restored (ADR-0189). |
| F-Zero X (USA) | From the ROM alone, 27,621 blocks and zero blockers under the address-taken scope (ADR-0185). Native graphics microcode feeds RT64 raw RDP commands; visible 65-second races show vehicle markings and shading without a runtime fault (ADR-0186). |
| Mario Party 2 (USA) | Boot window: 712 blocks and 29 blockers. 27 sit behind an `osInitialize` whose SDK build n64sym lacks; 2 are function-pointer calls. |
| Banjo-Kazooie (USA) (Rev 1) | No hand input. Boot-produced images are recovered with pinned ares (ADR-0190) and 13 executable files that share one RAM slot come from the ROM's own catalog (ADR-0192): 33,796 blocks, scoped OPEN with 1 blocker, an unsupported `MFC0` Status read in `__osGetSR` at `80259d30`. It stops before lowering; native execution is unmeasured. |
| Paper Mario, Star Fox 64, Mario Kart 64, GoldenEye 007, Rogue Squadron (USA) | Surveyed with the ROM-only pipeline (with Banjo-Kazooie above, six in all): every ROM is scoped OPEN and stops before lowering, on missing executable images and loads, system instructions or unproven indirect sites. Paper Mario is down to 164 blockers (ADR-0191). No runtime was reached. See [`research/rom-sweep.md`](research/rom-sweep.md). |

<details>
<summary><b>Native runs: finding and fixing what breaks</b></summary>

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
| Audio ran 4% fast | `osAiGetLength` always read 0 | AI DMA timed as ares models it, played through SDL (ADR-0170) |

**SM64 runs natively at full speed into gameplay** (59.9 VI/s, 30 fps): RT64 draws it (ADR-0163), the keyboard or a `--press` script controls it (ADR-0164), and `--save` keeps the EEPROM (ADR-0165). Its audio comes from the game's own RSP microcode, lowered to C; on real audio tasks it matches ares in every byte (ADR-0169). It plays live through SDL, paced by a model of the AI's DMA timing, and `--wav` records it (ADR-0170). The latest run is in [`research/sm64-first-measurement.md`](research/sm64-first-measurement.md), and what comes next is in [`docs/NEXT.md`](docs/NEXT.md).

</details>

## Per-game inputs and known gaps

Nothing in the compiler or the runtime is keyed to SM64: no game names, addresses or patches. The runtime implements libultra functions by name, and RT64 draws any game's display lists. A game needs a few inputs. `scripts/native.py <rom>` runs the whole pipeline and infers the first two from the ROM alone when it has a file table (ADR-0183, as for Majora's Mask); SM64 and OoT's earlier builds declared them by hand:

- **Where its code is and what loads where**: the boot and code segments as executable loads (`plaid infer-loads`, or `--loads` by hand), with their ROM ranges and addresses. Without a file table, code-named ROM ranges and slot alternates are inferred as well (ADR-0184/0185); `--loads` supplies declarations when inference is insufficient. The native build checks their bytes when they are loaded and faults on a mismatch.
- **Which functions are libultra** (`plaid identify`): n64sym signatures, or a symbol map with `--symbols` when the game's SDK build is missing from n64sym's database. SM64 uses its decomp symbol map, which stays local. The map only names functions; it is not used to find code.
- **The assumption scope**: for example `--address-taken` and `--fr0`. Every assumption is listed in the solver's report.

Known gaps:

- Overlay binding is itself an assumption (ledger row 12), and every overlay's load base is found at run time, not proven. MM's heap-overlay stop is fixed (ADR-0187), but that is finite execution, not a lifetime proof.
- The runtime covers the libultra functions that SM64, OoT and MM call. A game that calls a declared function the runtime lacks fails to link.
- Saves are 4 Kbit EEPROM, 256 Kbit SRAM and 1 Mbit FlashRAM (no 16 Kbit EEPROM or Controller Pak). Only controller 1 works, and there is no rumble.
- RSP microcode is derived from the ROM (ADR-0188): candidate texts come from its images and SDK-style descriptors, a task selects one by a unique match on the words reachable from its entry, and every later fetch is checked against the lowered word. The candidate registry is incomplete, OoT refuses at VI 2 on a protected RSP DMA write, and `--rsp-dump` saves IMEM images only as oracle inputs. Graphics tasks use RT64 display-list HLE by default; `--rt64 --rsp-gfx` runs their compiled microcode and sends its raw RDP output to RT64. Audio plays through SDL with RT64, or goes to a WAV file.
- Only Windows has been tested with RT64.

## Build

```bash
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

The full local gate, the native differential test and reference-lab setup are in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Credits

Plaid stands on other people's work. Each project below is pinned in [`refs.lock.toml`](refs.lock.toml) and its license is checked before any reuse; reuse decisions are recorded in [`docs/DECISIONS.md`](docs/DECISIONS.md) and [`docs/SOURCES.md`](docs/SOURCES.md).

| Project | What Plaid uses it for | How | License |
| --- | --- | --- | --- |
| [Rabbitizer](https://github.com/Decompollaborate/rabbitizer) | MIPS instruction decoder used by discovery | linked dependency | MIT |
| [spimdisasm](https://github.com/Decompollaborate/spimdisasm) | disassembly experiments for call and jump-table recovery | reference | MIT |
| [n64sym](https://github.com/shygoo/n64sym) | libultra function signatures; Plaid's matching rule follows its `TestSymbol` | signatures and a reimplemented rule | MIT |
| [N64Recomp](https://github.com/N64Recomp/N64Recomp) | the model of lowering MIPS to C, and of reimplemented runtime functions | reference and design | MIT |
| [RT64](https://github.com/rt64/rt64) | renders each game's display lists | built and linked into generated games | MIT |
| [ares](https://github.com/ares-emulator/ares) | accuracy oracle for CPU and RSP semantics | differential testing only, never linked into a native build | ISC |
| [Mupen64Plus](https://github.com/mupen64plus/mupen64plus-core) | instrumented discovery reference and second oracle | research instrument in `instruments/mupen/`, separately licensed | GPL-2.0-or-later |
| [n64-systemtest](https://github.com/lemmy-64/n64-systemtest) | hardware-behaviour test programs | test inputs | MIT |
| [Gopher64](https://github.com/gopher64/gopher64), [N64ModernRuntime](https://github.com/N64Recomp/N64ModernRuntime) | cross-checks of hardware and runtime behaviour | read only; no code copied or linked | GPL-3.0 |
| [SDL](https://www.libsdl.org/) | audio output and keyboard input in the runtime | linked at run time | zlib |
| Super Mario 64 decompilation project | a locally built symbol map, used to name three libultra functions and to score discovery recall | kept local; never committed or used to find code | CC0 |

Thank you to the authors and maintainers of all of them. Super Mario 64, Ocarina of Time, Majora's Mask and Mario Party 2 are the property of their owners; Plaid is not affiliated with Nintendo.

## Disclaimer

This project is intended for interoperability, research, and preservation purposes. It does not include, distribute, or require copyrighted software, firmware, keys, or proprietary libraries. Users are responsible for obtaining and using any ROM in accordance with applicable laws.

## License

Plaid is licensed under either of [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option. The Mupen64Plus instrumentation in `instruments/mupen/` is a separately licensed GPL research instrument (see its `COPYING`) and is not part of Plaid's compiler or runtime. Reused third-party logic is credited where it is used.
