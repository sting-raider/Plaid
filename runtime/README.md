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
- **Audio tasks.** These still complete immediately.

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

## Tests

`python runtime/test_runtime.py` runs a synthetic multi-thread program and
checks libultra's scheduling order, including VI preemption of a spinning
thread. It also checks the renderer bridge against a stub, without a GPU:
the VI registers and the task addresses the runtime hands over.
