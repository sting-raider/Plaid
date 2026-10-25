# Rogue Squadron native RSP overlays and automatic LLE (ADR-0274)

## Scope and recovered candidate

Base: `6ff5effa88462de3b83bab6d44b9ab83a079d739`. The earlier
`t3/rs-rsp-ucode` checkout at `t3-531c05dc` had seven useful uncommitted
files and no ahead commits. Its exact binary patch and ignored evidence were
preserved under `target/receipts/rs-rsp-ucode/prior`; the original checkout
was not modified. Implementation checkpoints are retained locally before
squashing the final direct child of the validated canonical base.

No game addresses seed discovery. No snapshot supplies compiler input. All
ROMs, captures, saves, generated C, images and executable artifacts remain
ignored. README is integrator-owned and unchanged. No child agents were used.

## Root cause and provenance

The refused `db0` is a **missing placement of ROM text**, rather than a missed
instruction in the original `080` placement. The boot copies `0xf80` bytes
from task ucode `8001ebe0` to IMEM `080`. Its native loader at IMEM `248`
subsequently reads `0xd8` bytes from RDRAM `0001f918` into IMEM `db0`.
The descriptor's encoded DMA length is `0xd3`; SP rounds it to doublewords.
Those bytes are rooted at ucode + `0xd38`, backed by ROM `00020518`.
The resident placement contains the same sequence at a different PC, which
cannot substitute for the instructions' actual IMEM control-flow addresses.

The existing descriptor scan understands u32 source/u16 length/u16 destination
records. This loader uses packed halfwords: a length's high nibble selects a
destination halfword by byte offset; its low twelve bits are SP_RD_LEN,
followed by a u16 ucode-relative source. Recognize the loader's LHU fields,
SRL-by-12 selector, ANDI `fff`, OSTask.ucode source addition, JAL delay-slot
destination load and exact three-register SP-read DMA helper. Only layouts
named by a rooted text are scanned, within one DMEM-sized rooted data window.
Reject odd/out-of-table selectors, unaligned sources/destinations, tiny or
wrapping extents, missing words and insufficient descriptors. These are
candidate hints, never target certificates.

Existing content filters, overlay composites, startup uniqueness and per-word
fetch guards remain authoritative. Each accepted placement is lowered ahead
of time; indirect transfers/changed overlays dispatch only among emitted
native entries and fault otherwise. The manifest still says `complete:false`.
Neither ROM-wide RSP closure nor CPU `native_complete:true` is established.

## Unknown GBI routing

The RT64 bridge queries its pinned GBI matcher against current RAM bytes,
including reuse of the same text/data addresses. Unknown GBI returns the new
ABI result `PLAID_GFX_UNKNOWN_UCODE` before display-list/RDP execution or
writeback. Bounds checks use the same physical addresses later consumed by
HLE. Known GBI continues through HLE. On the unknown result the host runtime
loads the task, seeds its native DPC state from CPU DPC start/current/status,
and selects the existing guarded native-RSP -> raw RDP -> RT64 path.
Subsequent graphics tasks stay on that path. No game-name/hash exception and
no runtime guest decoder, MIPS interpreter or MIPS JIT is added.

The synthetic bridge compares explicit `--rsp-gfx` and automatic LLE,
including CPU freeze before fallback, wrapped DMEM commands, thaw, RDRAM
commands, SP memory, state and refused altered boot code. The private real
RT64 contract checks unknown/out-of-range/alias addresses cause no framebuffer
writes and then verifies raw-RDP RGBA16/RGBA32 scissored clears pixel by pixel.

## Follow-on general gaps

Passing RSP exposed a callback at `8007ec04` to `80016ba0`. The ROM names the
function, but the function follows an unconditional J's delay slot instead
of JR RA. Address-taken discovery now accepts that non-fallthrough layout only with a
new aligned negative ADDIU sp,sp frame prologue,
also across existing bounded zero padding. This also admits the callback
`80020b80` reached at `800219b4`; it already had decoded blocks but lacked a
callable entry. Calls/conditional branches still supply no layout boundary,
and CPU-body filtering, hole/load identity and residual target guards remain.
Calls and conditional branches remain excluded. Requiring the frame keeps
ordinary jump-table cases from becoming independent proof barriers: the first
workspace gate caught two derived-entry/table-source regressions in a broader
J-only hint. Both regressions pass after narrowing; verifiers were not weakened.
This broadens candidate discovery; it is not a new control-flow theorem.

A timing-dependent SI refusal was a standard write probe to an absent
Controller Pak (TX35/RX1, command3). The declared platform still has no Pak.
It now returns absent-Pak reads and complemented write CRCs, rather than
refusing an ordinary device probe. Short writes return ff; unused receive
bytes remain untouched. No Pak storage/persistence is invented.

At VI70, with 35 graphics and 35 audio tasks, the SDK stopped a blocked
thread. Host queue wake selection is already explicit in T_BLOCKED. Stopping
now removes that eligibility while retaining the parked send/receive
continuation; restarting resumes it and rechecks its queue normally. Guest
STOPPED state is written. Tests check stopped receive and full-send waiters,
repeat stop, no accidental queue wake, message order and saved s0. The real
identified 176-byte osStopThread at `8002bbf0` has SHA256
`7224955f5cf4d00fdb7ea05f67494e0212264db251314b85843f7126a28cee26`;
its waiting-state arm writes STOPPED then removes the thread from its queue.

## Reference verification and deterministic tests

