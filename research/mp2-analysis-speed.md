# Mario Party 2 (USA) analysis speed — receipts

Cluster: MP2 (USA) `infer-loads`/`discover`/`solve` analysis time.
Branch: `oc/step5-mp2-speed` (direct-integration worker, exact-head CAS).
Host: Windows, native only (ADR-0295), 20 hardware threads, gcc 15.2, rustc 1.99.1.

The task kept two WIP commits from `oc/mp2-analysis-speed`:

- `34d56c4d` "Record per-phase pipeline wall times" — `scripts/native.py` times each
  pipeline phase and prints them in pipeline order, marking phases restored from the
  analysis memo cache. Diagnostic only; outputs unchanged.
- `bd693255` "WIP: MP2 analysis timing" — an env-gated `PLAID_PHASE_TIMINGS=1`
  diagnostic in `plaid-core` (`crate::timing`) that reports per-stage wall times inside
  the Rust analysis (`discover.*`, `address-taken.*`). The variable changes neither the
  map bytes, the stdout report, nor any decision, so a timed run and an untimed run of
  the same inputs stay byte-identical. This is measurement scaffolding, not production
  behavior.

Both are kept: they are correct, general, and the only way to attribute a slow phase
without re-profiling the whole pipeline.

## Before: per-phase pipeline wall times

`python scripts/native.py <MP2 rom> --name mp2-baseline --seconds 30` with
`PLAID_PHASE_TIMINGS=1`, from an empty output directory (cold; no memo restores):

```
timings: total 981.524 s
timings:   build                0.137 s
timings:   rom-info             0.047 s
timings:   infer-loads          0.109 s
timings:   harvest-vectors      0.000 s
timings:   identify             0.343 s
timings:   discover           135.167 s
timings:   partition            0.001 s
timings:   solve               11.454 s
timings:   infer-call-loads     1.261 s
timings:   harvest              4.230 s
timings:   harvest-vectors      0.013 s
timings:   identify             0.953 s
timings:   discover           134.066 s
timings:   partition            0.001 s
timings:   solve               11.704 s
timings:   infer-call-loads     1.626 s
timings:   harvest              6.407 s
timings:   residual-solve      11.342 s
timings:   boot-state           0.193 s
timings:   rsp-from-rom        52.939 s
timings:   lower               23.242 s
timings:   gcc                508.564 s
timings:   gcc-runtime          1.427 s
timings:   gcc-rsp             45.378 s
timings:   link                 0.768 s
timings:   validation           30.152 s
```

`discover` runs twice because `solve` reports OPEN and `infer-call-loads` changed nothing,
so the refinement loop re-runs discovery against the same inputs — the same 135 s of work
is repeated to produce the same map. Validation reached VI 1798, fault 0.

The `plaid-timing` breakdown of one 135 s `discover` invocation:

```
plaid-timing: discover.overlay-catalog 0.024 s
plaid-timing: discover.compose 0.051 s
plaid-timing: address-taken.rom-words 1.590 s
plaid-timing: address-taken.image-words 1.066 s
plaid-timing: discover.rounds count=5
plaid-timing: discover.cfg 6.358 s
plaid-timing: discover.indirect 10.600 s
plaid-timing: discover.fixed-point 22.248 s
...
plaid-timing: address-taken.returns 5.637 s
plaid-timing: address-taken.rounds count=6
plaid-timing: address-taken.total 128.796 s
plaid-timing: discover.slot-root-rounds count=1
plaid-timing: discover.slot-roots 0.021 s
plaid-timing: discover.serialize 0.856 s
```
(157061 blocks, 8267 indirect sites, 997 unresolved items.)

## Before: analysis artifact hashes

Produced by the baseline run above:

| artifact | sha256 |
| --- | --- |
| `map.json` | `4e4709eaf5ee5476b92c61825acf9abd7c363187f017a0b67065f9ec15339751` |
| `id.json` | `22bc25d4d0b9796a82675fe25e15a596927ee300f8039265fe97f1a5c075bf5c` |
| `loads.json` | `05141f50814a21411cd062bb43dafca7d6061db24882859e2634c947d5adb070` |
| generated CPU C | `099b63edf3d67beed846a2ff4edc238ab38364ac87d0de1a4cec22ff2a8005a9` |
| generated runtime header | `0d06a8ca5ab098bba6346d6ad37b0872871beb697ecf4feab88dac77a2f8a219` |
| `native-manifest.json` | `75d7ce03b433d25c2326437a6724c2638d8f17420f84f23bb96270d0fbbacb8a` |

The 116 overlay loads and the composed image identity
(`ca91a16e27d4cba32c0e30e83e8f206f90c75cce1c5534d4ebeeae63ffec7c91`) are structural
inputs to those hashes.

## The bottleneck

Instrumenting `analyze_indirect` per stage (ADR-0307) attributed one 136 s `discover`
invocation as follows: 17 `analyze_indirect` passes totalling ~38.7 s, of which
`tables::analyze` 14.3 s and `tail_cells::analyze` 11.3 s — i.e. both table-proof
passes, not the direct-CFG decode. Each of them did a **linear scan over the entire
block list** for a question the sorted block index already answers:

- `tables::analyze`, for every indirect site without a fresh table certificate, asked
  whether any decoded block overlapped the candidate table's byte range by iterating
  all 157061 blocks (`index.source().blocks.iter().any(..)`).
