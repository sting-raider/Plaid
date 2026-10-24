# OoT save-load RSP boot discovery (ADR-0265)

Prepared by oot-jpeg-boot-433319a6; recovered and validated by
oot-jpeg-boot-5efbebb9 in the independently bound worktree. Prepared base:
`588bd51cb3f9d70d20e75ea15ae3fffea85847bd`.

## Hypothesis and reference result

The save-load refusal may be a legitimate boot replacement missing from the
ROM-derived registry, or a native corruption. The first task supplies a tight
discriminator: replay exactly its pre-task RSP state in pinned ares, compare
all memory and architectural state, then inspect its boot buffer.

Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, interpreter enabled
and recompilers disabled, executes the protection task in 268 instructions.
All 8 MiB RDRAM, 4 KiB IMEM, 4 KiB DMEM, scalar/vector registers, flags,
signals, semaphore, halted and broken state match native execution. The
boot prefix changes from `08000411 8c11ffc4` to `08000439 8c11ffc4` in both.
Only byte `0x65c3` changes within the boot; the rest is unchanged. This is
the legitimate-rewrite branch, not a native CPU/runtime corruption.

The source doubleword appears at original boot IMEM `0xd0` (ROM `0x7290`).
It is DMA-written to OSTask.ucode_boot by the protection code. The entire
boot is not copied from ROM `0x7290`; its original body remains in place.
The replacement jump skips protection on later tasks.

Local ignored evidence: `target/receipts/oot-jpeg/first-task/`,
`oracle-task-repeat.log` and `oracle_task.py`. The driver is the existing
project-owned spike098 task oracle, built against the exact clean pin.
These are local task captures, not inputs to production discovery/lowering.
No reference implementation code is copied into the native runtime.

## Implementation and deterministic checks

Boot path analysis tracks task-field provenance independently of constants.
An SP_WR_LEN DMA from available, bounded IMEM bytes to OSTask.ucode_boot
supplies a prefix composition. DMEM sources, row/skip DMA, unknown bases,
wrong fields, clobbers, zero-register writes and unavailable/wrapping bytes
are refused. The recognized text-load DMA ends that path. The generator
lowers original and composed candidates; startup ambiguity and per-word
fetch checks are retained. These are candidates, not an executable-universe
certificate. No snapshot is a production build input.

The second content filter follows direct startup control flow to RSP
operations beyond scalar prologues. It requires all visited words to lower,
no direct exit and two reachable RSP operations. It permits guarded indirect
returns. The synthetic test calls a DMA subroutine beyond the former prefix;
invalid instructions, missing operations, out-of-range targets, short texts
and unreachable RSP-looking bytes fail. Existing strict short-program and
prefix filters remain intact.

The OoT registry changes from 41 to 44 texts: two self-DMA boot compositions
and NJPEG. The NJPEG pointer was already rooted; its instructions failed the
old prefix filter. Its 3,968 emitted bytes match the submitted task's RDRAM
exactly and come from the ROM's declared Yaz0 image.

The composed boot first exposed RSP fault 4 at IMEM 0xe4: its DPC_CLOCK read
had no bus outside --rsp-gfx. SDK task submission now installs a callback to
the CPU's existing DPC model. A constant zero DPC clock then sent the boot
through an eight-byte DMA to RAM zero. A full-task differential detected
those eight bytes; an advancing shared clock fixes the mismatch. Pinned
rdp/rdp.cpp adds system frequency / 3 to command.clock; io.cpp reads 24 bits
and resets on DPC_STATUS bit 9. Runtime time is elapsed nanoseconds / 16,
modulo 24 bits, with the same time model as its existing VI/AI/Count events.
This is not a new claim of cycle-accurate RDP scheduling. Busy counters and
synchronous HLE command consumption retain their existing limits.

The entire captured NJPEG task now matches the clean pinned ares interpreter:
9,668 instructions, final RSP PC 0xafc, identical RDRAM/IMEM/DMEM, GPRs,
vectors/accumulators/flags, signals, semaphore, interrupt-on-break, halted
and broken state. The protection task's final RSP PC is 0x90; its same
shared architectural fields match too. The task oracle does not run the
whole game or reconstruct prior RDP timing; these are declared task-level
comparisons from local pre-task captures and the oracle's idle DP context.

