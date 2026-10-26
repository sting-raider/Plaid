# Rogue Squadron lost-line CDE reuse (ADR-0278)

Prepared base: `91211ea8457a08c1391a6e9aeaf239c5786b0e9b`.
Worker: rs-cde-lost-9eebd1b4; branch: t3/rs-cde-lost.

## Hypothesis and observed boundary

CDE does not read destination RAM. A lost backing line can therefore become
an allocated dirty line, provided cache-byte uncertainty remains represented
and no unwritten byte becomes observable. The dunknown mask, byte-precise backing-loss mask and
dirty-residency CPU/DMA guards supply that contract. Incomplete writeback must
mark RAM lost again. This is an allocation, not recovery of unknown bytes.

The fresh native baseline stops VI501/fault4/PC80095040, graphics222/audio430,
physical0017da60, object interval8017da40..8017da90. The older ADR0277 receipt
stopped VI362 at the same PC. Scheduling varies; VI equality is not asserted.
A diagnostic run stops VI365 at the same PC on another object line00180b20.
Before that stop, instrumented native writeback marks0017da60 lost with
unknown mask0f00. This is incomplete CDE writeback, rather than proof that
Hit Invalidate or Index Store Tag caused this game's loss. Those operations
remain covered by synthetic regressions.

## Pinned reference and scope

Read pinned ares9408cb43d4948fc3ea6e152a307a34348df3fe04 CACHE and D-cache
handlers and ISC license. The analysis-only natural-boot observer is built
privately with the repository oracle builder. Shared .refs is read-only,
not fetched or modified. No upstream implementation is copied into production.

The natural interpreter run reaches CDE80095040 on8017da60 at instruction
553831709. Its slot is invalid; CDE retags it17d001, valid1, dirty0 without
filling RAM. The pinned ares dirty-mask difference from the NEC manual remains
explicit (ADR0271): native marks the allocation dirty immediately.
The object stores at8007f840/848/850 and80080188/1d0 cover offsets4..7,
14..15,12..13,2..3,0..1: maskf0ff. This is not four SDs or a full-line clear.
Unknown offsets8..11 must stay guarded. No loads from that line occur in the next2,000,000 observed instructions.
This finite observation does not prove every later lifetime or padding byte.
Immediately before CDE, Index Writeback Invalidate at8002cc40 on80001a60
invalidates this virtual slot (instruction553814752); its different resident
physical line was247a60 with dirty mask000f. No dirty discard of17da60 is
witnessed in this reference sequence. The lost marker belongs to native
witness accounting, not to ares, which retains concrete cache-slot bytes.

## Change and deterministic verification

Remove only CDE's lost-destination refusal. After successful translation,
alias/protection checks and dirty-victim handling, establish dirty residency
and clear the old backing-loss marker. Invalid-slot bytes remain all unknown;
a known resident victim retains only its witnessed bytes. Reads of unknown
bytes still fault4. Partial writeback recreates only its unknown backing-byte mask; dirty
discard conservatively loses every RAM byte in the line. Uncached and DMA observers still reject dirty residency.

Original new full-write-after-discard regression fails at CDE before the fix.
The first complete focused native/ares suite passes after the fix. Expanded
cases cover both discard operations, full recovery, partial read/writeback
refusals, lost state from partial CDE writeback, repeated same-tag CDE, byte
recovery, known dirty victims, and a private unknown-read guard mutation.
A later native cached SW at800801fc over lost backing also needs write
allocation: preserve unknown fill bytes, recover only the stored bytes, and
keep alias/protection checks. A subsequent read at80005e64 of physical17fb50
exposes the old boolean lost marker's overreach: the line could have known
fields alongside unknown padding. line_lost is now a16-bit byte mask, costing
512KiB additional state. Dirty writeback publishes exactly dunknown as the
backing mask (clearing prior loss for every now-known byte); dirty discard
marksffff. A cached fill imports that mask, including clean fills. Both new
fills and hits check the demanded unknown bytes before reads. Uncached CPU
reads check their demanded bytes; DMA retains its conservative whole-line
refusal whenever any backing byte is unknown. Existing full-line DMA recovery
remains unchanged; partial DMA does not manufacture a cache witness.

A second original full-state differential is red on the boolean model and
green with byte masks: partially initialize, writeback/invalidate, refill and
read known fields, then fill another field and inspect known uncached words.
The paired negative fixture reads still-unknown padding and faults4. The
native model contract checks mask0f00 for the observed12-byte pattern, known
reads after clean refill, unknown padding, and final complete recovery. The
complete focused suite passes, including DMA refusals and a killed private
unknown-read mutation. No production or shared reference source is mutated.