Pinned ares is `9408cb43d4948fc3ea6e152a307a34348df3fe04` (ISC).
Its `rsp/dma.cpp`, `rsp/io.cpp`, `pif/hle.cpp` and
`controller/gamepad/gamepad.cpp` were read as behavioral references.
Pinned RT64 is `43373749dac9bbc1b653e6a02aed40a9e1783bed` (MIT).
Its GBI manager and interpreter interfaces were read. Reference checkouts are
clean and read-only; neither was refetched. N64ModernRuntime's pinned thread
implementation was consulted but does not implement stopping another thread;
it is not claimed as an oracle for the new stopped-waiter behavior.
No reference implementation body or game/SDK instruction body was copied.

A fresh real first graphics task was captured from the native game run.
The isolated project-owned native task harness links the ROM-derived registry,
loads only the captured **initial** state/memories, and submits DPC without
rendering. The separate retained ares oracle's revision and exact driver hash
were checked. Both isolated paths agree after **2,694 instructions** in all
**331 state words**, **8 MiB RDRAM**, IMEM and DMEM, including PC `0f4`, scalar,
vector/accumulator/divider/flag, signals, semaphore, interrupt-on-break,
halt and break. This is one real task, not a whole-game differential.

Direct runtime after-RAM also contains RT64 framebuffer writebacks, which the
RSP-only ares driver does not execute. Those render side effects were not
misrepresented as RSP memory disagreement: the isolated native harness and
ares compare complete memories under equivalent DPC submission-only conditions.
Diagnostic task captures are never registry/compiler inputs.

Matched isolated after-memory SHA256:

- RDRAM: `94ef04fefcda1bbfdb4494440f7f67f98fecee102d5de44fe3c8530c5ba0356f`
- IMEM: `7d97bedb380fd73e51131f3f977614bdb16d1ee12b2c83820fa97b63bb6eecfc`
- DMEM: `a9018a9ccc50360cba5c2ca53a89cb47dab190712b702b37a60d5689cda8c02f`

Focused core, ROM discovery -> task DMA -> guarded entry, graphics bridge,
no-Pak and stopped-waiter contracts pass. The new synthetic packed fixture
loads its entire table in its task's DMEM DMA. Inverting the packed selector
alignment guard fails its core regression (exit101); source restored.
Removing the stopped-waiter transition fails the ordering/state regression;
source restored before acceptance. Tests mutate private runtime copies when
run by the retained suite.

## Build and acceptance receipts

Every game window is visible, with `SDL_AUDIODRIVER=dummy`. Runtime stop JSON
is authoritative for VI/fault/PC. Visuals use completed RT64 RDRAM writeback
and `--dump 0x80000000 2097152`, never the desktop or foreground window.
Use default MinGW GCC15.2, not the separate MSYS2 GCC15.1.

Private RT64 wrapper build: `target/receipts/rs-rsp-ucode/build-wrapper.py`
compiles this checkout's `runtime/rt64/plaid_rt64.cpp` with the retained Release
compile recipe and links existing read-only static RT64 objects/libraries,
writing all wrapper outputs under this checkout's `target/rt64-shim`.
No upstream RT64 patch changes or shared-shim rebuild occurred. After updating
the shared checkout to this landing, rebuild its wrapper with:

```
cmake --build X:/Plaid/target/rt64-shim --config Release --target plaid_rt64
```

Run `python runtime/rt64/test_scissor.py <new-plaid_rt64.dll>` and distribute
the rebuilt DLL with the new runtime. The old DLL cannot report unknown GBI
safely; both sides of the updated ABI must be deployed together.

Ignored receipt directory: `target/receipts/rs-rsp-ucode/`.
`controls.py` uses the normal source/compiler/header/flag cache, retains verified
load declarations, and omits unused headless artifacts for window-only runs.
Eighty-one retained RSP objects migrated in 23.844s only after verifying their
old normal cache keys and byte-identical actual -O2 preprocessor output at
old/new paths. All other changed/generated outputs compile normally. The
CPU layout change repartitions the generated parts and requires fresh objects;
no mismatching old CPU object is relabeled or accepted.

Baseline independently rerun: a 30s native-RSP request exits after 1.078s at
VI1, CPUfault0/fault_pc00000000, 15 PI DMAs, one graphics and zero audio tasks,
with unlowered IMEM db0. An intermediate fixed run reaches VI243, 48 graphics,
189 audio and 25 PI DMAs, then refuses the callback at800219b4. Its automatic
LLE readback is black (an independent timing reaches VI104 at the same fault).
These short requests stop at verified guards; CPU fault0 on an RSP/SI/runtime
refusal is not a successful run. Final control/game/gate records follow.

## Final narrowed-discovery Rogue Squadron result

The 30-second explicit --rsp-gfx request terminates on its next CPU guard:
VI105, fault2, fault_pc80884650, RA800a4638, 48 graphics tasks, 53 audio tasks
and 32 PI DMAs. The lowered instruction is SB v0,1(v1), with v1=80096bfc and
v0=41: a byte store to80096bfd. No guard is disabled to continue. Investigate
its executable/data binding and active write protection before changing the
memory model; the instruction's slot PC corresponds to linked800a4650.

The updated bridge also selects native LLE automatically without --rsp-gfx.
Independent full-RDRAM readback exits after4.594s at the same fault/PC, VI102,
48 graphics,55 audio,32 PI, framebuffer0066a280. Its320x240 RGBA5551 readback
has zero nonblack pixels and one color. No rendered title/menu or applicable
Start/A interaction is established. This task therefore remains PARTIAL for
first-frame/gameplay acceptance, despite passing its original RSP blocker.
VI/audio variation reflects timing; no continuation speedup is inferred.
The CPU/RSP completeness manifests remain false.

This worker did not rebuild the shared shim. The private bridge must be
deployed with the runtime, using the rebuild instruction above. Required
controls use the exact press lists from the task; final JSON and framebuffer
readbacks are retained with the gate receipt in the ignored directory.