After-state SHA-256 for the NJPEG comparison:

- RDRAM: 37c45fe67d80f02cef2c03008a11bdf6f345d8600fba4112566e0f81064d9bf5
- IMEM: 9f0c936c7030a91142db9f9e7d39bd423bde63804ef12f2cf4e6f9ca276193e4
- DMEM: 54c77331b86103fb7e55dfb10d79143d1f6c9757aceba5b9bc435ca2231f8d1b

Local full captures/hashes: oot-jpeg-clock-verify-task/, task-hashes.json,
njpeg-clock-diff.log under target/receipts/oot-jpeg. The native task capture
is produced with --rsp-capture, using observation-only type-4 selection in
a local runtime copy. The production runtime has no such selection.

Tests: four core rsp_rom tests and seven lower rsp_rom tests pass. The new
non-graphics DPC contract checks shared CPU register state, a running bounded
clock, idle busy counters, RSP writes and DMA-visible output. It fails on the
previous disconnected bus at RSP PC 0. DPC helper tests cover frequency,
sub-tick rounding and 24-bit wrap. Returning no self-DMA candidates makes the
positive recognizer test fail. Mutating the SP_WR_LEN destination provenance
guard to accept any known task pointer makes the wrong-field negative test
fail (8c02ffd0); the guard is restored. Full runtime tests retain graphics,
SP-event ordering, refusal, overlay, cache and architectural-state contracts.

## Native continuation and pacing

Baseline with the requested five presses and a copied local SRAM reaches
VI 1853 and refuses the 352-byte boot with zero matches (CPU fault 0,
fault_pc 00000000, return address 800a3760). A separate initial menu-timing
run reached the same refusal at VI 2846; timing and save state must accompany
VI counts. The accepted save-load task is type 4 with the user's reported
boot/text/data pointers and sizes.

An initial visible diagnostic reaches the opening cutscene at VI 3256,
fault 0, after 60 seconds. Its local VI 3000 image shows Link in the tree
house with Kokiri narration, verifying that the inputs passed save load.
This diagnostic deliberately pauses for screen capture and is not pacing
evidence. Initial occluded captures were discarded; retained game captures
bring the process's own window forward first.

A screenshot-free O1 profiling run reaches VI 3546, fault 0, time limit
at 60 seconds (61.296 wall seconds including shutdown). Fault PC remains
00000000, last return address 80000810; no CPU fault PC is reported because
execution did not fault. Presentation intervals: median 16.6916 ms, p95
18.0136 ms, p99 25.7032 ms, maximum 700.5084 ms. The maximum is the third
presentation at 0.051 seconds, during startup. Four later intervals exceed
33.34 ms (35.681, 55.653, 34.995, 35.997 ms). RSP task duration median
0.4361 ms, p95 5.2828 ms, p99 6.4676 ms, maximum 11.3515 ms. Other local
compilation was active, so this is not a controlled performance comparison.
A correct cutscene does not establish smooth gameplay. profile-summary.json/profile.json and profile-run.log
contain the raw receipt. A later quiet run is recorded separately below.

Iteration: copied CPU objects are reused only after regenerating the main
C and every CPU part with the current CLI and checking byte identity. RSP
C objects are reused only when source bytes match; OoT compiles five files
and reuses forty in 2.235 seconds. Its final registry is byte-for-byte equal
to the tested 44-text candidate (3.789 seconds to regenerate). This avoids
unnecessary CPU rebuilds; it is not a runtime speedup claim. The first cold
Rust release build took 151 seconds, while the final incremental build took
8.87 seconds; their compilation/cache scopes differ.

All game runs use visible RT64 windows and SDL_AUDIODRIVER=dummy. Shared
references, RT64 DLLs and junction targets are not rebuilt, refetched or
removed. No ROMs, extracted game data or screenshots enter git.


## Prepared-candidate controls and local gate

30-second visible, silent RT64 controls, using final runtime code and RSP
registries generated by the current CLI. The original CPU maps are retained;
current lower-map output (main C plus every part) is checked byte-identical
before old CPU objects are reused. Compiler-time reference inputs are not
linked into any game executable. Paper Mario and MP2 are repeated after
the final DPC clock change.

