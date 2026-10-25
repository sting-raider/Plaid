# Status

## Slot data and Rogue Squadron's first visible screen (ADR-0275)

Slot binding now verifies/protects every emitted instruction plus immutable
proof inputs, rather than treating a raw candidate extent as a contiguous
section. Mutable prefix/inter-function data remains writable; code tampering,
active/suspended frame writes, ambiguous bindings and unknown targets still
fail closed. Synthetic CPU/ares, rebind, tail-cell and guard-mutation coverage
is retained in runtime/test_slot_data.py.

Rogue Squadron passes SB at80884650 to80096bfd: its loaded overlay exactly
matches ROMfdec0..126660 in native RDRAM and pinned ares. The game advances
48 ->53 graphics tasks. A silent visible request stops at VI114/fault12/
80013c34; an independent VI111 readback shows the readable640x480 copyright
screen,19496 nonblack pixels/48 colors. Start/A repeats the new refusal.
A matrix routine's Status.FR0->FR1 transition in an SDK thread is unsupported;
its FPR accesses also need dynamic layout lowering. No interactive menu or
native completeness is established. Full receipts: research/rs-first-frame.md
and ignored target/receipts/rs-first-frame. No shared RT64 rebuild is needed.

## Native custom RSP overlays and unknown-GBI LLE (ADR-0274)

Packed RSP DMA descriptors now supply nonstandard ROM-derived IMEM
placements, passing Rogue Squadron's db0 refusal. Its first real graphics
task matches pinned ares after 2,694 instructions in all 331 RSP state words,
8 MiB RDRAM, IMEM and DMEM under equivalent DPC submission conditions.
Unknown GBI selects guarded native RSP LLE before HLE display-list effects;
raw RDP continues through RT64. Named CPU callbacks following terminal J,
absent-Pak probes and blocked SDK thread stop/restart are also covered.
A 30s request now stops at VI105/fault2/80884650 after48 graphics and53 audio
tasks; automatic LLE reproduces the stop. RDRAM framebuffer readback is black;
first-frame/gameplay acceptance remains open. This is finite coverage, not
native completeness. Detailed run,
framebuffer, controls, mutation and local-gate receipts are in
research/rs-rsp-ucode.md. Deploy the updated RT64 bridge DLL with the runtime;
the shared DLL was not rebuilt by this worker.


## SDK PI manager and SP task-load family (ADR-0273)

Full normalized PI-family identities now bind manager creation and DMA to the
existing runtime. Identical PI/SI queue helpers are disambiguated only through
the authenticated caller's exact call and shared globals. Missed yield and
SP-task-load variants also bind existing scheduler/RSP APIs. No jump-table
or native-target guard is relaxed; ordinary ambiguity refusals are retained.

Rogue Squadron identification rises from 25 to 32 runtime functions; residual
sites fall from 20 to 19, native_complete:false. The VI0/fault3/8002a2e4 PI
switch is passed. A silent visible 30-second request with native RSP graphics
stops at VI1, CPU fault0/PC00000000, 15 PI DMAs and the first graphics task,
on unlowered RSP entry db0. Readback is essentially black, with no title/menu.
The ordinary RT64 HLE path rejects the GBI and exits without stop JSON.
RSP placement/discovery is the next blocker. Synthetic matcher/PI contracts,
owner-guard mutation and required local/control acceptance receipts are
recorded in research/rs-pi-jumptable.md and the issue #4 closeout.

## SDK thread family and native entry dispatch (ADR-0272)

Relocation-normalized full-body SDK identities now bind Rogue Squadron's
create/start/message/priority APIs to the host scheduler, with verified peer
calls, shared globals and MI table contents. Identification rises from 14 to
25 functions. The failing `80025bf4` instruction is the standard-layout SDK
dispatcher's saved Status write; its differently compiled family was missed.
The existing Status/ERET guards remain. The newly exposed RAM-loaded thread
entry is an explicit residual site, dispatched only to emitted native code;
strict mode and unknown native-target refusals are tested. The manifest has
20 residual sites and `native_complete: false`.

The game passes dispatch and a second missed `osGetThreadPri(NULL)` getter.
Five SDK host threads are live at the later PI-manager switch refusal:
VI 0/fault 3/PC `8002a2e4`, computed target `8002a2ec`. No graphics/audio task,
PI transfer or rendered game frame/title/menu is reached. The switch has no
discovered candidates; recovering its base across calls/loop paths remains
open. A speculative message-call summary did not fix it and was removed.
Synthetic signature, strict/residual callback, scheduler saved-register/mask/
queue and native-entry mutation tests cover this change. Receipt:
research/rs-thread-dispatch.md; required controls and exact-tree local gate
are recorded in the ignored receipts and issue #4 closeout.

## Rogue Squadron cache boot clear (ADR-0271)

D-cache Create Dirty Exclusive now retains witnessed slot bytes, writes back a
conflicting dirty victim and allocates without a RAM fill. Unknown invalid-slot
bytes fault on reads until written; incomplete writeback marks RAM lost. Native
and pinned-ares memory/CPU contracts cover full writes, dirty victims, stale
bytes and hits. Native dirty state follows the NEC manual; pinned ares instead
clears its dirty mask on a miss until a store. This difference is explicit.

Rogue Squadron advances from CACHE at `8000041c` to raw SDK thread dispatch
Status restore at `80025bf4`: VI 0/fault 12, no first frame/title/menu. Thread
create/start identification and the Status/ERET scheduler contract remain open;
no guard was weakened. Nineteen residual sites and native_complete:false remain.
Receipt: research/rs-cache-cde.md; full local gate and silent visible controls
are recorded in the issue #4 closeout and ignored exact-tree receipts.

## Rogue Squadron residual build and infeasible paths (ADR-0270)

Rogue Squadron now emits a native residual-dispatch executable: 13 residual
blockers become zero, 50,862 decoded blocks become 47,866, and 19 transfer
sites remain explicitly residual (`native_complete: false`). Statically
untaken integer branches preserve link writes and ordinary delay slots;
likely slots are annulled. Calls into content-bound overlay slots no longer
decode the overlapping fallback window as another executable identity.
Undecodable alternate call entries remain solver obligations: strict mode
refuses them, residual dispatch accepts only lowered, byte-bound entries,
and selecting an omitted identity faults. This does not prove data sections.

A silent visible 30-second request stops before VI 1: fault 12 at
`0x8000041c`, CACHE Create Dirty Exclusive (`0xbd0d0000`), RA `0x80001eb0`.
There are no graphics/audio tasks or PI DMA, and no title/menu is reached.
This is an emitted build, not native gameplay acceptance. Native/ares branch
state comparison, alternate switching/refusal, missing-identity and guard
mutation tests are retained. Receipt: research/rs-blockers.md.