No runtime guest instruction interpreter, decoder or JIT is introduced.
Residual CPU sites remain16/native_complete:false. No README edits, child
agents, shared RT64 rebuild, copyrighted assets or traces in git. Ignored
artifacts: target/receipts/rs-cde-lost; native windows are visible and silent
(SDL_AUDIODRIVER=dummy). Stop JSON supplies VI/fault/PC; images decode RDRAM.


## Native continuation and remaining gameplay boundary

All VI/fault/PC below are runtime stop JSON, not desktop observations. The
user-supplied USA Rev1 ROM hash remains4813551d01d3a3474df3a51f84c31059cd2a9d1eeae7885dda51a88ee6b9f88d.
Every window is visible with SDL_AUDIODRIVER=dummy. PNGs are decoded from
RDRAM and excluded from git, together with all ROMs/assets/saves/traces.

| Stage | Request s | VI | Fault | Fault PC | Graphics/audio/PI | Run+dump s |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| Baseline |30|501|4|80095040|222/430/161|15.922|
| CDE allocation only |30|467|4|800801fc|264/397/266|14.187|
| Cached write allocation |30|489|4|80005e64|198/402/788|17.781|
| Byte-precise backing |30|1276|0|00000000|572/997/2453|see rs.json|
| Byte-precise backing + early input |30|984|0|00000000|408/811/2132|see rs-press.json|
| Neutral continuation |90|2092|0|00000000|646/1676/5334|see rs-long.json|
| Pilot menu input |90|1523|11|80013408|606/1252/see rs-menu.json|see rs-menu.json|

The literal PI values in the two30s fixed rows are supplied by rs.json and
rs-press.json; the final receipt remains authoritative for all measurements.
Runs progress to rendered X-wing/terrain, the film intro and an ENTER NAME
pilot menu. rs.png/rs-press.png, rs-long-interlaced.png and the pilot-menu
readback preserve these milestones. Scheduling/load and reached content differ;
these stop times are not a controlled before/after speed benchmark.

A working prefix reaching the pilot-name menu is:
`--press 0x1000@600:4 --press 0x1000@1000:4 --press 0x1000@1200:4 --press 0x1000@1500:4`.
The full attempted list also has Start1800/2000 and A2200/2300/2400/2500/
2600/2800/3000/3200/3400, each4VIs; they do not fire before this stop.
No interactive mission/gameplay acceptance is claimed.

80013408 is SWC1 f26,0x24(s2), compiled with the checked FR0 default; live
Status is2400ff01 (FR1), so fault11 protects a real layout mismatch. The
function includes odd-FPR loads and register transfers too: deleting this
guard would silently use the wrong layout. Unknown-entry FR specialization
or verified dynamic FPR accesses across calls is separate work. Preserve the
ADR0276 scheduler/FR guard and establish the actual incoming-mode contract.

VI WIDTH is a stride, not always the displayed image width. The later menu/
film mode has WIDTH1024, serrate, X_SCALE819,Y_SCALE1024: pinned RT64 detects
512-wide interlaced storage and about444 rows. A naive1024x221 decode shows
two fields side by side. Diagnostic PNG decoding must account for this;
raw storage PNG dimensions are not a display-aspect measurement.

## Aspect: framebuffer storage versus the TV surface

Pinned RT6443373749dac9bbc1b653e6a02aed40a9e1783bed (MIT) defaults to
Original aspect, Original extended aspect, WindowIntegerScale resolution,
Original refresh and SkipBuffering presentation. The bridge disables disk
configuration, so saved RT64 preferences do not override these. The actual
window/swapchain is1302x776 on this host. Window size alone does not stretch
the image: VIRenderer fits and centers a viewport on each resize.

The inherited removeBlackBorders=true setting instead uses fbSize as that
surface. RS programs WIDTH400, X_SCALE640,Y_SCALE2048, H_VIDEO108..748,
V_VIDEO53..495, V_SYNC524,H_SYNC3093 (NTSC; runtime tvType1 and59.94Hz).
This is roughly400x444 storage with non-square pixels. Before correction the
common actual viewport is700x776 (other startup modes1044/1108x776), rather
than a4:3 TV surface. SF64's320x240 storage already produces1034x776.
VI registers alone do not identify an intentional guest anamorphic option;
no bridge16:9/Expand setting is active in these runs.