| Game | VI | Fault | Fault PC | Build seconds |
| --- | ---: | ---: | --- | ---: |
| pm | 1691 | 0 | 00000000 | 61.402 |
| mp2 | 8 | 8 | 80102800 | 166.754 |
| bk | 1758 | 0 | 00000000 | 27.6 |
| mm | 1699 | 0 | 00000000 | 292.657 |
| sf64 | 1761 | 0 | 00000000 | 31.189 |
| oot | 1764 | 0 | 00000000 | 224.047 |

MP2 retains main's expected VI 8 / fault 8 at 80102800. All other controls
reach their time limit with fault 0. These are finite fault/control-flow
controls; they do not establish visual correctness or FPS equivalence under
concurrent compilation. SF64's previously documented border defect remains
outside this fix. Logs and build commands are retained in control-*/ and
controls-final.json. CPU source identity is asserted for all six games.
The scalar-zero provenance hardening changes only a negative recognizer
case: final-CLI OoT registry JSON and every generated RSP C file are also
byte-identical to the registry already used in the reference task checks.

The final gate runs on one staged tree based on exact main 588bd51c:

- cargo fmt --all -- --check
- cargo clippy --locked --workspace --all-targets -- -D warnings
- cargo test --locked --workspace
- python scripts/test_cli.py
- python runtime/test_runtime.py
- python tools/progress.py --check

The earlier complete runtime pass includes the new DPC contract, retained
SP-event and raw-graphics tests, CPU/PC/RAM ares contracts, cache, coroutine,
overlay, boot and fail-closed mutation checks. The final exact-tree gate is
recorded in target/receipts/oot-jpeg/final-gate.json and final-gate-*.log;
its validated base/tree, exits, timings and landed SHA are posted in issue
#4's MAIN-INTEGRATION CLOSEOUT. Direct-parent equality, refetch/ancestor check
and a plain fast-forward push are required; main drift requires reconciliation
and another full gate. No force options or GitHub Actions are used.


## Independent takeover verification

The requested branch was already checked out in t3-433319a6. Its uncommitted
production/test/documentation candidate was preserved there and recovered
into this worktree's t3/oot-jpeg-boot-1 branch at the same main 588bd51c.
No child agents were launched. Shared references and RT64 were linked to
existing X:/Plaid artifacts without refetching or rebuilding them.

The clean exact ares pin was checked again. Replaying the retained protection
task independently reproduces the 268-instruction result and identical full
RDRAM/IMEM/DMEM and checked architectural state. The retained NJPEG task again
matches all three memories, scalar/vector/flag state, signals, semaphore,
interrupt-on-break, halt/break and final PC 0xafc after 9,668 instructions.
Commands and local outputs are oracle_task.py and recheck_njpeg.py under
target/receipts/oot-jpeg. These observations support the legitimate-rewrite
branch using the requested reference oracle; they are not direct hardware
measurements or a whole-game differential.

Four core and seven lower RSP tests pass. Removing the SP_WR_LEN
OSTask.ucode_boot provenance guard causes the wrong-field 8c02ffd0 test to
fail; it passes after restoration. The mutation compile/test took 25.340 s.
An initial mutation helper had Windows newline/stream parsing errors; only
the subsequently reproduced semantic failure is counted. The DPC synthetic
contract passes current code and fails main's runtime with RSP fault 4 at
IMEM 000 (takeover-dpc-red.log). No production guard is weakened.

Review covered candidate-only provenance, byte bounds, clobbers/zero, DMA
direction, direct CFG filtering, startup uniqueness, fetch identity and the
shared synchronous DPC path. No reference runtime code was copied and no
new guest instruction semantics, decoder, JIT or completeness claim is added.

### Current-tree native controls

Regenerated every game's CPU main/part source with this checkout's release
CLI and asserted byte identity before reusing CPU objects. Regenerated all
RSP registries and built the runtime from current sources with GCC 15.2/O1.
All controls ran visibly with SDL_AUDIODRIVER=dummy and a 30-second limit.
The known MP2 refusal terminates earlier. No other game ran concurrently.