## Fresh catalog/replay declaration reconciliation (ADR-0269)

The ROM-alone MP2 pipeline now applies discovery's catalog text subtraction
before infer-call-loads compares declarations. Fresh and retained loads files
are identical; the old refusal compared a trimmed 0x1140 mapped slice with its
original 0x1360 replay declaration. Source-image reconstruction and exact stale
source/witness/range checks remain required, including refusal when a removed
declared catalog tries to authenticate itself. Synthetic normalization and guard
mutations fail as expected. From an empty output directory, a silent visible
30-second run with scripted Start/A reaches the explicit destination-selection
prompt: VI 1798, fault 0, fault_pc 00000000, graphics 2349/audio 1788. No supplied
--loads is needed. Eight residual sites remain, native_complete:false; board
gameplay and full closure are unverified. Receipt: research/mp2-fresh-analysis.md.

## Parked SDK thread and coroutine retirement (ADR-0268)

Thread destruction/recreation retires every owned host context, invalidates
its jump registrations and releases text pins before reuse. Acknowledgement
waits release the scheduler mutex; no host join holds the guest baton. MP2
passes the VI 520 deadlock and a silent visible 30-second Start/A run reaches
destination selection: VI 1798, fault 0, fault_pc 00000000, graphics 2351/audio
1788. Deterministic stopped/blocked recreation, live coroutine, self-destroy,
repeated reuse and mutation checks cover the lifetime rule. ADR-0269 resolves
the separately observed bare-pipeline declaration refusal. Eight residual
sites remain, with
native_complete:false. Receipt: research/mp2-thread-lifecycle.md.

## Catalog overlay binding over first-fetch replay text (ADR-0267)

Validated catalog text now supersedes overlapping fixed AresBoot text,
preserving the replay's other bytes and every runtime binding guard. MP2
passes the old VI 8/fault 8 entry and displays the HUDSON logo. Its 30-second
observation reaches VI 520, fault 0, fault_pc 00000000, RA 80016174, graphics
504/audio 514, then remains on black in an osCreateThread host-join deadlock.
It requires external termination; title/menu/gameplay acceptance remains open.
Core mutation and native/ares catalog-switch/refusal tests pass. Receipt:
research/mp2-overlay-binding.md. The build remains natively incomplete.

## Scissored RT64 fill clears (ADR-0266)

RT64's optimized fill-cycle GPU clears now intersect each call's scissor
and skip empty intersections. SF64's out-of-scissor stars no longer
accumulate tiled border garbage; the defect was also present in read-back
RDRAM and reproduced with a fresh build of the original shim. Synthetic
RGBA16/RGBA32 tests check all pixels, four edges, overlaps, touching and
empty scissors; removing the left clip is detected. Build/test instructions,
matched-input captures, six silent visible controls and the full local gate
are recorded in research/sf64-border.md. This does not establish full VI,
subpixel/field-mode accuracy or gameplay closure.

## OoT save-load boot and NJPEG (ADR-0265)

Pinned ares confirms the protection task's boot rewrite (268 instructions,
complete RAM/SP memory and checked RSP state agree). Discovery derives its
bounded self-DMA entry replacements and follows scalar task prologues to
RSP operations, adding both boot variants and NJPEG (41 -> 44 texts).
SDK RSP tasks now share the CPU DPC bus and advancing/resettable DPC clock.
The complete NJPEG task matches pinned ares after 9,668 instructions across
all 8 MiB RAM, both SP memories and checked RSP state. The save-load refusal
is passed: the same-press 60 s run reaches VI 3596, fault 0, fault_pc
00000000 (main stops at VI 1845). The opening Link/Kokiri scene is reached.
This is finite tested coverage, not complete gameplay or RSP closure.
See research/oot-jpeg-boot.md for final VI/fault/PC, controls and pacing.

## Code-built PI load descriptors (ADR-0264)

Load inference and overlay discovery recognize structurally connected
PI/RAM/size/end stores and place their bounded sources in content-bound
slots. Rogue Squadron Rev 1 now declares its three files at `0x800960e0`
and discovers 50,862 blocks (was 39,550), but its residual solve remains OPEN
with 13 blockers (was 5). The original false BLTZAL target and data at
`0x80096d50` remain, and alternate data introduces further blockers. No
native artifact is emitted; VI/fault/PC are unavailable before and after.
See research/descriptor-built-overlays.md for tests and control receipts.
The six fault-code controls match baseline. SF64 border garbage is a real
pre-existing rendering defect, reproduced on current main with VI/framebuffer
evidence in the receipt; visual acceptance remains open.

## Paper Mario regression fixed (ADR-0263)

ADR-0258 had replaced Paper Mario's validated `segment` slots with duplicate
catalog overlays (fault 3 at VI 2). Catalogs now supersede only inferred raw
slots and never re-declare a declared file.

## Structural native coroutine contract (ADR-0262)

Fixed-text word-layout setjmp/longjmp bodies are recognized structurally.
Caller-owned host jump buffers and per-SDK-thread host contexts preserve
creation, sleep/yield and exit continuations. Context-tagged registrations
release discarded fixed-text and overlay pins without touching other stacks.
The deterministic native/ares contract compares full architectural state and
64 KiB RAM; mutation, ownership, scheduler and refusal cases pass. Edited
entry values require residual-dispatch mode; this is not native completeness.
Mario Party 2 now passes its process switches and starts audio tasks; the
latest run reaches VI 8, fault 8 at overlay base 80102800. The previous
stop was VI 2, fault 5 at 80092e70. See research/native-coroutines.md for
the exact validation receipt and declared limits.

## Constant pairs stop at register rewrites (ADR-0261)

Load inference no longer pairs a `lui` with a low half after its register was
rewritten. Rogue Squadron's three stale loads are gone and its
residual-dispatch blockers fall from 140 to 5; its descriptor-built overlays
at `0x800960e0` are the next gap.

## Mario Party 2 reaches its process system (ADR-0260)

COP0 WatchLo is modelled while disarmed and `__osGetCause` is a runtime
function, so Mario Party 2 passes `osInitialize`. It now stops at VI 2 on
Hudson's `setjmp`/`longjmp` coroutine switch (fault 5).

## Lowered CACHE (ADR-0259)

`CACHE` lowers onto the modelled D-cache; I-cache forms are no-ops, and
discarding a dirty line fails closed. TagLo/TagHi are modelled for Index
Store Tag. Checked against pinned ares.

## Mario Party 2 overlays from its segment table (ADR-0258)

Mario Party 2 (USA) overlays are found from the linker segment table in its
main image: 116 overlays sharing `0x80102800`, bound by content at run time.
Residual-dispatch blockers fall from 301 to 3; the last three are `CACHE`
instructions, which lowering does not model yet.