- `tables::evidence` asked the same overlap question about a recognized table, again
  over all blocks.
- `tail_cells`' recheck asked, per certificate target, whether any decoded block
  started at that address — also over all blocks.

These are O(blocks) per question, executed per site per target per fixed-point round.
`MapIndex` had just built a per-image block list **sorted by start with the largest
size beside it**, so both questions are a bounded scan / binary search away.

## The fix

`MapIndex` gained two indexed predicates over that sorted list, both with semantics
identical to the linear forms they replace:

- `decoded_overlaps(image, generation, start, end)` — bounded scan from the first
  block whose start can still reach `start`.
- `starts_block(target)` — binary search for a non-delay-slot block at that address.

`tables` now uses `decoded_overlaps` at both sites and the tail-cell mapped-target
test uses `starts_block`. Nothing else changed: no predicate, input, ordering or
evidence identity. Five Rust tests cover each indexed form against its linear
reference over every aligned start/count pair and every block-start address, plus
generation, image and empty-range refusals.

## After: byte-identical artifacts and faster phases

Every output is unchanged. `map.json` is still
`4e4709eaf5ee5476b92c61825acf9abd7c363187f017a0b67065f9ec15339751`, the generated CPU C
is still `099b63edf3d67beed846a2ff4edc238ab38364ac87d0de1a4cec22ff2a8005a9`, and
`id.json`/`loads.json`/`runtime.h`/`native-manifest.json` are likewise unchanged.

End-to-end pipeline wall times, `scripts/native.py --rt64 --seconds 30` before vs
after (same ROM, same output-name convention, cold output directory):

| phase | before | after |
| --- | --- | --- |
| discover (1st) | 135.167 s | 54.346 s |
| discover (2nd) | 134.066 s | 57.016 s |
| solve (ordinary) | 11.454 s | 4.572 s |
| solve (2nd) | 11.704 s | 4.899 s |
| residual-solve | 11.342 s | 4.911 s |
| **analysis phases total** | **269.2 s** | **111.4 s** |
| pipeline total | 981.524 s | 489.619 s |

The two `discover` runs are the same work repeated because `infer-call-loads` changes
nothing, so its cost dominates the analysis total; it is now less than half.

### Contention-controlled discover measurement

Wall time on this shared host (chrome/Discord/Taskmgr active) swings 2x for the same
binary, so the comparison above is confirmed with process `TotalProcessorTime`, which
counts work rather than idle. Five runs each of the discover command
(`plaid discover <rom> 0x1000 2147484672 0xd47f0 2147484672 <map> <id>
--loads <loads> --address-taken --fr0 --overlays`), medians:

| stage | before | after |
| --- | --- | --- |
| discover process total CPU | 79.8 s | 57.8 s |
| address-taken total | 54.33 s | 50.18 s |
| address-taken.returns | 2.56 s | 1.17 s |
| discover.cfg | 12.12 s | 11.94 s |
| discover.indirect | 20.51 s | 18.71 s |
| address-taken.block-constants | 3.12 s | 2.87 s |
| address-taken.pointer-roots | 0.84 s | 0.77 s |

`TotalProcessorTime` sums every thread, so a multi-threaded phase reads higher than
its wall time; the comparison is only valid between equal configurations. All runs of
both configurations produced the same `map.json` hash.

## Controls

Six silent 30 s `--rt64` controls (`SDL_AUDIODRIVER=dummy`), each at about 1798 VIs
with fault 0 / fault_pc 00000000:

| ROM | VI | fault | gfx | audio | PI DMA |
| --- | --- | --- | --- | --- | --- |
| Paper Mario | 1797 | 0 | 1784 | 1794 | 11254 |
| Banjo-Kazooie | 1795 | 0 | 583 | 887 | 1011 |
| Majora's Mask | 1798 | 0 | 662 | 1759 | 4395 |
| Star Fox 64 | 1796 | 0 | 896 | 1653 | 4689 |
| Ocarina of Time | 1777 | 0 | 604 | 1421 | 5306 |
| Rogue Squadron | 1795 | 0 | 692 | 1424 | 3096 |

MP2 with the required press list, 45 s `--rt64`: VI 2667, gfx 3876, audio 2657,
PI DMA 3406, framebuffer `00360280`, fault 0, fault_pc 00000000 — the
destination/rules prompt.

## Local gate on the exact tree

```
cargo fmt --all -- --check                              OK
cargo clippy --locked --workspace --all-targets -D warnings   OK
cargo test --locked --workspace                         OK (936 plaid-core, 553 plaid-lower)
python scripts/test_cli.py                              OK
python runtime/test_runtime.py                          OK
python tools/progress.py --check                        OK
```

## Environment note

This worktree started without the shared junctions (`.refs`, `target/rt64-shim`,
`target/native-slice`) that other worktrees carry. They were re-created as junctions into
the existing `X:\Plaid` locations (no `refs.lock.toml` pins were re-fetched):

```
mklink /J .refs X:\Plaid\.refs
mklink /J target\rt64-shim X:\Plaid\target\rt64-shim
mklink /J target\native-slice X:\Plaid\target\native-slice
```

`target/native-cache` was empty before the baseline, so the baseline measured cold
analysis work and did not restore memoized results.