Set only enhancementConfig.presentation.removeBlackBorders=false before
setup. Keep Original projection/aspect settings and the actual guest VI
registers. This corrects presentation to1034x776 for both games, without
changing the guest's 3D projection to a guessed widescreen mode. A synthetic
live-resize check records666x500 in1000x500 and700x525 in700x700: pillarbox
and letterbox behavior stays4:3. Numeric viewport/scissor observations come
from the actual VIRenderer and swapchain, never desktop captures. This does
not implement the pinned VI viewRectangle/cropRectangle placeholders or
certify PAL/overscan/anamorphic options.

## Pacing: synchronous per-command renderer handoffs

Separate private instrumented bridges log host nanoseconds at each VI,
actual swapchain present/wait, screen call, native RSP task, raw RDP/HLE
submission, RAM sync and audio call. Each request is30s, neutral controller,
visible/silent; only this worker's compiler process tree is suspended during
the measurement and resumed in finally. User applications are untouched.
No capture pause or compiler runs during the timed windows. Trace logging
itself has overhead, so a second pair omits trace-file logging.

Aspect-only correction leaves pacing approximately unchanged. RS has roughly
420k renderer submissions in30s, versus about900 HLE tasks for SF64. RSP runs
synchronously under the scheduler mutex. Sending each tiny DPC chunk through
a second thread's condition variable blocks VI delivery for long stretches.
RS VI p95 is194.341ms, with mutex wait p95192.756ms. In the aspect-only run,
p95 is203.845ms. Screen calls are sub-millisecond and present-wait p95 is
0.0044ms; dummy audio p99 is0.014ms or less. These exclude recurring vsync or
audio blocking as the main measured cause. The initial RDP call can hitch
for0.56s; shader/pipeline compilation attribution was not separately
instrumented. The recurring long gaps also occur after startup.

Run each already-lowered RSP task once on the renderer owner, synchronously.
Nested RDP calls execute inline on that owner, preserving command order,
readback visibility, return codes, native-fetch guards and the existing
SP/DP completion points. No commands are batched across RAM writes, no CPU
execution overlaps the RSP, and no decoder/JIT/interpreter is introduced.
The C ABI borrows a context until completion and rejects null callbacks.
GPU tests verify a different owner thread, exactly-once/nested callbacks,
result37, borrowed context, nested RDP/readback bytes and null refusal.
Retained native graphics tests verify frozen DPC, wrapped DMEM, RDRAM/CPU
visibility, automatic LLE and corrupted-code refusal through this callback.

In the matched traced owner run: VI1195/fault0, VI p9590.918ms, present p95
93.913ms, RDP average10.620us (38.415us in the aspect-only baseline). The
same30s without trace-file logging advances VI777->1285, both fault0:
65.4% more VIs in the fixed wall budget. These are finite host measurements,
not a cycle-accuracy certificate or universal FPS claim.

Presented-frame interval histograms (all samples, including startup):

| Interval ms | Before | After owner handoff |
| --- | ---: | ---: |
| 0..8 | 27 | 39 |
| 8..12 | 30 | 33 |
| 12..16 | 140 | 220 |
| 16..20 | 176 | 362 |
| 20..25 | 57 | 96 |
| 25..33.4 | 52 | 73 |
| 33.4..50 | 21 | 74 |
| 50..100 | 16 | 76 |
| 100..250 | 65 | 39 |
| 250+ | 25 | 1 |

The after run reaches more content, so compare normalized counts/quantiles,
not raw bin counts alone. The first visible-start interval is about2.17s;
after5s distributions are retained separately in pacing-summary.json.
SF64 remains near60VI/s, with VI p95 about17.99ms and presented p95 about41ms
(its original logical rate is around30Hz). SF64 aspect-only checks isolate
the global configuration issue from RS's unusually fine-grained RDP path.

An all-zero dirty-map precheck was tested separately and rejected:1195 vs
1178VIs and sync average5.823 vs5.844us do not demonstrate a gain. It is not
in production. Remaining90..120ms tails track long synchronous native RSP/
RDP tasks and the fixed-deadline policy drops retraces after a frame-long
stall. Further work should profile RSP CPU versus RT64 workload/driver costs,
then verify asynchronous RSP/event scheduling or RAM-write-aware submission
batching with state/readback/event differentials. Do not disable vsync or
relax guest guards to hide those tails.

## Build, local gate and integration

Default GCC15.2 builds native artifacts. The renderer bridge uses the existing
MSVC RT64 toolchain. The private production DLL links the unchanged pinned
RT64 library with its three retained build patches; new bridge code is built
in this worktree. Parser/readback and the visible GPU scissor/owner contracts
pass. Only the local game-window DLL is updated. Shared .refs, protected
junctions and the shared RT64 Release directory are not written or refetched.
No RT64 patch changes or upstream code copies enter production.

To deploy to the shared checkout, rebuild the bridge with the repository's
normal command (the new runtime requires the native-RSP callback export):

