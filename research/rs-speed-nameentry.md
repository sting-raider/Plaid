# Rogue Squadron native LLE performance and name entry

Worker: rs-speed-nameentry-33d31dd2. Prepared base: `40515aef`.
Direct integration is authorized; no child agents. README belongs to the
integrator. Native runs use visible windows and `SDL_AUDIODRIVER=dummy`.

## Measurement plan and competing hypotheses

1. Raw DPC submissions dominate through RT64 parser/setup work. Measure
   raw-call, parser and byte totals separately from native RSP execution.
2. RAM synchronization still dominates despite sparse dirty pages. Measure
   its exclusive elapsed time; preserve task-entry invalidation and DMA pages.
3. Native RSP instruction/fetch overhead dominates. Subtract nested renderer
   time from total RSP work before changing lowering or compiler flags.
4. Scheduler waits amplify long tasks into dropped VIs. Measure mutex wait,
   VI intervals and actual swapchain presents, including a post-startup split.
5. Logging or presentation is a significant cost. Aggregate hot-path counters
   in memory and compare an uninstrumented run; time screen/present waits.

Ignored evidence: `target/receipts/rs-speed-nameentry`. Pinned references are
read through a junction to `X:/Plaid/.refs`, never refetched. Native inputs and
matching objects from ADR-0278 are copied privately, with unchanged source,
compiler and preprocessing checked before reuse. The profiling bridge links
the unchanged pinned RT64 library; instrumented present-queue code is a private
copy. RT64 is MIT; no reference body is copied into production.

## Initial measurements and retained change

Private instrumented 30-second RS baseline: VI1487/fault0, about2.08M
raw submissions by the last aggregate checkpoint. Total RSP16.167s,
renderer calls8.994s, nested RAM sync5.118s and parser2.581s. These are nested
timers, not additive totals. SF64 HLE control: VI1794/fault0.

The shadow-RAM synchronizer compared every dirty page word-by-word and
scanned2048 dirty flags for every tiny raw submission. Compare dirty flags
in groups of64 and RAM in64-byte blocks first, retaining the original
changed-word stores. This preserves renderer words whose guest bytes did
not change. An independent byte-for-byte reference test covers clean/full/
sparse/non-boolean dirty flags, group/page/block boundaries, last RAM byte,
both directions of guest changes and untouched renderer bytes.

One-variable staged results: original VI1487, RAM-block comparison VI1663,
grouped dirty flags plus blocks VI1788, all fault0. Post5s VI p95 respectively
61.762/34.417/28.229ms. Startup/build and instrumentation qualifications
require quiet repeat runs before final acceptance. The aggregate grouped
sync cost is1.972s for2.88M raw calls. Original content advances less far,
so per-call and interval distributions matter more than unnormalized totals.

Rejected experiments: conservative command batching across DPC END writes
with explicit DMA/DPC-observation/sync/task-end boundaries did not establish
a useful independent gain. The private initial game experiment also reused
generated prelude bodies, so it does not verify the new DMA callback; its
timings are excluded from any production claim. The complete candidate is
retained only in ignored receipts. `-O3` alone likewise did not improve the
matched workload enough to keep. Production has no batching or flag change.

## Quiet matched measurements

All four requests use the same local ROMs and privately copied save inputs,
visible windows, SDL dummy audio and default GCC15.2 RSP `-O2` objects. No
compiler, screenshot or capture pause runs inside the timed windows. Timers
use steady-clock nanoseconds. VI samples are recorded at the actual source;
present samples are the actual RT64 swapchain calls. Hot-path timers aggregate
in memory; only VI/present/checkpoint rows go to CSV. Aggregate totals are
sampled every60VIs, so the final partial second is excluded from those totals.
The stop JSON is authoritative for VIs/fault/PC and the30s wall budget.
Elapsed process time also includes window/driver startup and output teardown.

