# Scissored RT64 fill clears (ADR-0266)

Worker: sf64-border-491e64b1. Prepared against main
`4c89bd7406dcabf4372f514892be246fc42a5092`, on `t3/sf64-border`.
The integrator-owned root README is unchanged. No child agents were used.

## Root cause and discriminating evidence

Three hypotheses were tested: incorrect VI/overscan translation; a missing
shim build patch; and incorrect RDP framebuffer writes. The last is the
cause. This is a defect in pinned RT64's fill-clear optimization, rather
than a game-specific border policy.

RT64's `FramebufferRenderer::addFramebuffer` converts fill-cycle commands
into `InstanceDrawCall::FillRect`. `submitRasterScene` implements these with
GPU `clearColor`/`clearDepth` calls. GPU clears do not use the rasterizer's
scissor state; the original path passed the entire fill rectangle without
intersecting the draw call's scissor. Rasterized triangles use that scissor.

The intro generates legitimate one-pixel star commands outside its inset
scissor. An observed example has 10.2 coordinates `(20,236):(20,236)`,
scissor `(32,32):(1248,928)`, fill color `294b294b`, fill cycle `00382c20`.
Other stars lie above, below and to the right. The inset black clear cannot
erase leaked border stars, so they accumulate over successive buffered
frames. The visible result resembles tiled glyphs, but these are accumulated
star fills, not an uploaded glyph texture.

The unmodified shader path's completed readback already contains the bad
pixels. On the first framebuffer, its left border is entirely `0001` before
intro task 94; afterward 11 pixels are colored. By task 310, 717 of the
sampled 1,776 border pixels are colored. VI-only cropping cannot explain
those guest RAM changes. Earlier MIO0 scratch DMA at the first framebuffer
is cleared before the intro; it is not the accumulating corruption.
Observation sources, task snapshots, edge-fill log and RAM conversions stay
under ignored `target/receipts/sf64-border/`.

References were read at their declared pins:

- RT64 `43373749dac9bbc1b653e6a02aed40a9e1783bed`,
  `src/render/rt64_framebuffer_renderer.cpp`, fill-call construction and
  submission; `src/hle/rt64_rdp.cpp`, fill/scissor tracking.
- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`,
  `ares/n64/vulkan/parallel-rdp/parallel-rdp/rdp_device.cpp`,
  `op_fill_rectangle`, and `rdp_renderer.cpp`, primitive/scissor clipping.
  This is source-level reference evidence, not a claimed full-game ares
  screenshot comparison. No reference implementation was copied.

## General correction and regression

The generated renderer build copy converts fill and scissor bounds into
render-target coordinates using each one's alignment origins, intersects
the bounds, and marks an empty intersection as an Unknown/no-op instance.
Keeping the instance preserves draw-call indices. Color and depth clears
share this path. It adds no game addresses, border constants, runtime guest
decoder, VI masking or fallback execution.

`runtime/rt64/test_scissor.py` sends synthetic raw RDP lists through the
actual built DLL. A 64 by 48 framebuffer has an inset scissor and white
fills against black. The test checks every pixel for RGBA16 and RGBA32:
interior fills, four disjoint sides, four partial overlaps, a covering fill,
four touching edges and horizontal/vertical zero-area scissors. Corner
writes with a full scissor force complete framebuffer readback. No ROM,
microcode, captured game commands or external Python package is needed.

The old DLL fails at the left-outside case: pixel `(1,12)` is `ffff`,
expected `0001`. Removing only the new left-bound `std::max` guard in the
generated build copy produces the same failure. The guard was restored,
the shim rebuilt, and all cases pass. The CMake/CTest entry invokes the
test in a child process so its detached renderer is never unloaded live.
Every test window is visible and `SDL_AUDIODRIVER=dummy` is set before rendering.

The contract is bounded to integer-coordinate color cases. It does not
certify subpixel or field scissors, unequal fill-word halves, VI coverage,
filtering, or complete depth accuracy. Whole-row native readback can also
requantize pixels not written by the primitive; the random-color probe
exposed that existing issue, but it is separate from the border-star leak.

## Rebuilding the shim correctly

The shared rebuilt shim already compiled Plaid's two pre-existing patches:
both patched units are listed in its generated `rt64.vcxproj`, including
the tile-load and readback hooks. A fresh original shim built in this
worktree reproduces the defect. There is no evidence that the rebuild
skipped those patches, or that it caused the historical onset.

Configure from Plaid's shim project, not directly from RT64. After this
change the generated RT64 target must compile all three build copies:
`rt64_rdp.cpp`, `rt64_state.cpp`, `rt64_framebuffer_renderer.cpp`.
The original reference checkout remains unchanged. The local commands are:

```powershell
cmake -S runtime/rt64 -B target/rt64-shim -G "Visual Studio 17 2022" -A x64 "-DCMAKE_POLICY_VERSION_MINIMUM=3.5" "-DCMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES=X:/Plaid/target/directx-headers/include/directx;X:/Plaid/target/directx-headers/include"
cmake --build target/rt64-shim --config Release --target plaid_rt64 -j 8
ctest --test-dir target/rt64-shim -C Release --output-on-failure
```

`.refs` here is a junction to the existing pinned `X:/Plaid/.refs` and was
never refetched or modified. The build directory and rebuilt DLL belong to
this worktree. No junction was recursively deleted and no shared shim was
rebuilt. The game's executable must use the rebuilt DLL and its accompanying
SDL/DXC DLLs. Rebuilding native game objects alone does not update the shim.

## Captures, controls and local gate

All game images, ROMs, RAM and renderer-input captures are ignored local
artifacts under `target/receipts/sf64-border/`; no game assets enter git.
The complete command drivers and machine-readable receipts live there.
Results and exact-tree validation are detailed below.

### Same-input VI 600 comparison

An observation-only current native runtime records the renderer's CPU word
changes, task arguments and VI presentations, separating CPU writes from
completed renderer readbacks. Initial VI state is retained from the
per-retrace log. The replay is analysis-only and is not linked into the game
or used as a compiler input. A native C driver replays this same stream
against the original and corrected DLLs, including a one-second presentation
settling wait before capturing the visible client. Audio is dummy throughout.
The earlier Python HLE replay helper crashed despite identical initial RAM;
it is not used for acceptance. The native C replay completes both variants.

Both variants finish at VI 600 / 308 graphics tasks, origin `0038fa80`, width
320. All 14 VI register values agree, including H/V video `006c02ec` /
`002501ff` and X/Y scale `200` / `400`. Input SHA-256:
`ccf3ad08e0ed276bd8d50a81ce7b331ddbcf05909ffb310f55d6d53aaac1a611`.
The interior `[8,312) x [8,232)` is byte-identical in the two read-back
framebuffers. Exactly 1,318 border pixels change; every final border pixel
is opaque black `0001`. The same text and starfield appear in both displayed
frames; the accumulated border stars are gone.

Local screenshots and RAM-derived views, intentionally ignored by git:

- Before: `target/receipts/sf64-border/replay-before/vi-600.png` and
  `sf64-screen-vi-600.bmp`; BMP SHA-256
  `75847866cc2f56e01260c992d39c2b26d816ff14b208c9d5b72fb40afab550f1`.
- After: `target/receipts/sf64-border/replay-after/vi-600.png` and
  `sf64-screen-vi-600.bmp`; BMP SHA-256
  `e26051612ad03c2cfd8ba8e5684d71c8718376e45cecd68912b3720c11fdd564`.
- Each directory also contains `framebuffer.png`, the complete captured
  readback RAM and its replay log. `same-frame.json` checks input/register
  identity, interior equality and the clean border.

Before/after replay wall times are 13.346 / 13.337 s, including 600 paced
presentations, setup and the settling wait. This is the same-input iteration
receipt, not evidence for a general FPS speedup. The controls reuse CPU/RSP
objects only after source-identity checks; generated RSP object reuse takes
0.024 s for SF64 and 1.841 s for OoT (five rebuilt, 40 reused), avoiding
unnecessary whole-game recompilation.

### Six current-tree controls

All use visible RT64 windows, `SDL_AUDIODRIVER=dummy` and a 30-second limit.
The current compiler regenerates CPU main/part sources and asserts byte
identity before borrowing old CPU objects. ROM-only RSP registries are
regenerated, and current runtime objects are compiled. Game commands and
logs are retained by `controls.py`, `control-*/`, `controls-final.json` and
`mp2-repeat.log` in the ignored receipt directory.

| Game | VI | Fault | Fault PC | Build seconds |
| --- | ---: | ---: | --- | ---: |
| Paper Mario | 1764 | 0 | `00000000` | 27.811 |
| Mario Party 2, quiet repeat | 8 | 8 | `80102800` | reused current build |
| Banjo-Kazooie | 1768 | 0 | `00000000` | 15.814 |
| Majora's Mask | 1768 | 0 | `00000000` | 121.772 |
| Star Fox 64 | 1766 | 0 | `00000000` | 15.628 |
| Ocarina of Time | 1767 | 0 | `00000000` | 86.531 |

MP2 preserves the known refusal, with audio tasks 3 / PI DMA 17. An initial
run during compilation stopped at VI 11 with the same fault/PC; the quiet
repeat above exactly matches the required VI 8. The other five complete
their time limits. These are finite fault/control-flow checks, not a full
gameplay or pacing certification.

BK's VI 600 Rareware-logo image was also visually inspected: clean left,
right and bottom edges, with ordinary black pillarboxing and no glyph-like
garbage. Local image `control-bk/bk-screen-vi-600.bmp`, SHA-256
`0f0bd0434beefcf1e3a38e68ef025dd5322bc1e753437f5ca9782fca356f3ca5`.

### Frozen-tree gate and integration protocol

`target/receipts/sf64-border/gate.py` records the exact staged tree and
base SHA in `final-gate.json`. It asserts both an unchanged index tree and
no unstaged tracked changes before and after every command, preserving
individual exit codes, durations and full logs. The required commands are:

```text
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

The same gate configures/rebuilds the shim and runs its registered CTest
GPU contract before those commands. The preliminary workspace run has
939 passing tests and one pre-existing ignored test. Canonical integration
requires every final gate exit code to be zero, a fresh fetch with unchanged
base SHA, a direct-child commit, `git merge-base --is-ancestor origin/main
HEAD`, and a plain `git push origin HEAD:main`. The ignored integration
receipt and issue #4 closeout record the resulting SHA; no force option,
CI substitute, ROM, game screenshot or extracted asset enters git.

Remaining: MP2's existing overlay refusal, full gameplay comparisons,
fractional/field scissor semantics, VI filtering/coverage and the separate
whole-row readback requantization issue described above. Root-cause and
acceptance claims here are limited to the reproduced fill-scissor defect.