```powershell
cmake -S runtime/rt64 -B target/rt64-shim -G "Visual Studio 17 2022" -A x64 "-DCMAKE_POLICY_VERSION_MINIMUM=3.5" "-DCMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES=X:/Plaid/target/directx-headers/include/directx;X:/Plaid/target/directx-headers/include"
cmake --build target/rt64-shim --config Release --target plaid_rt64 -j 8
ctest --test-dir target/rt64-shim -C Release --output-on-failure
```

CPU/RSP control maps are retained, ROM-content-bound inputs, regenerated with
current solver/lowering and normal source/compiler/header/flag keys. RSP
object migration additionally checks prior keys and exact preprocessor output;
it avoids recompiling unchanged reference-independent native code. This is
runtime/lowering regression coverage, not fresh discovery for the controls.
The initial baseline build is45.969s (52 RSP objects reused); changed-code
builds101.610/167.282/178.703s rebuild different units and are not a controlled
compiler speed comparison. The large MM build includes explicitly paused
compiler time. Full per-build timing/command receipts remain ignored.

Required exact-tree gate:

```
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

Sealed-tree command exits/timings are in gate.json and final-gate-*.log.
Final controls are silent/visible PM,BK,MM,SF64,OoT30s; MP2 uses Start600/1250
and A1360/1440/1520/1600/1680/1760 (all4VIs). OoT save-load uses the retained
SRAM fixture (source/hash recorded),60s, Start1200 and A1400/1550/1700/1850
(all4VIs). all-controls.json and per-run stop JSON/PNG record actual acceptance.
The final issue4 closeout and integration.json record exact base/tree, gate,
controls and landed SHA. A refetch, direct-parent/base equality and ancestry
check precede plain git push origin HEAD:main; main drift requires a new gate.
No README edits, child agents, forced push, CI validation substitute or
copyrighted payload in git. Native completeness remains false/16 residual sites.

## Final control receipts and input timing limit

On the final production code, PM/BK/MM/SF64/OoT30s stop at VI1763/1782/
1620/1765/1760 respectively, all fault0/PC00000000. OoT save-load60s stops
VI3588/fault0, with the opening scene visible after loading the retained SRAM.
RS30s stops VI1247/fault0; Start600/1000/1200/1500 reaches SELECT GAME at
VI3369/fault0 in90s. The longer Start/A list below stops VI1873/fault11 at
80013408, Status2400ff01, confirming the remaining name-entry guard on the
final executable. A separate90s run ends in the film intro at VI4782/fault0.
These runs share persisted512-byte EEPROM state from prior pilot attempts;
rs-final-save-fixture.json records its hash. They are finite paths with
different input/save/scheduling history, not proof that FR11 was repaired.

The longer attempted RS list is the earlier Start600/1000/1200/1500/1800/2000
and A2200/2300/2400/2500/2600/2800/3000/3200/3400 prefix, followed by
Start4000/4500/5000 and A5200/5300/5400/5500/5600/5700/5800/5900/6000/
6200/6400/6600/6800/7000, all4VIs. Later presses do not fire before the fault.
No interactive mission acceptance is established. Current RDRAM readbacks:
rs-final.png, rs-final-menu-interlaced.png, rs-final-play-interlaced.png and
rs-final-drive-interlaced.png, with matching stop JSONs.

MP2's supplied exact list completes30s at VI1766/fault0 but ends during
Toad's transition;45s reaches VI2685/fault0 and his greeting on the destination
screen. A same-host A/B with the retained pre-change executable and identical
EEPROM hash also misses the explicit prompt: baseline VI1792/fault0,
graphics1732/audio1742; candidate VI1794/fault0,1708/1765. The candidate with
AboveNormal process priority reaches VI1798/fault0,1740/1784 and the same
transition. This does not establish a new regression or a priority fix.

Keeping the supplied prefix and adding A2000/2100/2200 (each4VIs),45s reaches
VI2691/fault0/PC00000000, graphics2524/audio2624. The readback matches the
prior destination/rules screen, including the selection hand and Yes/No
question (mp2-destination-extended.png). All these runs retain the supplied
Start600/1250 and A1360/1440/1520/1600/1680/1760 prefix unchanged. The exact
list alone is not certified to reach the explicit prompt on this host today;
baseline/candidate input-poll timing needs an SI trace to explain it. Do not
silently count the earlier greeting as the requested selection acceptance.

All final production source/bridge code is unchanged by this receipt update.
The six-command gate is rerun on the updated tree; new visible/silent controls
reuse the same content-keyed native objects and exact production bridge.