| Game | Before VIs/fault | After VIs/fault | VI p95 after5s, before/after ms | Actual present p95, before/after ms |
| --- | --- | --- | --- | --- |
| RS |1602/0|1798/0|37.768/18.180|38.109/20.360|
| SF64 HLE |1798/0|1798/0|17.759/17.793|36.877/37.065|

RS's VI median is16.693ms after startup, close to the16.683ms model period;
the measured tail is18.180ms, rather than exactly17ms. SF64's original
roughly30Hz logical presentation remains distinct from60Hz VI cadence.
This establishes the requested approximate VI rate for the finite tested
scope, not60 new guest render frames per second, instruction-cycle accuracy,
or universally stall-free gameplay. Neutral/menu scope is followed by controls.

Histogram bins below are milliseconds. VI histograms include startup; the
separate post5s statistics and all quantiles are in pacing-summary.json.

### VI interval histogram

| ms | RS before | RS after | SF64 before | SF64 after |
| --- | ---: | ---: | ---: | ---: |
|0..8|134|1|0|0|
|8..12|29|10|1|0|
|12..16|183|445|326|324|
|16..20|932|1320|1469|1473|
|20..25|34|20|1|0|
|25..33.4|150|1|0|0|
|33.4..50|138|0|0|0|
|50..100|1|0|0|0|
|100..250|0|0|0|0|
|250+|0|0|0|0|

### PRESENT interval histogram

| ms | RS before | RS after | SF64 before | SF64 after |
| --- | ---: | ---: | ---: | ---: |
|0..8|139|4|0|0|
|8..12|27|12|0|0|
|12..16|309|469|16|11|
|16..20|702|1137|68|75|
|20..25|40|30|1|3|
|25..33.4|166|30|421|426|
|33.4..50|165|27|428|422|
|50..100|3|9|1|2|
|100..250|0|0|1|0|
|250+|0|0|0|0|

### Host-time attribution

The quiet baseline checkpoint includes2,726,763 raw submissions/82.455MB;
after includes2,843,071/86.559MB. Both hit fault0, reaching different amounts
of content. Nested total RSP time is16.177->13.528s. Renderer-call time is
9.495->6.481s, containing RAM synchronization5.030->2.003s and raw parsing
3.172->3.132s. Per raw call, sync1.845->0.704us and renderer3.482->2.279us.
Native RSP exclusive of nested renderer time is approximately6.682->7.048s;
this is not evidence of an instruction-code speedup. Screen0.159->0.163s,
dummy audio0.0051->0.0052s; actual present waits remain tiny. Unnormalized
totals cannot be treated as identical instruction workloads.

A separate private generated-unit probe measures2.974M live-text verifications
at1.128s and3.832M DMA calls at0.353s, including probe overhead. It narrows the
remaining native cost but does not justify deleting guards or DMA checks.
The profile paths and source hooks are retained in target/profile-helper.h,
target/profile-units.py, target/build-pacing.py and target/bench.py. These are
diagnostic instruments, never linked into the production DLL/executables.

### VI source ordering

The old event thread could not observe the next VI deadline while the guest
mutex was held across an entire synchronous native RSP task. Even a fast
renderer therefore sampled some retraces only after a20..40ms task ended.
The same fixed-deadline VI source now also polls before an RSP DPC bus
operation and after the owner finishes. No CPU instruction runs concurrently
with RSP work. No guest queue write or scheduling handoff is permitted inside
the borrowed renderer callback. RDP calls, readbacks, DPC registers and final
SP/DP completion remain synchronous and ordered. Polling can present the
last guest-written VI state between complete RDP submissions; it never
interrupts the parser or invents extra render completions.

An original deterministic synthetic clock advances exactly one period at
each of10 raw submissions. All10 retraces occur during the native callback;
the guest queue remains unchanged in every renderer call. After scheduler
delivery, its messages remain SP,10VI,DP. Command words and2048/0 sparse
dirty-page census are unchanged. Removing both new RSP polling points gives
zero retraces inside the callback and fails the positive contract. The normal
fixed-deadline/drop policy remains; no wall-clock catch-up counter is added.