| Game | VI | Fault | Fault PC | Build s | Run/shutdown s |
| --- | ---: | ---: | --- | ---: | ---: |
| pm | 1750 | 0 | 00000000 | 28.662 | 31.312 |
| mp2 | 8 | 8 | 80102800 | 76.113 | 1.247 |
| bk | 1774 | 0 | 00000000 | 15.945 | 31.135 |
| mm | 1766 | 0 | 00000000 | 123.108 | 31.210 |
| sf64 | 1766 | 0 | 00000000 | 15.955 | 31.122 |
| oot | 1767 | 0 | 00000000 | 87.128 | 31.108 |

MP2 matches main's VI 8/fault 8/80102800; the other five controls reach their
time limits with fault 0. This preserves the finite fault/control-flow
controls, not a new FPS/visual equivalence claim. SF64's existing border
rendering defect remains outside this change. Current command script,
per-game logs and source-identity assertions are controls.py, control-*/
and controls-all.json in target/receipts/oot-jpeg.

Current cold release compilation took 70 seconds. ROM-derived RSP object
reuse compiles only 5 OoT files and reuses 40 after source-byte equality,
in 1.973 seconds. Current OoT control build is 87.128 seconds versus the
earlier prepared-candidate 224.047 seconds. Host load/cache state differs;
this is an iteration receipt, not a controlled compiler/runtime speedup.
CPU/RSP reuse avoids repeated compilation without changing generated code.

### Same-save, same-press comparison

Built main's runtime from exact origin/main 588bd51c and used its retained
41-text registry and source-identical CPU objects. Copied the same local SRAM
independently for both executables, then passed the requested five presses
unmodified at VI 1200/1400/1550/1700/1850. Both windows stayed visible and
SDL_AUDIODRIVER=dummy. No other game or compilation ran concurrently.

Main refuses the 352-byte boot at VI 1845 after 32.412 wall seconds: zero matches, unknown or ambiguous ROM-derived RSP microcode. CPU fault 0,
fault_pc 00000000, last return address 800a3760. The fixed executable reaches
VI 3596 and the 60-second time limit (60.729 wall seconds including shutdown), fault 0, fault_pc 00000000, last return address 80000810.
There is no faulting CPU PC to report on the successful run. These are
continuation measurements, not a main/candidate FPS speedup comparison.

Local command/log receipt: run_repros.py, takeover-repros.json and
takeover-{baseline,oot}-repro.log. The first external screenshots were
incorrectly cropped by Windows DPI scaling and are not visual acceptance.

A repeat with a DPI-aware external capture also reaches VI 3596, fault 0,
fault_pc 00000000 and RA 80000810 in 60.719 wall seconds. The 55-second
full-client image visibly shows Link in the tree house and Kokiri narration,
confirming save load passed. The external capture does not pause the game.
The local image visual-oot-scene-55.png has SHA-256
9c95592401ff47c0afde447d7c111b42126a6bbe658717b865581335a8d31e5f.
Commands and log: run_visual.py, visual-repro.json, visual-driver.log.
The screenshots and all ROM/save/capture data remain ignored.

Every current OoT RSP C source and its registry/manifest is byte-identical
to the prepared candidate used in the task-level reference comparisons.
All runtime/lowering headers are also byte-identical. This joins the fresh
visible runs with the retained native task captures and independently rerun
clean-reference comparisons; snapshots do not supply compilation inputs.

### Exact final-tree gate and integration

After the above results, all tracked changes are staged and frozen.
`python target/receipts/oot-jpeg/final_gate.py` runs all six required local
commands listed above, records exit codes/timings, and checks that the staged
tree is unchanged before and after. The ignored final-gate.json includes
its exact base/tree; final-gate-0.log through final-gate-5.log retain outputs.
Issue #4's MAIN-INTEGRATION CLOSEOUT records the resulting SHA, validated
tree/base and actual gate results. A refetch, exact-base and direct-parent
check plus merge-base ancestor check precede the plain fast-forward push.
Main drift invalidates this gate and requires reconciliation and retesting.

Unresolved: this covers save load and the opening cutscene, not interactive
play, every scene/load or whole-ROM RSP closure. DPC timing uses elapsed
wall time and the existing synchronous device model. MP2's overlay refusal
and SF64's pre-existing border rendering defect remain.