## Star Fox 64 runs natively (ADR-0256, ADR-0257)

Star Fox 64 US Rev 1 builds from the ROM alone and runs the 30-second
validation with fault 0 (1798 VIs, 945 graphics tasks). Residual dispatch
now treats SP-memory targets as faults, libultra's development-board helpers
have runtime stubs, and catalog overlay verifiers relocate their pointer
tables, so the level overlays bind at `0x80187520`.

## GoldenEye mapped engine-page sources (ADR-0255)

The ROM-only pipeline now recovers 48 replay-authenticated 4 KiB engine pages
and reaches 9035 blocks (was 4706). Destinations for 81 of the original 85
missing direct edges are decoded; four still name 7f010290 or 7f08fe74.
Whole-map OPEN counts rise from 175/172 ordinary/residual to 592/589 as the
new code exposes more dependencies. Native emission remains refused.
Unsupported mapped call projection no longer blocks independent known-source
replays; it still supplies no call observations. Existing replay, source,
physical mapping, content and generation guards are unchanged. Research traces
the raw 8 KiB DMA page loader and copied TLBWR refill stub, separately from
the 1172 initialized-data stream. Unobserved sources, page-boundary instruction
coverage and exception/paging lifetimes remain open. See
research/mapped-page-source-recovery.md for concrete addresses and receipts.
Fresh baseline/expanded pipeline wall times were 274.641/196.988 s. The
baseline included a cold release build; replay caches and coverage differed,
so these are receipts, not a speedup comparison.


## SF64 DMA overlays (ADR-0252)

Generic overlay discovery now recognizes structurally validated virtual-to-physical DMA catalogs and scene descriptors, including MIO0-compressed overlays and raw files with catalog-bounded extents. The CC0 SF64 US Rev 1 decompilation was used as format evidence; no source was copied. Synthetic checks cover catalog extents and MIO0 bounds.

SF64 US Rev 1 moved from 296 blockers (294 with residual dispatch) to 8 before residual dispatch and 1 after, with 7 residual sites. The remaining residual blocker is the indirect candidate `0xa40000b0` from `0x8001efb8`. No native artifact was emitted. See ADR-0252 for the evidence and limitation.

## Native Windows ares oracle (ADR-0254)

Analysis-time ares replays run natively on Windows with MinGW instead of in
WSL; Banjo-Kazooie analysis outputs are byte-identical and replays are about
3x faster. `PLAID_ARES_WSL=1` keeps the old route.

## Ocarina of Time runs from the ROM alone (ADR-0253)

The RSP boot recognizer follows jumps and wrapped DMEM offsets, and short task
texts followed by data become candidates. Ocarina of Time (USA 1.2) builds with
0 blockers and runs 30 s: VI 1749, 660 graphics / 1275 audio tasks, fault 0.

## Rogue Squadron table/code overlap (ADR-0251)

Table snapshots that overlap decoded executable blocks no longer contribute
pointer candidates. Rogue Squadron Rev 1 residual blockers fell 184 -> 151
(17 sites); ordinary harvested blockers ended at 168 vs. 201 observed. The
map remains OPEN and native.py emitted no artifact. Banjo-Kazooie, Paper Mario
and Majora's Mask each built and ran headlessly for 30 seconds with fault 0
under `SDL_AUDIODRIVER=dummy`. See
`research/rogue-squadron-table-provenance.md` for evidence and remaining
blockers.

## GoldenEye first-use table data (ADR-0250)

The automatic ROM-only pipeline improves from OPEN 338/327 ordinary/residual
blockers to 175/172, with 4706 blocks. Ten replay-authenticated, nonexecutable
data slices replace packed boot bytes at later table sources; all 106 invalid
table-entry blockers disappear. A controlled mapped-text trim leaves blocker
counts unchanged, refuting it as the cause. All 85 missing direct destinations
are in the 7f engine range; their sources/paging, callbacks and COP0 effects
remain unresolved. Native emission is still refused; no GoldenEye run is
accepted. Replayed data is checked at its consuming native transfer after guest
initialization, and rechecked after writes. Closure and source gates remain.
See research/mapped-boot-text-extents.md and its local validation receipts.

## Faster analysis (ADR-0249)

`solve` (4.2 -> 2.65 s), discovery (16.8 -> 15.9 s) and each two-billion-
instruction ares harvest replay (77 -> 61 s) are faster with identical
outputs. Banjo-Kazooie first build: 282 s (was 296 s), of which the three harvest replays take 126 s (were about 144 s).

## Faster rebuilds (ADR-0248)

native.py reuses identify, discover and solve results for identical inputs.
Rebuilding Banjo-Kazooie after a runtime-only change takes 38 s (was 109 s),
with byte-identical outputs.

## Faster builds (ADR-0247)

Analysis-time ares replays are cached by their exact inputs and the oracle is
built at -O2. A Banjo-Kazooie build takes 335 s instead of 606 s, and 109 s
when rebuilt.

## Mario Kart 64 runs 60 s (ADR-0246)

Overlays also become candidates inside their resident microcode, and a
transfer whose delay slot is outside its text leaves instead of faulting.
Mario Kart 64 runs 60 s natively with compiled graphics microcode and audio:
VI 2762, 1270 graphics / 2635 audio tasks, fault 0.

## Saved-$ra returns (ADR-0244)

`jr rX` where rX is a copy of the entry `$ra` closes like `jr $ra`, with the
same run-time check. Mario Kart 64 needs two residual sites instead of four.

## RSP candidates all run again (ADR-0245)

All RSP candidates are lowered again; only one per group the task matcher
cannot tell apart is matched. Corrects ADR-0240, which dropped texts F-Zero X
needs.
F-Zero X with --rsp-gfx runs 20 s again (50 texts, VI 1166, fault 0); Banjo-Kazooie runs 30 s (45 texts, VI 1773, fault 0).

## Short table-named RSP overlays (ADR-0243)

Overlay-table entries of 64 bytes or more become RSP candidates when they are
all code with an RSP operation. Mario Kart 64 runs natively to VI 526 (224
graphics, 517 audio tasks) with compiled graphics microcode, then faults 3.

## Boot EntryHi (ADR-0242)

EntryHi is seeded from the pinned-ares boot replay and kept across runtime
calls. Mario Kart 64 passes startup: VI 2, 865 PI DMAs, one graphics task,
then an unlowered word of its ROM-derived graphics microcode.

## PIF terminate-boot (ADR-0241)

A natively lowered osInitialize may end the PIF boot handshake itself; the
runtime clears the command byte as pinned ares does. Mario Kart 64 now stops
later, at fault 12 (MFC0 EntryHi with unknown state) at 800d1c80.
## RSP candidate identity (ADR-0240)

