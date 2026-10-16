# Plaid host runtime

`plaid_rt.c` is Plaid's own libultra host runtime (ADR-0158, ADR-0159), licensed
MIT OR Apache-2.0. It implements the declared runtime functions
(`plaid_rt_<name>`) that lowered code calls.

It is built as one translation unit with a lowered program that was compiled with
`PLAID_SAFEPOINTS`:

```bash
plaid lower-map <rom.z64> <map.json> <entry> <exit> game.c
gcc -O1 -std=gnu11 -DPLAID_SAFEPOINTS -DPLAID_LOWERED='"game.c"' -I . runtime/plaid_rt.c -pthread -o game
./game --rom <rom.z64> [--stop-at gfx|none] [--gfx-tasks N] [--seconds S] [--dump <addr> <words>]
```

A large program compiles faster split into parts (ADR-0174). `--parts N`
writes `game.c`, which the runtime includes, plus `game.part<k>.c` files that
hold the guest functions. Each part compiles on its own:

```bash
plaid lower-map <rom.z64> <map.json> <entry> <exit> game.c --parts 16
ls game.part*.c | xargs -P 16 -I{} gcc -O1 -std=gnu11 -DPLAID_SAFEPOINTS -c {} -o {}.o
gcc -O1 -std=gnu11 -DPLAID_SAFEPOINTS -DPLAID_LOWERED='"game.c"' -I . runtime/plaid_rt.c game.part*.c.o -pthread -o game
```

To run RSP tasks natively, add `-DPLAID_RSP -I crates/plaid-lower/src` and
link the lowered texts:

```bash
python runtime/rsp_texts.py target/debug/plaid snapshots/ texts/   # prints the C files to link
./game --rom <rom.z64> --rsp-dump snapshots/                          # saves IMEM it cannot run yet
```

## Model

- **Threads.** Guest threads run on host threads, but only the holder of a
  single baton executes guest code. A handoff swaps the CPU register file.
  Scheduling follows libultra:
  - priority order, FIFO within a priority;
  - preemption when a thread is started or woken at a higher priority;
  - a yield when a thread lowers its own priority.
- **Events.** VI retrace runs at 60 Hz. Timers, SP and DP completion, SI and
  PI are posted by host sources and delivered by the baton holder at a
  runtime call or a loop-header safepoint.
- **Guest RAM writes.** All writes go through `plaid_runtime_write`, so
  executable bytes and verified declared loads stay protected.
- **Graphics tasks.** With `-DPLAID_RT64` they go to RT64 through
  `rt64/plaid_rt64.dll` (ADR-0163), and VI registers derived from the
  `OSViMode` are presented on every retrace. Without it, graphics tasks
  complete at once.
- **Controller 1.** `--press <buttons>@<vi>:<frames>` scripts, ORed with the
  RT64 window's keyboard (ADR-0164): X/C/Z = A/B/Z, Enter = START, Q/E = L/R,
  I/K/J/L = C, W/S/A/D = D-pad, arrows = stick.
- **EEPROM.** 4 Kbit. With `--save <file>`, it is loaded at start and written
  back after every write, through `<file>.tmp` (ADR-0165).
- **RSP tasks** (ADR-0169). With `-DPLAID_RSP` and `-I crates/plaid-lower/src`,
  tasks other than graphics run lowered microcode, as libultra starts them:
  - `osSpTaskLoad` puts the task, its pointers made physical, at DMEM 0xfc0;
  - the game's boot microcode goes to IMEM 0;
  - `osSpTaskStartGo` runs from PC 0 until the RSP halts.

  IMEM is plain bytes, and DMA can rewrite it. A lowered text is a 4 KiB IMEM
  snapshot, and its code runs a word only while IMEM still holds that word.
  When control reaches a word no linked text holds, the runtime fails closed.
  With `--rsp-dump <dir>` it saves that IMEM as a new snapshot first.
  `runtime/rsp_texts.py` lowers the snapshots and writes the registry, so the
  next build runs further. RSP DMA into RDRAM passes the same write checks as
  the CPU's runtime writes. `--rsp-capture <n> <dir>` saves the state before
  and after the n-th RSP task, for the ares comparison in
  `spikes/098-rsp-task`. Without `PLAID_RSP`, these tasks complete at once.
