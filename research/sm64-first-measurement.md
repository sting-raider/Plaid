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
| plus forwarded callbacks (ADR-0149) | 2936 | 8 | 8.1% (245/3029) |
| plus engine and goddard loads (ADR-0150) | 5337 | 12 | 11.4% (435/3832, whole map) |
| plus IDO slot-bound tables (ADR-0151) | 5580 | 10 | 11.5% (442/3832) |
| plus `--data-roots` (ADR-0152) | **47976** | 227 (rooted code) | **99.03%** (3795/3832) |

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

## Update: disjoint loads (ADR-0150)

`sm64-loads.json` declares two raw loads:
- the engine segment, ROM `0xf5580` to `0x80378800`, `0x13490` bytes
  (`load_engine_code_segment`);
- goddard, ROM `0x21f4c0` to `0x8016f000`, `0x4a9e0` bytes (the intro and
  menu `FIXED_LOAD`).

Run it with `plaid identify ... --symbols --loads` and `plaid discover ...
--loads`. Discovery reaches 5337 blocks and 515 indirect sites.

The 12 guarded blockers are all calls through function pointers loaded from
memory:
- 5 in `render_game` and 2 in `geo_process_held_object` (geo node and render
  callbacks);
- `level_script_execute+0x54`, which calls through the level command table;
- the 3 audio dispatches;
- the goddard vblank callback.

Recall is 11.4% over all segments (3832 reference functions) and 13.6% over
the main segment alone.

## Update: milestone 2 met (ADR-0152)

`plaid discover ... --loads sm64-loads.json --data-roots`, followed by
`plaid recall map.json sm64.us.map`, gives 3795 of 3832 functions (99.03%,
`meets_target: true`).

| Roots added | Recall | Not in reference |
| --- | --- | --- |
| ROM data words | 78.1% | 1625 |
| plus code `lui`/`addiu` constants | 88.8% | 1636 |
| plus the layout pass, excluding dead `jr ra` epilogues | 99.03% | 1760 |

The "not in reference" count is mostly `static` functions (502 are direct
call targets) and jump-table case labels, which recall counts through map
entries. The layout pass contributes 124 of them.

## Update: address-taken dispatch scope (ADR-0153)

```
plaid discover R 0x1000 0x80246000 0xf4580 0x80246000 map.json id.json --loads sm64-loads.json --address-taken
plaid solve R map.json --address-taken
```

Discovery reaches 42856 blocks, 4171 indirect sites and 1313 address-taken
functions. It takes about 9 minutes in a release build.

| Scope | Blockers |
| --- | --- |
| guarded RAM | 120 (100 indirect sites) |
| guarded RAM plus address-taken dispatch | **32** |

The 32 remaining blockers:
- 12 `jr` sites:
  - 11 goddard `switch` tables (`gd_get_colour`, `make_object`,
    `proc_dynlist`, `gd_printf` and others) where a load-delay `nop` sits
    between the table `lw` and the `jr`;
  - the `audio_signal_game_loop_tick` table.
- 18 TLB/COP0 instructions in `osMapTLB` and `osUnmapTLBAll`, reached from
  goddard's `load_dynlist`. Neither is a declared runtime function yet.
- 2 from a junk root that branches into `rspF3DBootStart` and to
  `0x84001068`.

Rejecting COP2 bodies and counting only constants inside decoded blocks
removed the earlier `eret` (`__osException`, taken as a constant inside
`osInitialize`) and most of the RSP microcode impostor.

## Update: goddard tables, TLB functions, in-image bodies (ADR-0154, ADR-0155)

Re-running `identify --symbols --loads` now names 56 runtime functions,
adding `osMapTLB` and `osUnmapTLBAll`. Discovery with `--address-taken`
reaches 45388 blocks, 4385 indirect sites and 1341 address-taken functions
(12 minutes, release build).

| Scope | Blockers |
| --- | --- |
| guarded RAM | 92, all register calls |
| guarded RAM plus address-taken dispatch | **1** |

The last blocker is `audio_signal_game_loop_tick+0x4e0`:
`sltiu at, s4, 10` is followed by a taken `bnez t9` to `beqz at` (whose slot
is the scale), and then the dispatch block. The bound's interval crosses a
branch, so the linear walk in ADR-0140 stops.

Recall on this map is 90.2%. It has no layout pass; the milestone 2 figure
is measured with `--data-roots`.

## Update: milestone 3 met (ADR-0156)

With the table bound walked across the `bnez` into the guard, `plaid solve
R map.json --address-taken` reports **`status: closed`**, with no blockers
and `native_complete: false`. Discovery has 45419 blocks, 4385 indirect
sites and 1341 address-taken functions. The guarded scope, without
address-taken dispatch, has 91 blockers, all register calls.

The report lists 14 assumptions. Each native-checked one names its fault
code; the execution-source exclusions and the runtime ABI of the 56 declared
functions are declared rather than checked.

## Update: lowered to C and run to the first thread (ADR-0157)

```
plaid lower-map R map.json 0x80246000 0x80000000 sm64.c
gcc -O0 -std=c99 -c sm64.c
```

- `lower-map`: 45419 blocks in 47 s, giving a 47 MB C file.
- gcc 15 `-O0`: 58 s, giving a 28.8 MB object. It printed no errors.

A local harness (not committed) defines the 56 `plaid_rt_*` functions as
stubs. `osInitialize` returns to its caller; every other stub prints its
arguments and stops the run. Run natively, it prints:

```
runtime osInitialize (stub, returns)
runtime osCreateThread at ra=80246384 a0=8033a730 a1=00000001 a2=80246cf0
```

That is `create_thread(&gIdleThread, 1, thread1_idle, ...)` in `main_func`,
with addresses as in the decomp map. Continuing needs a host thread
scheduler and the rest of the libultra runtime.