ROM-derived RSP candidates are deduplicated by what the runtime compares
(IMEM base and reachable word values), keeping the larger text. Banjo-Kazooie
runs 60 s again: VI 3568, 1265 graphics / 1779 audio tasks, fault 0.

## COP1 control registers and Status.FR (ADR-0238)

Native Status writes already track FR correctly. CFC1/CTC1 and their HLE
__osSetFpcCsr equivalent now check CU1 independently of the map's FPR layout,
as pinned ares does. FPR operations retain fault 11 for real FR mismatches.
Both layouts match complete synthetic reference state across native FR
transitions; old-gate mutations fail. The first fresh visible MK64 compiled-RSP
build passes its old fault 11, then faults 1 at 800d1be8 writing PIF RAM
bfc007fc: VI/graphics/audio/PI DMA zero. It remains a four-site residual
validation artifact, with no rendered frame or gameplay acceptance.
See research/status-fr-control-registers.md for evidence and limitations.
## Continuation-only frame pins (ADR-0239)

Suspended native frames pin only the text reachable from their pending call's
link, so code that clears its own already-executed prefix no longer faults 2.
Majora's Mask is fixed: 60 s, VI 3563, 1243 graphics / 3530 audio tasks, fault 0.

## Bounded ERET and aligned executable loads (partial; ADR-0237)

ERET lowers with known explicit EPC/ErrorEPC and Status outside SDK contexts;
EXL/ERL selection and LLbit clearing match pinned ares. Event-enabling, unknown,
wide and SDK states fault 12. Strict solve retains return-target closure;
residual mode dispatches only to compiled targets. ISA is 204/209 (97.6%).
Lone-LUI aligned load destinations recover MK64's four missing functions and
four direct edges: 41631 blocks, ordinary OPEN/4, residual 0 with four sites.
Its visible RT64 validation build stops at VI 0, zero tasks, fault 11 at
800cc0f4; no gameplay is accepted. GoldenEye remains OPEN 339/327. BK/F-Zero X/MM
maps are byte-identical; separate native regression work is untouched.
See research/eret-lowering.md for the contract, measurements and limitations.
Production `0c4d9010` landed by exact-head CAS; all five gate steps passed
(320.5 s), with 910 Rust tests passed and one ignored.

## Mapped instruction sources (partial; ADR-0236)

Pinned reset replay now exports produced RAM at a unique global TLB virtual
link, including observed IPL producers. Composition replays and checks the
virtual/physical source; native bindings retain content, generation and frame
guards and require that physical backing. Mapped tail transfers discover their
unchanged slot text. GoldenEye expands 348 -> 3,716 blocks, resolving its old
mapped boot target, then exposes OPEN 341 ordinary / 331 residual blockers.
MK64 remains OPEN 13/10 with ERET and four missing targets. Both requested
60-second RT64 pipelines refuse before any native window or gameplay.
BK/F-Zero X/MM complete maps are byte-identical to ADR-0235 controls; separate
native regressions remain untouched. ISA stays 203/209. See
research/mapped-code-discovery.md for synthetic/reference/mutation gates,
timings and the open replay-projection/text/lifetime/overlap obligations.
Production `438a0c2d` landed by exact-head CAS after all five local gate
steps passed (321.6 s total); the full Rust suite ran 908 tests, one ignored.
Final GoldenEye/MK64 pipelines took 52.911/217.063 s and refused at analysis.

## Bounded native COP0 state (partial; ADR-0235)

Seven additional forms lower with checked kernel state: MFC0/DMFC0/MTC0/DMTC0,
TLBWI, TLBR and TLBP. Index, EntryHi/Lo, PageMask, Wired and bounded Status
match pinned ares; Status writes keep FR checks consistent. Unknown CP0 state,
unsupported modes, ASID-dependent commits and unmodeled event effects fault 12.
Native boot Status comes from the first post-IPL replay fetch. TLBWR/Random,
Count/Compare, Cause/EPC/ERET, CACHE, mapped instruction discovery and the
core-only boot evaluator remain open. This is a partial lowering milestone,
not a new game or whole-ROM completion claim. Validation and ROM receipts:
research/cop0-lowering.md.

Continuation on e9d1ccf0: ISA 196/209 -> 203/209; GoldenEye ordinary/residual
OPEN 1/1 and MK64 OPEN 13/10. Both requested 60-second RT64 pipelines refuse
before building; no native execution is claimed. BK/F-Zero X discovery maps
are byte-identical; MM's retained visible run reproduces its existing fault 2
at VI 0 with identical reported state. The 905-test Rust suite and complete
pinned runtime contracts are the integration gate; see the receipt above.

## Residual dispatch is the default build (ADR-0233)

`scripts/native.py` now builds whenever the only blockers left are unproven
indirect transfer sites; they dispatch at run time over the lowered entries and
fault 3 elsewhere. `--strict` keeps the CLOSED-only build. Every build writes
`native-manifest.json` (`mode`, `native_complete`, residual sites).

Sweep of seven local ROMs with the new default (2026-10-21, visible 60 s runs
where a build was emitted; details in `research/rom-sweep.md`):
Paper Mario builds by default and runs to VI 2908 (2875 graphics tasks, 2904
audio tasks), then faults 3 on an indirect call into an undiscovered occupant
of a shared slot. OoT is CLOSED and stops at ROM-derived RSP microcode it does
not find (VI 4). GoldenEye (7 blockers), Mario Kart 64 (27), Star Fox 64 (296)
and Rogue Squadron (225) still do not build: their blockers are COP0/TLB/ERET
code the solver's integer scope excludes, code never discovered, and table
proof gaps, not residual indirect sites. Mario Party 2 fails in `identify`.

## TLB host register effects (ADR-0231, partial)

Callee proofs can carry GPR requirements across the three explicitly supported
TLB host boundaries under the existing runtime ABI scope. Exact declaration
metadata joins the recomputed certificate; callbacks, guest clobbers, independent
entries and memory effects remain separate obligations. Synthetic table tests,
mutations and a native host-state contract cover the rule. Paper Mario still has
eight residual sites and native_complete: false: passing osMapTLB exposes another
guest overwrite, rather than closing its switch. See the frontier research note.

## Completed raw slot occupants (ADR-0230)

Paper Mario completes two visible, neutral-controller 60-second residual-validation
runs with fault 0. The fresh ROM-only pipeline reaches VI 3590, 3579 graphics
tasks, 3588 compiled audio tasks and 17696 PI DMAs. A separate visible executable
repeat reaches VI 3560, 3548 graphics tasks, 3557 audio tasks and 17602 PI DMAs,
exit 0. The window renders the Nintendo logos and opening storybook scene.
Captured stereo PCM is nonzero, peak 32121. This is finite intro validation;
full gameplay, audio/mixing accuracy and whole-ROM closure remain unestablished.