- **RCP I/O** (ADR-0177). Uncached CPU words in SP DMEM/IMEM and the PI
  registers and bus behave as pinned ares:
  - DMEM starts with ROM 0x40..0xfff;
  - `PI_STATUS` reads idle and the domain timing registers latch;
  - the ROM reads as itself and the absent 64DD reads as open bus.

  After a task whose microcode did not run, SP memory is unknown and reads
  fail closed. Other devices, register DMA and cached access fault.
- **Audio out** (ADR-0170). The AI is modelled as ares models it:
  - a two-buffer DMA FIFO drains one sample per DAC period on the host
    clock, at the rate `osAiSetFrequency` set from the NTSC VI clock;
  - `osAiGetLength` and `osAiGetStatus` report what the hardware would;
  - a third buffer is refused;
  - each buffer start raises the AI event.

  So a game paces its own audio as on hardware. With RT64, each buffer also
  plays through SDL. `--wav <file>` writes the buffers as 16-bit stereo PCM.

## Rendering with RT64

`rt64/` wraps RT64 (pinned in `refs.lock.toml`, with submodules) in a C ABI
DLL. On Windows, build it with MSVC. D3D12 headers newer than Windows SDK
22621 are needed: [DirectX-Headers](https://github.com/microsoft/DirectX-Headers)
(MIT) placed ahead of the SDK works.

```bash
cmake -S runtime/rt64 -B target/rt64-shim -G "Visual Studio 17 2022" -A x64 -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES="<DirectX-Headers>/include/directx;<DirectX-Headers>/include"
cmake --build target/rt64-shim --config Release --target plaid_rt64
gcc -O1 -std=gnu11 -DPLAID_SAFEPOINTS -DPLAID_RT64 -DPLAID_LOWERED='"game.c"' -I . -c runtime/plaid_rt.c -o game.o
gcc game.o target/rt64-shim/Release/plaid_rt64.dll -pthread -o target/rt64-shim/Release/game.exe
```

The executable must sit next to `plaid_rt64.dll`, `SDL2.dll`,
`dxcompiler.dll` and `dxil.dll`; the build copies those DLLs there.

### Native graphics microcode

`python scripts/native.py <rom> --rt64 --rsp-gfx` runs graphics tasks through
the same native RSP snapshot pipeline as audio (ADR-0186). It renders the
microcode's raw RDP output with RT64, including DMEM command buffers and lists
split across submissions. This handles graphics microcode variants that RT64's
display-list HLE does not implement. There is no runtime instruction interpreter
or JIT; missing microcode still stops the executable and is lowered before the
next build.

The script runs each game validation visibly, accepts `--press` for scripted
controller input, and writes a `Play <name> native RSP.cmd` launcher beside the
window executable. The launcher supplies the ROM and save paths and has no time
limit or automated input. The earlier HLE executable has a separate filename.
Objects are cached by source, headers, flags and compiler identity; a failed
rebuild cannot mark an old object current. `python scripts/test_native.py`
checks dependency invalidation and failed builds.

DPC commands complete synchronously. Unknown ranges fault, and the native RSP
word guards remain active. Snapshot collection is finite execution coverage,
not a proof that every graphics microcode overlay has been found. A new mode
can still stop at an unlowered snapshot; rebuild through the same pipeline.

## Tests

`python runtime/test_runtime.py` runs a synthetic multi-thread program and
checks libultra's scheduling order, including VI preemption of a spinning
thread. It also checks the renderer bridge against a stub, without a GPU:
the VI registers and the task addresses the runtime hands over. It also
checks controller input, an EEPROM save kept across two runs, and an RSP
task run through the snapshot protocol: two runs save the boot and ucode
snapshots, and the third runs the task natively and checks its RDRAM output
and the SP event.

The native graphics contract uses a renderer stub and synthetic microcode to
check CPU/RSP shared DPC registers, freeze/resume, DMEM wrap, RDRAM command bytes,
CPU memory visibility and readable SP memory after a native task. Raw handle PI
DMA is tested through the o32 ABI, including its stack argument, bounds and
refused cartridge writes. `plaid_rt64_contract`, run by the renderer build,
checks empty vertical tile loads and split raw commands without a GPU or ROM.

It also checks AI DMA against a host-audio stub:
- the FIFO refuses a third buffer;
- the status bits are right;
- the second buffer starts one buffer of DAC time after the first;
- the WAV file and the host get the right samples.