Reference semantics read at pinned ares9408cb43: VI's own timed execution in
vi/vi.cpp and RSP timing in rsp/rsp.cpp; RT6443373749's raw parser and original
present queue. ISC/MIT notices remain upstream. No upstream implementation
body is copied into Plaid and no emulator, guest decoder or JIT is linked.

## Build and validation contract

### Required MP2 control exposed an existing one-use descriptor refusal

The retained ADR0278 executable and candidate both stop on the full supplied
MP2 list, respectively VI2502/2503, fault13/8007dbd8, during the transition
after Toad's destination scene. The candidate's graphics/audio counts are
3720/2494, versus3716/2493. This is a reproduced baseline limitation, not a
new renderer regression. A private refusal probe identifies `j->spawned`:
buffer801debcc has the same thread/generation and all21 non-entry/stack words,
but a second authored stack/entry. A blanket one-use flag rejects it even
though the previous creation descriptor has no live host continuation.

Retain the most recently accepted23-word descriptor after each creation.
An unchanged descriptor without a live saved owner still refuses. A later
actual entry/stack edit may create another native context after alignment,
layout, saved-register, thread-generation and native-entry checks. Rechecking
a null previous owner is required, rather than bypassing native target proof.
No old host continuation is resurrected; existing retirement and pin release
rules apply. All resource caps and foreign/stale/edited-register refusals stay.

An original three-generation program uses one buffer for three distinct
entry/stack descriptors. It matches the pinned ares interpreter in all GPRs,
FPR bits, PC, HI/LO, FCSR and64KiB RAM, and finishes with only its root native
context. Reinstating a one-use refusal kills the positive contract. The full
retained coroutine suite also passes unchanged-descriptor, foreign-edit,
cross-thread/generation, ownership, frame-pin and resource-limit negatives.
The full supplied MP2 press list now completes45s at VI2696/fault0/PC00000000;
RDRAM PNG mp2-fixed.png shows Rules Land's explanation screen. The prior
stopped transition and old/candidate command/state receipts remain ignored.

CPU lower-map output was freshly regenerated from each retained ROM-bound
control map and byte-compared before object reuse. Every reused CPU and RSP
object's normal source/compiler/header/flag key was checked against the
ADR0278 input. RS experimental objects were replaced with original default
GCC15.2/O2 objects. No shared reference, Release DLL or protected junction was
modified. CPU native completeness remains false with16 residual RS sites.

The private CMake bridge project compiles current bridge/parser/readback/RAM
contracts in this worktree and links the unchanged pinned shared RT64 static
library. `ctest --test-dir target/rt64-private -C Release --output-on-failure`
passes parser/readback, RAM equivalence and visible GPU scissor/owner tests.
Full RT64 source recompilation is unnecessary for this bridge-only change.

Shared deployment command (run by the shared checkout owner):

```powershell
cmake -S runtime/rt64 -B target/rt64-shim -G "Visual Studio 17 2022" -A x64 "-DCMAKE_POLICY_VERSION_MINIMUM=3.5" "-DCMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES=X:/Plaid/target/directx-headers/include/directx;X:/Plaid/target/directx-headers/include"
cmake --build target/rt64-shim --config Release --target plaid_rt64 plaid_rt64_ram_contract -j 8
ctest --test-dir target/rt64-shim -C Release --output-on-failure
```

Required final-tree gate and exact commands/results are recorded in gate.json,
bridge-ctest.log and integration.json under ignored receipts:

```
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

Silent visible PM/BK/MM/SF64/OoT30s, MP2 destination45s with the full supplied
Start/A list through VI2200, and OoT save-load60s use stop JSON and RDRAM PNGs.
The retained SRAM fixture is copied privately and hashed in the receipt.
Controls.json and individual command/stop/PNG receipts record actual VI counts.
No screenshot, ROM, save or game asset is committed. Name entry and missions
remain subsequent work, independently subject to ares and native verification.