Harvest identifies complete PI-backed occupants by full content and completed
source effects even inside numerically covered raw slots. Same-source subranges
remain known; equal-prefix ambiguity, partial producers, overwritten generations,
stale cache bytes and ambiguous projections remain fail-closed. Slot order stays
stable as alternates append. Native frame/content/alias and boot-image guards
are unchanged. The map has 60454 blocks and eight residual sites; the artifact
continues to declare native_complete: false. Exact source/progress evidence,
synthetic mutations, unchanged retained-input BK/F-Zero X/MM discovery and local
gate receipts are in research/paper-mario-native-frontier.md.


## Switch candidates across incomplete predecessor paths (ADR-0229)

Paper Mario's visible residual-validation run passes the previous 80a08aa8 switch
stop and reaches VI 659, 646 graphics tasks, 657 compiled audio tasks and 7,314
PI DMAs. The next fault 3 is JALR a2 at map 80a06450 (runtime 802c6450), target
80240880. A repeated visible run confirms the same VI/graphics/DMA and fault,
with 656 audio tasks; captured PCM remains silent. native_complete is false.

Completed switch-table paths now retain source-bound candidate targets when
another predecessor defeats exhaustive closure. Incomplete evidence never
certifies closure. Function-call arrays retain their old all-path behavior.
The same rule recovers 5/4/5 distinct targets at the three slot switches and
13 blocks, without changing their residual status. Final BK/F-Zero X/MM maps
and verdicts equal exact-parent rediscovery. Synthetic tests, mutations, final
map/lowering comparisons and gate receipts are in the frontier research note.



## Relocated replay call coverage (ADR-0227)

Paper Mario's visible residual-validation run passes the relocated checksum call
and reaches VI 654, 642 graphics tasks, 652 compiled audio tasks and 7,314 PI
DMAs. It then stops fail-closed on an unresolved JR at map PC 80a08aa8 (runtime
802c8aa8). The repeated native run confirms the counters and stop; PCM remains
silent. This is still a native_complete: false validation artifact.

Harvest now projects call sites and targets through declared linked sources,
checks shared-slot bytes and aliases, rejects ambiguity, and bounds extended
call observation at 1B instruction calls/3600 VI. Snapshot capture retains its
100M contract. Observations do not certify target closure. Synthetic mutations,
parent-tree discovery comparisons, timing and the next stop are recorded in
research/paper-mario-native-frontier.md. Historical game maps are not fresh
current-tree closure evidence.

## Paper Mario after replay-entry validation (ADR-0226)

ADR-0226 is landed. A fresh visible residual-validation run passes the previous
observed-call fault and reaches VI 648, 637 graphics tasks, 646 compiled audio
tasks and 327 PI DMAs. It then stops fail-closed at a checksum-derived call
from relocated text whose target lacks dispatch-admission evidence. Captured
PCM is silent (peak zero); audio and gameplay acceptance remain unestablished.
The artifact is still native_complete: false. Exact gate timings, repeat-run
state and the relocation/replay-coverage diagnosis are in
research/paper-mario-native-frontier.md.

## PI DMA RSP sources (ADR-0225)

Boot harvest retains ROM-backed DMA ranges outside CPU images as RSP-only
search inputs. Externally named starts and recognized short task boots can
supply native RSP candidates; native byte guards and fail-closed unknown-task
handling remain mandatory. This adds no closure proof or native-complete claim.
See research/paper-mario-native-frontier.md for validation and ROM observations.


## Shared CPU/RSP executable-write policy (ADR-0219)

OoT type-4 startup patches eight bytes of its RSP boot program in RDRAM. The
same bytes were conservatively decoded as immutable base CPU text. Inactive
fixed text is now revocable through the shared CPU/device write gate, with
compiled-byte verification before subsequent execution. Active native frames,
including suspended threads and relocated overlays, remain protected; fixed
proof-bearing data remains immutable. Synthetic state matches pinned ares and
six policy mutations are caught. A fresh visible current-runtime OoT run passes
the write, confirms the patched RAM words, and stops at unlowered RSP IMEM
0x080: VI 3, CPU fault 0, no graphics or PCM. It is not audio accepted. See
research/rsp-from-rom.md. Full local gates pass (886 Rust tests; one ignored).
Visible audio controls pass for newly lowered SM64 and retained F-Zero/MM
artifacts; MM ran 60 seconds. Their retained scopes and compatible legacy DLL
pair do not establish fresh ROM-only closure. Solver maps and assumptions are
unchanged.

## Paper Mario closure work (ADR-0202 through ADR-0217)

The selected ROM remains scoped OPEN/7, with 56,851 blocks and 162 loads.
ROM-only indexed TLB/copy consumers identify 127 effect files and the shared
bridge. Guarded constant-cell tail dispatch closes the former effect-wrapper
frontier. Native TLB execution retains virtual PC/return addresses and distinct
physical backing, verifies source bytes, tracks mapping generations, and pins
active frames. Authored native state/checkpoints match pinned ares; remap,
write, protected-cell and overflow contracts pass. Remaining indexed dispatches
still prevent native emission. Scheduled pointer and constant-SLLV proofs now
have authored native/ares contracts and retained clobber counterexamples;
unchanged loop predicates now have an inductive proof and native reference
contracts. Inferred case-entry origins and candidate evidence now survive outer
discovery rounds; every incoming indirect case edge is checked while explicit,
address-taken and callback entries retain unknown-state barriers. Five sites
recover 84 candidate edges; extending the general bounded path search closes
one 56-entry dispatch. Bounded callee no-write proofs now preserve pending
table bases across direct guest calls, closing another 24-entry dispatch.
Standalone BREAK paths end at the existing checked abort boundary; this closes
a further five-entry dispatch without adding an assumption. Flag-value tracking now rejects overwritten guard booleans and prunes
contradictory zero/nonzero paths, exposing eight more blocks. Captured
pointer/flag values now survive calls with checked no-write effects in fixed
text or the same placed alternate, closing one five-entry dispatch. A bounded
low-word affine relation now proves paired index/byte-offset updates and closes
another five-entry dispatch. Fixed-text return sources require an exact checked
callee witness. Mapped callee effects now recheck unique declared linked/placed text and every
constant-cell tail target, retaining source cells, normal return witnesses and
path-local binding authority. Fresh discovery carries declared sources through
all proof rounds; two more dispatches close and expose 38 blocks. Reusing
successful callee effects within one immutable table walk closes another two
dispatches without raising resource limits. Target/GPR keys, source hashes,
binding identities and exact return witnesses are retained; each verifier
recomputes its own cache. Four semantic mutations are caught, and authored
repeated-call native state matches pinned ares. Save/restore,
stack-cell provenance, remaining predecessor paths and other pointer relations
still need proof. Frame-local SW/LW pointer reloads now have a source-rechecked
all-path allocation/SP proof; every intervening store or unknown call refuses.
The four authored native cases match pinned ares and five mutants are
caught. Fresh PM remains OPEN/7 with an identical ProgramMap (partial ADR-0217).
No Paper Mario native run is accepted. See research/stack-table-pointer.md,
research/table-effect-reuse.md,
research/mapped-callee-effects.md,
research/affine-table-index.md,
research/captured-callee-values.md,
research/branch-flag-feasibility.md,
research/checked-break-callee-paths.md,
research/callee-register-preservation.md,
research/table-path-budget.md,
research/derived-entry-discovery.md,
research/loop-table-dispatch.md,
research/scheduled-table-dispatch.md,
research/paper-mario-native-frontier.md and
research/native-tlb-executable-bindings.md.

