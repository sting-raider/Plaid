# SM64 US: first discovery, recall and closure measurement

Date: 2026-10-15. Measured at base 09ccdce (ADR-0148) plus ADR-0149.
Milestones 2 and 3.

## Inputs (local only, never committed)

- ROM: user-supplied Super Mario 64 (USA), sha1
  `9bef1128717f958171a4afac3ed78ee2bb4e86ce` (the verified dump), copied to
  `target/local-inputs/sm64.us.z64`.
- Oracle: the n64decomp/sm64 decomp (CC0) at
  `9921382a68bb0c865e5e45eb594d9c64db59b1af`, built in WSL Ubuntu 26.04 to a
  matching ROM (`sm64.us: OK`). Its `build/us/sm64.us.map` is copied to
  `target/local-inputs/sm64.us.map`. No decomp code is copied into Plaid.
  Getting it to build on this host took four local workarounds:
  - MIPS binutils 2.45 unpacked from `apt-get download`, since there is no
    root.
  - decompals' prebuilt IDO 5.3 recomp v1.2, since the in-tree recomp
    misbehaves under GCC 15.
  - `-std=gnu++11 -include cstdint` for armips.
  - Explicit per-level `leveldata.elf` rules with an `nm`-generated symbol
    script, because make 4.4.1 drops the target-specific `TEXTURE_BIN` during
    secondary expansion and ld 2.45 ignored `--just-symbols`.

## Commands

```
plaid identify R 0x1000 0x80246000 0xf4580 sm64.us.map --symbols > id.json
plaid discover R 0x1000 0x80246000 0xf4580 0x80246000 map.json id.json
plaid solve R map.json --guarded-ram
plaid recall map.json sm64.us.map 0x80246000 0x8033a580
```

The window is the main segment, ROM `0x1000..0xf5580` at `0x80246000`, from
the map's `_mainSegment*` symbols.

## Results

| Step | Blocks | Guarded blockers | Recall |
| --- | --- | --- | --- |
| n64sym identification (49 functions; `osInitialize` missed) | 68 | 11 | 2.0% |
| `--symbols` identification (54 functions, ADR-0148) | 13 | 1: `create_thread`'s forwarded entry | 1.9% |
| plus forwarded callbacks (ADR-0149) | **2936** | **8** | **8.1%** (245/3029) |

n64sym misses SM64's `osInitialize`: 5 variants match its crcA and none its
crcB, as on Mario Party 2. Its cache and COP0 callees then show up as 10
instruction-scope blockers.

SM64's game code is built with IDO at `-O0`. `main_func` and `thread1_idle`
create threads through `create_thread(thread, id, entry, arg, sp, pri)`,
which spills `entry` to its argument home and reloads it before calling
`osCreateThread`. ADR-0130 needs a constant at the runtime call, so
discovery stopped at the idle thread. ADR-0149 follows the forwarded
argument to each caller's constant: the idle, main, game-loop and sound
threads.

## Remaining 8 guarded blockers

- 4 targets in the **engine segment** (`0x80378800..0x8038bc90`, a raw DMA
  from ROM `0xf5580`): `vec3f_copy` and `level_script_execute` are reached
  as direct targets, plus two calls into it from the game and sound loops.
  ADR-0136 composes declared loads into one contiguous image, but the engine
  and goddard (`0x8016f000`) segments are disjoint from main. Covering them
  needs one image per segment, not a composite with BSS and heap gaps inside
  the protected image.
- 3 audio `jr` sites in `sequence_channel_process_script`,
  `sequence_player_process_sequence` and `audio_signal_game_loop_tick`. These
  are likely IDO jump tables in a shape ADR-0140 does not recognize yet.
- 1 `jalr t9` in `display_and_vsync`: the goddard vblank callback pointer,
  loaded from memory (the ADR-0142 class).

## Recall

245 of 3029 reference functions (8.1%). Most SM64 code is reached only
through data: behavior scripts, geo layouts, level scripts and the level
command table, which all hold function pointers. Milestone 2's 99% target
needs discovery roots from those data structures, and the engine segment
holds the script interpreters.