## Remaining-ROM automatic pipeline sweep (2026-10-18)

The five additional local ROMs remain scoped OPEN at production commit
109f467: GoldenEye 7 blockers, Mario Kart 64 30, Paper Mario 164, Star Fox 64
298 and Rogue Squadron 210. Each automatic pipeline refuses native emission;
native gameplay/audio for these titles was not reached. This is a fresh
ROM-only test, with no supplied loads or symbol files. Finite native coverage
for SM64/OoT with extra inputs is distinct from the ROM-only BK/MM/F-Zero X
results. See research/remaining-roms-20261018.md for commands and diagnoses.

## Framebuffer readback and BK puzzle transitions (ADR-0201)

Completed RT64 color/depth readbacks now return to native CPU RAM through the
runtime's existing executable-write and cache-coherence guards. The fix covers
both graphics entry points and uses no game-specific values. Two visible
75-second BK runs finish with fault 0; title and new-game puzzle transitions
show colored piece interiors. Synthetic coverage includes cache aliases,
invalidation, same-value transfers, exact byte spans and refused writes.
See research/native-framebuffer-readback.md for evidence and limits.

## BK native startup and guest VI (ADR-0195 through ADR-0200)

The ROM-only BK pipeline is now scoped **CLOSED/0** with 80,850 blocks and
41 ROM-derived RSP texts. A visible 60-second audio-required run reaches VI
3578, 1270 graphics tasks, 1785 audio tasks and 3750 PI transfers, fault 0,
PCM peak 32767. Separate inspection confirms the Nintendo opening's blue
background/sun/lens flare and Banjo's forest/waterfall backdrop are restored.

Verified Status/global bindings, per-context interrupt masks, native SI/Joybus,
post-IPL SP state, the EEPROM timer queue and image-word pointer discovery
complete the scoped bring-up prerequisites. The game's VI manager now executes
as guest code against modeled VI registers; Compare and the core scheduler
remain runtime boundaries. The graphics defect came from missing IPL3-written
RDRAM in the first 0x400 bytes, causing the guest to choose fallback clip
distances. The builder now preserves that bounded startup-data prefix.

This is finite native execution and visual coverage, not full gameplay,
pixel-perfect rendering, verified mixing or whole-ROM completion. No assumption
is retired. The current compiled-RSP graphics probe separately faults on its
first task; the accepted BK run uses RT64 display-list rendering with compiled
RSP audio. See research/native-bk-status.md and research/native-bk-graphics.md.

The prerequisite reports below describe the earlier states they established.

## SDK scalar address evidence (ADR-0194)

Identification retains optional per-function `data_bindings` for verified
adjacent LUI plus ADDIU/ORI/LW/SW references. Every use and surviving signature
variant must agree; unsupported or conflicting evidence supplies no binding.
Separate SDK copies retain separate globals. These are address references,
not verified global contents or a runtime mask implementation. Discovery still
consumes the original declaration fields; BK remains scoped OPEN/1.

## Interrupt restore prerequisite (ADR-0193)

`__osRestoreInt(0)` preserves an already-enabled IE bit. A retained synthetic
test reproduces the old assignment bug and compares nested/repeated restores,
preserved ABI registers and RAM with pinned ares. Full Status/mask/thread
semantics remain unverified; BK stays scoped OPEN/1.

## BK paired executable slot catalog (partial; ADR-0192)

Review hardening rejects conflicting source initializers, partial matches of
longer segment tables and malformed metadata arithmetic. Six retained Rust
regressions cover these failures; the primary receipt is
`research/integration-receipts/20261017-paired-slot-primary.md`.

The ROM-only path now derives 13 executable files sharing 80385610 from a
constant-initialized physical source catalog and a matching segment table.
The 1172 paired-stream boundary supplies text/data sizes; data remains readable
for tables but is excluded from instruction discovery. Existing content-verified
bindings and native-frame pins apply. BK improves **29 -> 1 scoped blocker**:
the remaining MFC0 Status at 80259d30 is the unsupported SDK __osGetSR helper.
Seven data-word effects, seven invalid candidates, seven missing targets and
seven direct edges are resolved. Native lowering and gameplay/audio remain
unreached; VI, fault/PC and PCM are unmeasured. No assumption is retired.
The full receipt, controls and local gate are in `research/rom-sweep.md`.

## BK SDK identification and boot harvest (partial; ADR-0190/0191)

The ROM-only pipeline replays pinned ares at analysis time, preserving PI/CPU
provenance and native executable-byte guards. Independent SDK copies now have
separate signature symbol namespaces across supplied-image holes, while
preserving whole-image identification evidence. Constant-return
stub lookalikes remain guest code. BK improves **72 -> 29 scoped blockers**:
one unsupported Status read, seven invalid/data-shaped candidates counted in
two classes, and seven missing targets plus seven direct edges. Exception-handler
and jump-table indirect blockers are resolved; 32,192 blocks, 87 runtime IDs.

A 500-million-call no-input experiment reaches analysis VI 676 without fetching
the seven missing targets; this does not prove input dependence. The production
100-million-call profile is unchanged. BK still refuses before native lowering;
native VI, fault/PC and PCM are unmeasured. Paper Mario improves 204 -> 164 after
SDK identification and three additional replayed loads. No assumption is retired.
See `research/rom-sweep.md` for the six-ROM sweep, control maps and local gate.

## ROM-derived RSP native dispatch (ADR-0188)

The default native build derives and lowers RSP microcode from ROM images;
snapshots are oracle-only. Startup requires a unique direct-reachable entry
match. Every executed word remains guarded against current IMEM, including
indirect targets and fallthrough. Visible timed ROM-only runs pass with audio
and fault 0 for F-Zero X (native graphics, 20 s), SM64 (20 s) and MM (60 s).
This removes the snapshot hand input on those paths; whole-ROM closure and the
general RSP-policy proof remain open. See research/rsp-from-rom.md for counters,
OoT's separately reported result and the full gate receipt.

Last updated 2026-10-17. This page is the current state in one screen. The
per-cluster history it replaces (spikes 001-095, every receipt summary) is
preserved verbatim in [`STATUS-LOG.md`](STATUS-LOG.md). Priorities live in
[`NEXT.md`](NEXT.md); decisions in [`DECISIONS.md`](DECISIONS.md).

**Summary:** SM64 is CLOSED under the declared address-taken scope and runs
natively with RT64 graphics, input, EEPROM saves and live native RSP audio
(ADR-0153..0170). Three runtime function names still use a reference map
(ADR-0171). Whole-ROM closure without assumptions remains unproved.

OoT's fixed image is **CLOSED** under the address-taken scope: 29,542 blocks
and 0 blockers (ADR-0175). This needed three fixes:
- address-taken roots come from the decoded contents of Yaz0 streams, not
  their compressed bytes;
- the cartridge's 64DD driver segment is a declared load;
- `osYieldThread` is a runtime function.

It lowers to C and compiles in 31 s. Natively, with its RSP task as lowered
microcode, boot runs to its first game-state overlay and stops fail-closed
there (ADR-0176). It uses no symbol map. CPU access to SP memory and the PI
is modelled as hardware, so unnamed library variants work (ADR-0177).
`discover --overlays` adds the 468 executable overlays at their link addresses
(ADR-0179). With jump-table bounds proven over every path (ADR-0180), OoT
with all 468 overlays is **CLOSED** under the address-taken scope: 154,414
blocks, 0 blockers; whole-ROM without assumptions it has 16,239 blockers.
Overlays are lowered at their link addresses and run through a run-time
binding that verifies the relocated bytes in RAM (ADR-0181): natively, OoT
runs through its relocated overlays, and with RT64, its own lowered audio
microcode and SRAM saves it draws the boot logo, title and file select
(ADR-0182).

`scripts/native.py <rom>` takes a ROM to a native executable with no
per-game input (ADR-0183). It infers the code segments from the ROM's file
table and its boot stub, identifies the runtime, and refuses to build
unless the address-taken scope is CLOSED. Majora's Mask went through it
untouched: it is CLOSED, and natively with RT64 it plays its intro and the
Clock Town attract scene. This needed an exact VR4300 D-cache model,
FlashRAM, and four general closure fixes. With native-frame-pinned overlay
bindings (ADR-0187), an erased-FlashRAM startup now passes the former heap-overlay
fault at VI 3188 and reaches VI 5358 in a visible 90-second run, with no fault.
Overlay loader lifetimes remain assumed; no assumption is retired.

MM audio is restored (ADR-0189): lowered RSP C shares the host's state header,
and task completion must halt before capture acceptance. A visible 60-second
run produces PCM peak 32569; SM64 remains audible at peak 28116. A real MM
audio task matches pinned ares in all captured state and memory. Native
validation can require non-silent PCM with `--require-audio`.

F-Zero X's shared executable slots now have separate, content-checked
alternates (ADR-0185). From the ROM alone it discovers 27,621 blocks and is
CLOSED under the address-taken scope, with zero scoped blockers. A synthetic
overwrite-and-rebind sequence matches pinned ares; tampered and ambiguous
text fault. With native graphics microcode and RT64 raw RDP output
(ADR-0186), it runs through a race with vehicle markings and shading,
input, saves and audio.
Visible 65-second runs have no runtime fault; the build and launcher are
reproducible with `native.py --rt64 --rsp-gfx`. Whole-ROM remains OPEN
with 2,995 blockers; the scoped result still has 14 assumptions.

## By layer

| Layer | State | Main gap | Evidence |
| --- | --- | --- | --- |
| Discovery (ROM -> ProgramMap) | ROM normalization, direct CFG, local and cross-block indirect proofs, function partitioning and return certificates (ADR-0127), trace import, conflict-aware merge | Jump tables beyond the bounded recognizer; overlays and DMA | `crates/plaid-core/tests/`, `crates/plaid-lower/tests/` |
| Closure proof (solver) | Fail-closed whole-ROM solver; assumption scopes `DeclaredStaticImages` and `DeclaredStaticImagesGuardedRam` reach CLOSED for synthetic programs | Whole-ROM closure without assumptions remains open | `crates/plaid-core/tests/core/pipeline.rs`, ADR-0126 |
| Executable provenance | PI/SP/PIF/cache/TLB/RSP byte lineage over pinned ares histories; 20M-fetch commercial boot prefix measured (its raw local traces were deleted on 2026-10-21; rerun the capture to regenerate them) | Paused by ADR-0125 until a milestone needs it | [`STATUS-LOG.md`](STATUS-LOG.md) |
| Native lowering | CLOSED map -> C; integer, COP1, checked calls/returns and native RSP scalar/vector code | Remaining system instructions | spikes096/097/098; ADR-0157..0169 |
| Runtime and rendering | Plaid runtime + RT64: threads, timing, input, saves, native RSP audio and graphics tasks | Runtime ABI/timing assumptions, additional devices and non-Windows hosts | `runtime/test_runtime.py`; ADR-0158..0186 |

## Real-ROM numbers

| ROM (local, never committed) | Result |
| --- | --- |
| Ocarina of Time US 1.2, conditional window `0x1000..0x101000` at `0x80000400` | 293 blocks, 45 indirect sites, **62 whole-ROM blockers** (44 unresolved indirect sites, 8 unsupported instructions, 4 other site-level blockers, 6 global model obligations). 43 of the 44 unresolved indirect sites are returns with ADR-0127 certificates, which count only in the assumption scope. Under `--guarded-ram`: **82 blockers**, 69 of them libultra system instructions (ADR-0128). With heuristic runtime declarations and the `osCreateThread` callback (ADR-0129/0130): **628 blocks, 6 blockers** after COP1 moves and guarded jump tables (ADR-0131/0132). With n64sym-identified declarations (ADR-0133, 39 functions): **320 blocks, 16 blockers** after unaligned access and COP1 compares (ADR-0134/0135): in boot code only the host return and one pointer call. With the Yaz0 `code` segment declared as a load (ADR-0136): **7451 blocks, 566 blockers** after `BREAK` became a checked abort (ADR-0138), then **42 blockers** after COP1 arithmetic, conversions and FCSR access (ADR-0139). Recognizing GCC's scheduled jump-table shapes (ADR-0140) closes all 12 remaining tables and extends discovery to **8082 blocks, 31 blockers**: 22 unresolved indirect sites (9 `jalr s4` output callbacks in one `_Printf`-shaped function, 12 struct function-pointer calls, the boot return), 4 unresolved direct targets, 3 unmapped targets, one `COP0` and one `CACHE` instruction. Identifying runtime functions over the composite image as well (ADR-0141, 59 functions) leaves **7684 blocks, 29 blockers**: the 22 indirect sites and 7 calls into the 64DD driver segment at `0x801c7740..`, each behind a "64DD present" flag test. No instruction-scope blocker remains. A points-to census for the 21 function-pointer `jalr` sites is recorded as unsound; they stay open (ADR-0142). Host-entry returns (ADR-0146) remove the boot return: **28 blockers**, the 21 function-pointer sites and 7 calls into the 64DD driver, which is not on the cartridge |
| Super Mario 64 USA, main segment `0x1000..0xf5580` at `0x80246000`, plus the engine and goddard segments as declared loads | Decomp-map identification (ADR-0148, 54 functions), forwarded callbacks (ADR-0149) and disjoint loads (ADR-0150): IDO slot-bound jump tables (ADR-0151): **5580 blocks, 523 indirect sites, 10 guarded blockers**: 7 render and geo callbacks, the level command table, 1 audio dispatch and the goddard vblank pointer. With `--data-roots` (ADR-0152): 47976 blocks and milestone 2 recall **99.03%** (3795/3832), which **meets the target** against the matching decomp map. Under the address-taken scope (ADR-0153..0156): 45419 blocks, 1341 address-taken functions, **`closed`** with 0 blockers (milestone 3; closed under declared assumptions, not whole-ROM). Lowered with `lower-map` and linked with Plaid's runtime (ADR-0159, FR = 0 per ADR-0160), it runs natively without a fault and, through RT64 (ADR-0163), **boots to its title screen** and, with input (ADR-0164), into gameplay at full speed (59.9 VI/s, ADR-0166); EEPROM saves persist (ADR-0165); its audio tasks run the game's own RSP microcode lowered to C, from two IMEM snapshots found by running it, and match ares exactly (ADR-0167..0169, spike098), and play live through SDL with AI DMA timing (ADR-0170) (`research/sm64-first-measurement.md`) |
| Mario Party 2 USA, window `0x1000..0x101000` at `0x80000400` | 51 n64sym-identified runtime functions; 712 blocks, 92 indirect sites; under `--guarded-ram` **29 blockers**: 27 libultra system instructions behind an `osInitialize` whose SDK build n64sym lacks, and 2 memory-loaded function-pointer calls (ADR-0148, `research/mario-party-2-boot-window.md`). `identify --symbols` can name runtime functions from a reference map instead |
| Commercial ROMs CLOSED without assumptions | **0**; SM64 is CLOSED under the declared address-taken scope |

Reproduce the OoT numbers with `plaid discover <rom> 0x1000 0x80000400
0x100000 0x80000400 map.json`, then `plaid solve <rom> map.json`.

## Native lowering subset (spike096)

Matches the pinned ares interpreter exactly (all GPRs, HI, LO, a 256-byte RAM
window) on eleven synthetic programs (also comparing all 32 FPRs):

- ALU and shifts: `LUI ORI ADDIU ANDI XORI SLTI SLTIU ADDU SUBU AND OR XOR NOR SLT SLTU SLL SRL SRA SLLV SRLV SRAV`
- HI/LO: `MULT MULTU DIV DIVU MFHI MFLO MTHI MTLO`, including divide-by-zero and INT_MIN/-1
- 64-bit: `DADD DADDU DSUB DSUBU DADDI DADDIU DSLL DSRL DSRA DSLL32 DSRL32 DSRA32 DSLLV DSRLV DSRAV DMULT DMULTU DDIV DDIVU LD SD`, plus trapping `ADD ADDI SUB` with an overflow check
- Memory: `LB LBU LH LHU LW LWU SB SH SW` through KSEG0 and KSEG1, and the unaligned `LWL LWR LDL LDR SWL SWR SDL SDR` (ADR-0134)
- COP1 data moves (FR = 1): `MFC1 DMFC1 MTC1 DMTC1 LWC1 LDC1 SWC1 SDC1`; all 32 `C.cond.S/D` compares and `BC1F BC1T BC1FL BC1TL`, with NaN operands faulting 7 (ADR-0135)
- COP1 arithmetic (ADR-0139): `ADD SUB MUL DIV SQRT ABS MOV NEG` in `.S` and `.D`, `CVT.S` from D/W/L, `CVT.D` from S/W/L, `CVT/ROUND/TRUNC/CEIL/FLOOR` to W and L from S/D (ADR-0143), `CFC1 CTC1`, with FCSR rounding modes, cause and sticky flags and FS flushing as pinned ares
- System (ADR-0145): `LL LLD SC SCD` with an exact LLbit, `SYNC`, and the twelve conditional traps checked as never taken
- Control: `BEQ BNE BLEZ BGTZ BLTZ BGEZ J JAL JR JALR BLTZAL BGEZAL` and the branch-likely forms, with delay slots; indirect jumps only over proven targets, including bounded jump tables in GCC's scheduled shapes (ADR-0132/0140); nested, recursive, pointer and tail calls with checked returns

Anything else rejects the whole program. A store into executable bytes (fault
2) or cached and uncached access to the same 16-byte line (fault 4, because the
write-back D-cache makes the result state-dependent) aborts instead of
executing, as does a return whose `$ra` is not its call's continuation (fault 5) or an
overflowing trapping add (fault 6) a COP1 operation outside the modeled subset: a NaN or subnormal operand, an out-of-range conversion or an enabled FPU exception (fault 7), entry into a declared load whose bytes are not in RAM (fault 8), a reached `BREAK` (fault 9), or a taken conditional trap (fault 10).

## Residual-dispatch validation mode (ADR-0218)

An explicit opt-in `--residual-dispatch` mode relaxes only the unresolved
indirect-site blocker for native validation runs. Its artifacts and manifest are
`native_complete: false` and are never accepted as fully native; the default
path is unchanged. The first Paper Mario run closes with 0 blockers and 7
residual sites, builds, and faults 3 at a site whose computed target is code
absent from every lowered entry (VI 1, 1 gfx task, 0 audio tasks).
With boot text capture (ADR-0220) the run closes with 0 blockers and 8 residual
sites, passes the boot stub (154 PI DMAs, 11 threads) and faults 3 at a
checksum-computed call whose target function discovery never reached.
With observed call targets as discovery roots (ADR-0222) it passes that check
(235 PI DMAs) and faults 3 at a residual switch whose known case labels the
residual dispatch does not include. With residual candidate dispatch and PI
DMA into TLB-mapped buffers (ADR-0223, ADR-0224) it reaches VI 3 and its
first audio task, then stops on audio RSP microcode that ROM-derived
extraction has not found (CPU fault 0).
ADR-0226 validates replay-observed call entries without a return-layout clue
only when they pass `executed_start`; solver dispatch requires that replay
evidence, and observations remain open-site evidence rather than certificates.
