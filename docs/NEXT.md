# Next

## After SDK runnable queue publication (ADR-0306)

Authenticate the lowered dispatcher restore continuation, then implement the
checked foreign ERET handoff to the owned blocked host receive. Preserve the
refill owner's suspended frames, exception scope and thread/context generation,
then restore it through authenticated lowered code after paging. GoldenEye
remains VI1/fault12/PC80810a7c; no logo/title is verified. Runnable-list
publication now exists, but guest list edits are not host scheduling authority.
See research/ge-sdk-run-queue.md and ge-native-fault-event-bridge.md.

## After SDK waiter/context publication (ADR-0305)

Bridge the lowered dispatcher's foreign ERET to an owned suspended native
queue continuation, then resume the original refill owner after paging.
GoldenEye reaches VI1/fault12/PC80810a7c. The ABI return PC is not permission
to skip the pending host receive. Preserve exception scope, context generation,
retirement and source/frame guards. Run-queue synchronization and authenticated
restore entry discovery remain necessary; no title/logo has been verified.
See research/ge-sdk-waiters.md and ge-native-fault-event-bridge.md.

## After guest SDK event publication (ADR-0304)

Publish blocked waiter and run-queue state under verified SDK bindings, then
bridge guest dispatch to owned native contexts. GoldenEye's lowered fault
sender now queues the real message, but host thread5 remains blocked because
its guest waiter link is absent. Preserve exception/context generation and
native-frame ownership while the pager runs and the original fault resumes.
The current stop is VI1/fault12/PC80810950. See ge-sdk-event-state.md and
ge-native-fault-event-bridge.md; no logo/title is verified.

## After native MI mask access (ADR-0303)

Bridge source-verified SDK event registration, fault queues and dispatch to
the native host scheduler. Preserve exception ownership and suspended native
frames while another thread runs the pager, then resume through checked guest
state and mapping/source guards. GoldenEye currently stops at
VI1/fault12/PC80810950. The natural pinned-ares fault path and pager selection
are recorded in ge-native-fault-event-bridge.md; no logo/title is verified.

## After verified guest TLB address-exception state (ADR-0299)

Connect authenticated lowered vectors and checked ERET retries to real native
translation failures, retaining source/mapping/generation/frame protections.
Establish CP0 provenance across SDK calls and context switches, plus Random/Wired
selection. GoldenEye needs both the fast and general handlers: the first fast
refill intentionally installs invalid EntryLo0=1/EntryLo1=41, and demand paging
precedes the final d01f/d05f pair (physical340000/341000). Never preload that mapping.
The state helper alone does not advance native execution. See ge-native-refill.md.


## After mapped host ABI callback obligations (ADR-0298)

The next stop is the unmapped engine fetch7f000bd0 at VI0/fault3/PC80805d58.
Authenticate and discover the guest refill vector, model native fetch-miss
Context/BadVPN/EPC/Cause provenance and checked return, then establish
Random/Wired timing and CP0 preservation across host ABIs independently.
The initializer writes Wired=2; an ares sample is not a hardware clock proof.
Preserve unknown-state refusals and all source/mapping/native-frame protections.
Do not preload captured mappings or add a guest execution fallback. Receipt:
research/ge-mapped-abi-callbacks.md. No logo/title is verified.

## After bounded Context writes (ADR-0297)

Preserve GoldenEye execution past the MTC0 Context stop without inventing read-only BadVPN
or exception state. Preserve the unknown-read refusal. Establish native refill
entry, EPC/Cause/BadVAddr provenance and Random/Wired timing independently as
measured execution requires. Continue from the mapped-fetch refusal above. Receipt: research/ge-context.md.


## GoldenEye after independent mapped lifetimes (ADR-0296)

Preserve full natural captures, agreeing virtual/physical offsets, independent
source guards and proof-consumer grouping. The next measured stop is
VI1/fault12/PC80801bbc, an MTC0 to Context(reg4), RA70000614. Establish the PTEBase
write and read-only BadVPN provenance independently before admitting Context
reads; do not invent reset or exception state. General refill/exception delivery
and Random/Wired timing remain unverified. There is no initialized VI/framebuffer
or graphics/audio task, and no logo/title claim. See ge-mapped-fragments.md.


## GoldenEye after native alias ownership (ADR-0294)

Preserve both fixed and mapped source owners, immutable proof data, native frame
pins, complete-write preflight and source verification. Keep independent
fixed-text comparisons and heap-copy overlap refusal. The first binding now
passes; the next stop is VI0-1/fault2/PC80920a04, byte store800411c0 during
decompression. The whole large raw mapped fragment pins code candidates that
the live continuation need not execute. Investigate independently authenticated
page sources with general cross-page verifiers instead of suppressing stores
or treating copied/decompressed bytes as permanently executable.

Zero ordinary blockers/five residual sites remain unchanged; general refill
Random/Context/exception and RSP source obligations still apply. Evidence:
research/ge-source-aliases.md.
## GoldenEye after native Windows oracles (ADR-0295)

Supported reference gates now execute natively without WSL. The retained mapped
fragment experiment a8bd4513 is integrated as ADR-0296 with its source guards
and residual dispatch scope preserved.

## GoldenEye after authenticated startup data (ADR-0293)

Preserve the full entry-time ROM-copy verification independently of discovery's
BSS bound. The startup fragment now verifies all288 ranges, but binding still
refuses existing fixed-source protection at physical0xb6ac/tag2 (1678 overlapping
words total). Design a general alias-ownership contract that preserves both
source witnesses, immutable proof data, fixed/mapped native frame pins, atomic
refusal and revocation. Do not erase an existing protection tag to admit a
mapped alias. Recheck VI/fault/PC and RDRAM after that contract is verified.
Receipt: research/ge-boot-rom-copy.md.

## GoldenEye after first native emission (ADRs-0289–0292)

Preserve the residual manifest and guarded TLBWR scope. The first executable
stops at VI0/fault3/PC800004b4 entering virtual70000510, with no initialized VI
or framebuffer. Diagnose mapping, source-byte verification and protected-source
ownership at that transfer using stop-state and RDRAM evidence. Do not suppress
the refusal, preload a permanent mapping or substitute a counterfactual state.

Then continue toward verified native VI/graphics. Five residual sites remain;
Wired=2 Random timing, Context/EPC/exception delivery and RSP source discovery
remain separate obligations. Keep all control CPU/runtime objects fresh after
the fixed-load state-layout expansion. Receipt: research/ge-first-native.md.

## GoldenEye after independent native delay slots (ADR-0288)

Preserve separate slot source identities, mapping/content/generation checks,
balanced source pins, architectural PC+8 and likely annulment. The unchanged
227-page frontier has 49,241 blocks, one TLBWR blocker and five recorded residual
transfer sites. Emission remains refused.

Verify the real guest refill routine's Random/Wired selection, Context/EPC and
exception entry. Pinned ares's sampled replacement index does not establish a
hardware instruction clock. Wired=31 has a timing-independent singleton domain;
unknown or wider domains must remain unknown until modeled and verified. Do not
guess an index to remove the static blocker. Continue with a bounded native
contract, then obtain VI/fault/PC from the stop JSON and inspect RDRAM readbacks.
Evidence: research/ge-independent-delay.md.

## GoldenEye after mapped runtime closure (ADR-0287)

Preserve virtual callback pointers, complete source identities and native
mapping/content/generation checks. Mapped host calls require their whole declared
guest source pinned before effects; they must never become guest-code roots.
The fixed 227-page source set now has 49,241 blocks and 44 residual blockers:
43 independent delay-slot fetches and one TLBWR. Emission is still refused.

Finish the independent delay-fetch representation, native source guards and
dataflow contracts, including memory effects and negative/mutation cases. The
TLBWR belongs to a real Context-based refill handler with Wired setup. Verify
Random/Wired, exception entry, Context/EPC and refill execution without selecting
an arbitrary replacement index or inventing a permanent page mapping. Source
discovery is already productized by ADR-0282; counterfactual roots still do not
prove neutral execution or target closure. Evidence: research/ge-mapped-runtime.md.

## GoldenEye after source-bounded call admission (ADR-0286)

Preserve separate source identity when checking a call-entry prefix. The fixed
222-page frontier improves109->85; its direct/unmapped buckets are12/10.
Separate production refill/table convergence expands to227 verified engine pages
and49305 blocks with59 blockers:43 independent delay-slot fetches,8 decoded
host-runtime entries,7 callbacks and1 TLBWR. No direct/unmapped/table/indirect
blockers remain in that expanded map. Expansion is not part of109->85.

Guard mapped callback sources and stop rooting declared host entries as guest
bodies through general native contracts. Independent delay-slot source guards
and dataflow, plus Random/Wired/refill/exception semantics, remain prerequisites
for an accepted executable. Evidence:research/ge-entry-prefix.md.

## GoldenEye after source-aware return closure (ADR-0285)

Keep caller source identity and architectural PC+8 distinct from analysis
allocation. Fixed-source residual blockers improve124->109 without changing
47161 decoded blocks or the222 engine-page declarations. Five remaining
indirect-target blockers at one table still name stale aligned snapshot words.
Cross-fragment slots42, direct37, unmapped9, runtime-body8, callbacks7 and TLBWR1
remain. No accepted executable or native VI/logo/title.

The direct-target bucket includes a call-entry heuristic that scans neighboring
analysis storage after its own fragment ends. An isolated candidate has a
baseline-red synthetic proof and preserves rejection of a reserved word within
the real prefix; it is separate from this landing. Three additional verified
refill sources likewise remain a separate frontier measurement. Continue
independent slot-fetch representation/guards and refill/Random/Wired/exception
semantics without admitting counterfactual reachability or guest execution.
Evidence:research/ge-return-continuations.md.

## GoldenEye after aligned first-use table repair (ADR-0284)

Preserve neutral data-only replay, complete PC/image/generation selection and
same-site table evidence. The fixed222-page frontier improves196->124 residual
blockers; aligned instruction words must not masquerade as initialized tables.
The remaining20 indirect-target obligations include return certificates that
still construct source-boundary continuations from analysis PC+8. An isolated
candidate verifies architectural continuations and independently placed JAL/JALR
sources; it is not part of this landing. Further verified refill probes recover
new pages separately, without a source formula.

Cross-fragment delay slots remain42: current raw-source classification finds7
NOPs,29 ordinary instructions,5 non-raw sources and1 missing slot source. Model
independent fetch identity/guards and all instruction effects across discovery,
proof/dataflow and lowering before admission. Direct37, source9, runtime-body8,
callbacks7 and Random-dependent TLBWR1 remain. No executable or native VI/logo/title.
Evidence:research/ge-table-snapshots.md; later source rounds require fresh counts.

## GoldenEye after sequential fragment continuations (ADR-0283)

Preserve architectural advancement/RA and independently guarded native tail
continuations. The fixed222-page source set improves432->202 residual blockers,
with no load straddles and only2 unmapped targets. Continue first-use table repair
and source convergence, then represent the42 cross-fragment delay slots with
separate byte identities and guards. Do not borrow neighboring storage or fallback
ROM words. Remaining direct30, indirect91, table21, runtime-body8, callbacks7 and
TLBWR1 require general source/closure or execution capabilities. Keep Random/Wired,
refill/exception delivery and timing unknown until reference contracts establish
them. No accepted GoldenEye executable or native VI/logo/title yet.
Evidence:research/ge-continuations.md.

## GoldenEye after verified refill sources (ADR-0282)

Preserve separate counterfactual/neutral protocols, actual ROM-read and completed
producer verification, and native mapping/content/generation guards. Continue
source convergence and first-use table repair; coverage growth exposes new
obligations and is not an aggregate closure certificate. The first49-page batch
reduces unmapped targets317->231 but exposes1391 residual blockers. Categorize
the converged map before choosing each reduction. Sequential PCs/continuations
and delay slots must cross virtual fragments without assuming adjacent storage
or physical pages. TLBWR/Random/Wired, refill/exception execution, callbacks and
tables remain open. No GoldenEye executable/logo/title is yet accepted.
The standalone MM control returns1798VIs/30s/fault0; retain quiet independent
timing comparisons before attributing previous variation to a code regression.
Evidence:research/ge-closure.md.

## GoldenEye mapped-code continuation (ADR-0281)

Preserve architectural relative targets and guarded cross-fragment native
dispatch. The fixed48-page direct-target challenge improves331->317; expanded
coverage reaches55 pages/11633 blocks and909/903 ordinary/residual blockers at
the16-attempt pipeline cap. Emission remains refused. Recover unvisited bytes
from a decoded general loader relation without extrapolating the observed ROM
offset into a game-specific rule. Model cross-page slots/continuations without
merging independent physical bindings. Verify TLBWR/Random/Wired, Context/refill/
exception entry and mapping lifetimes against pinned ares; retain source/table/
callback guards. No GoldenEye native VI/logo/title exists. Evidence and control
receipts:research/ge-blockers.md.

## Rogue Squadron after name entry and first mission (ADR-0280)

Preserve live guarded FPR selection for unknown entry/call/join facts, proven-FR
checks, canonical FPR storage, CU1 refusals and all reference/mutation contracts.
PC-relative shared-tail roots remain bounded source-derived candidates; stale map
membership, unknown-condition links and captured targets must not authorize them.
Native completeness remains false with16 residual CPU sites.

The retained-save new-pilot route now reaches the first mission's playable HUD:
VI12284/fault0/PC00000000 in205s. Continue flight, combat, mission completion,
later overlays and longer save/load paths; do not infer them from the initial HUD.
The exact Start/D-right/A/B list, EEPROM provenance and RDRAM PNGs are recorded in
research/rs-name-entry.md. Fresh EEPROM logo timing differs from that retained
input. Arbitrary FR-changing coroutine compatibility remains separately guarded.
Keep the ADR0279 synchronous RSP/RDP/readback and sparse-dirty-page pacing rules.

## Rogue Squadron after restored VI pacing (ADR-0279)

Keep sparse dirty pages, changed-word-only shadow writes and synchronous
RDP/readback ordering. VI polling on the borrowed renderer owner may post
events and present the last guest VI state, but must never run CPU code or
deliver guest queue writes inside native RSP work. Preserve the exact-clock
and removed-poll mutation contract. Default GCC15.2/O2 RSP flags remain.

The matched30s RS run now reaches VI1798/fault0 with post-startup VI
p9518.180ms; SF64 remains near60VI/s. Longer play, PAL timing and RSP/CPU
cycle overlap are separate coverage. Continue the unknown-entry FR1 fault
at80013408 using the pinned ares oracle and complete FPR state comparisons;
then record name-entry and mission milestones from RDRAM readbacks.

## Rogue Squadron pilot entry and remaining pacing (ADR-0278)

Preserve byte-precise line_lost/dunknown masks, CDE no-fill allocation, known
refill bytes, dirty-discard/DMA refusals, native fetch guards and16 residual
CPU sites. The working pilot-menu prefix is Start600/1000/1200/1500, each4VIs.
It reaches ENTER NAME but refuses SWC1 f26,0x24(s2) at80013408, VI1523/fault11,
Status2400ff01. This function uses the checked default FR0 for unknown entry;
its caller arrives in FR1. Establish incoming FR facts/specialization or
verified dynamic FPR accesses across calls, with pinned-ares odd-register,
state, scheduler and mutation contracts. Do not delete the guard. No mission
or interactive-gameplay acceptance yet.

Keep Original projection/aspect plus the4:3 TV presentation surface; verify
PAL, overscan and intentional guest anamorphic modes separately. Rebuild and
deploy the bridge DLL with the native-RSP callback export. Native RSP and
nested RDP/readback remain synchronous and in order on the renderer owner.
Quiet measurements isolate recurring stalls from vsync/audio: VI p95 improves
194->91ms, but long native RSP/RDP tasks still block the scheduler and drop
retraces. Profile exclusive RSP CPU/RT64 workload/driver time, then test async
RSP/event scheduling or RAM-write-aware batching against complete task state,
readback visibility and SP/DP/VI event ordering. Do not batch blindly across
RAM producers. Histogram, resize checks and remaining limits:
research/rs-cde-lost.md and ignored target/receipts/rs-cde-lost.

The final retained-save runs also reach SELECT GAME without a fault, but a
longer Start/A drive reproduces the FR11 name-entry boundary at VI1873.
Keep save-state provenance when comparing these paths. MP2's original input
list alone currently ends before its explicit destination prompt on both
baseline and candidate; A2000/2100/2200 after that prefix reaches the retained
destination/rules screen. Investigate VI-relative input/poll scheduling with
an SI trace before claiming the original list is timing-independent.

## Rogue Squadron after the N64 logo (ADR-0277)

Preserve renamed ADDIU source tracking, partial table evidence/native-only
residual guards, rooted packed tables and contextual short-overlay filtering.
The76-word ROM table at80031740 is recovered; do not seed targets from captures.
RSP db0 placements after valid short records and scalar DMA trampolines now
load.51 RSP candidates and16 residual CPU sites remain; native_complete:false.

The next ordinary/input stops are fault4/80095040, showing the N64 logo in
400x442 VI-derived RDRAM readback. A private diagnostic identifies CDE targeting
p0017da60 with line_lost1. The model previously wrote back unknown cache-slot
bytes and marked their RAM line lost. Establish retained invalid-slot history
or a verified partial/full recovery contract, with CPU/ares, byte masks,
aliases, writeback and DMA checks. Keep the refusal until then. No title/menu
or working gameplay presses yet. Exact commands, attempted inputs and receipts:
research/rs-title.md and ignored target/receipts/rs-title.

## Rogue Squadron after dynamic FR (ADR-0276)

Preserve per-instruction FR analysis, canonical FPR bits, strict SDK Status
changes, unknown-path layout checks and scheduler save/restore. Calls kill
FR facts; arbitrary FR1 call contexts still require verified specialization.
Keep sparse RSP DMA dirtiness without losing full CPU/task-entry invalidation.
Idle overlay proof writes may revoke; active/suspended frames refuse writes,
and altered proof bytes must prevent rebinding.

The30s ordinary/input requests pass the copyright/model and overlay clear,
then stop at VI351/349,fault3/8003dc58. JR v0 requests8003dc68 through a
halfword selector bounded by4c and runtime table base t4=80031740. This is one
of the19 existing residual sites. Establish table-base provenance and discover
the internal targets; do not seed targets from the stop or weaken dispatch.
Final sampled readback is mostly black/noisy, without a verified title/menu.
Commands, PNGs, full-state/mutation tests and gate/control receipts are in
research/rs-dynamic-fr.md and ignored target/receipts/rs-dynamic-fr.

## Continue Rogue Squadron after its first copyright screen (ADR-0275)

Preserve sparse slot instruction verification/protection, immutable dispatch
inputs (including those within candidate text), rebind/ambiguity guards and
native-only residual dispatch. The write to80096bfd is mutable prefix data,
not code; native and pinned ares identify the second descriptor overlay at
800960e0 and agree on SB41. Do not restore whole-candidate protection.

The next blocker is fault12 at80013c34, MTC0 Status, requesting2400ff01 from
2000ff01 while an SDK thread owns execution. The matrix routine switches FR0
toFR1 before loading odd FPRs independently. A verified dynamic-FR contract
must preserve all GPR/FPR bits, Status/interrupt effects, thread save/restore
and refusals for unsupported Status changes. Merely allowing MTC0 would hit
the fixed-map FPR-layout guard next. Keep that guard until lowering and its
native/ares verifier cover transitions.

The readable copyright screen is640x480 RGBA5551:19496 nonblack pixels/48
colors in RDRAM. Ordinary30s request: VI114,53 graphics/62 audio,36 PI DMAs;
independent readback VI111; Start100/A110 repeats fault12 nearVI112. No menu
or gameplay is established. Preserve ADR-0274 native RSP task/fetch tests and
19 residual CPU sites/native_complete:false. Evidence and complete acceptance
commands are in research/rs-first-frame.md.


## Continue OoT after NJPEG save load (ADR-0265)

Preserve the protection-task and NJPEG pinned-ares memory/state comparisons,
self-DMA provenance/bounds, startup ambiguity and per-word fetch guards.
Continue past the opening cutscene into interactive play and longer save
loads. Candidate discovery is not RSP closure. DPC clock uses the existing
wall-time event model; synchronous graphics/busy assumptions remain open.
Keep screenshot pauses out of pacing measurements; follow the timing
receipt in research/oot-jpeg-boot.md for any remaining stutter.

## Rogue Squadron after PI-family binding (ADR-0273)

The PI switch at 8002a2e4 is passed by authenticating the public PI manager/DMA
family and binding the existing host APIs. Preserve full-body/peer/global and
caller-owned helper authentication, strict/residual native guards, cache
unknown-byte refusal and scheduler/RSP contracts. Identification is 32 runtime
functions; 19 residual sites remain and native_complete:false.

Native RSP graphics reaches VI1, 15 PI DMAs and one graphics task, CPU fault0 /
PC00000000, then refuses unlowered IMEM db0. The stopped framebuffer readback
is essentially black, without title/menu. RT64 HLE reports unsupported GBI and
access-violates without stop JSON; do not treat that as a measured CPU fault.
The 64 bytes at the refused entry uniquely match ROM offset20518. The captured
predecessor placement has this sequence eight bytes later: establish the RSP
DMA/placement provenance and add ROM-derived candidates with pinned-ares state,
memory and fetch-guard verification. Snapshots are diagnostic outputs, never
native compiler inputs. The native run must continue to refuse absent words.
No further rendered frame or gameplay is claimed. Receipt:
research/rs-pi-jumptable.md (prior receipts: rs-thread-dispatch.md,
rs-cache-cde.md, rs-blockers.md).

## Preserve scissored fill clears (ADR-0266)

The SF64 border defect is fixed in the shared RT64 fill-clear path. Keep
all three generated patched compilation units when rebuilding the shim;
run its CTest framebuffer contract. Preserve the same-input VI 600 capture
and empty/partial/disjoint-scissor tests in research/sf64-border.md.
Remaining renderer accuracy work includes fractional scissors, interlace,
VI filtering/coverage and broader gameplay comparisons; this bounded fix
does not certify those behaviors.

## Continue Mario Party 2 after thread retirement (ADR-0268)

Preserve catalog-over-replay text reconciliation and unique runtime binding,
text/data/BSS checks and revocation. The VI 8/fault 8 refusal is fixed. MP2
now passes the VI 520 deadlock. A 30-second Start/A run reaches destination
selection at VI 1798, fault 0/fault_pc 00000000. Preserve the thread-owned
context registry, retirement acknowledgements before reuse, owner-specific
pin release, stale-generation refusals and lifecycle/mutation tests. Continue
into board play and longer runs. ADR-0269 fixes the bare native.py path by
reapplying catalog text trimming before the stale-declaration comparison;
fresh-ROM discovery/build/run reaches destination selection without --loads.
Preserve its exact-source/witness/range and declared-catalog refusal tests.
Edited coroutine targets still require residual dispatch. Copied buffers,
other layouts and running-thread self-reinitialization remain refused.
Abandoned buffers within a still-live generation retain the existing caps;
thread teardown does not prove arbitrary buffer-liveness/reclamation.
Receipts: research/mp2-thread-lifecycle.md, research/mp2-overlay-binding.md and
research/mp2-fresh-analysis.md.

## GoldenEye after mapped-page source recovery (ADR-0255)

48 engine pages are authenticated; 81/85 original direct-edge destinations
are decoded. Four edges still name 7f010290 or 7f08fe74. The expanded 9035-block
map remains OPEN 592/589 ordinary/residual. Recover unvisited source pages and
model instructions/delay slots across independently bound pages without using
synthetic storage adjacency as virtual continuity. Then establish the copied
TLB refill/exception contract: Context, Random/Wired, TLBWR at 70001b94 (running
at vector 80000034), ERET and page-pool eviction/reload generations. A first-fetch
physical source is not a permanent placement proof. Keep unsupported mapped
call observations refused, boot text/data bounds conservative, native source
checks and BK/MM controls. Receipt: research/mapped-page-source-recovery.md.


## GoldenEye after first-use data recovery (ADR-0250)

The normal ROM-only pipeline remains OPEN 175/172 ordinary/residual. Establish
the sources and paging/loader model for the 85 direct destinations in the 7f
engine range, then the remaining callbacks, mapped helper and COP0 effect.
The first mapped producer extent includes writable data; its text/lifetime
bounds still need refinement before native acceptance. Text trimming alone
does not reduce these blockers. Preserve replay-authenticated data-only ranges,
table guards, the closed-world gate and BK/MM controls. Evidence and receipts:
research/mapped-boot-text-extents.md.

## After Mario Kart 64 runs (ADR-0244, ADR-0246)

Mario Kart 64 still builds with two residual dispatch sites; prove them for
native_complete. Re-run the ROM sweep (GoldenEye, Star Fox 64, Rogue Squadron,
OoT) on the current pipeline.

## After short RSP overlays (ADR-0243)

Mario Kart 64 faults 3 at 80040c8c after VI 526: an indirect jump reaches a
target that discovery did not find. Find the target and its source.

## After boot EntryHi (ADR-0242)

Mario Kart 64 stops at VI 2 with --rsp-gfx on an unlowered word of its
graphics microcode. Find which text and word, and whether the RSP lowering or
the candidate search misses it.

## After PIF terminate-boot (ADR-0241)

Mario Kart 64 reads EntryHi at 800d1c80 to save it around a TLB write. Seed
the TLB staging registers from the ares post-IPL capture (as Status is) and
stop runtime calls from forgetting EntryHi where the replaced libultra
functions provably preserve it.
## After RSP candidate identity (ADR-0240)

Banjo-Kazooie runs again but with 2 residual sites: since 94a4d7cb (ADR-0205)
a new entry splits the blocks holding table jumps 0x80876480 and 0x808acf48,
and their five-candidate table proofs are lost. Restore them generically.

## After COP1 control-register startup repair (ADR-0238)

MK64's native Status writer is correct; do not clear FR to bypass a real
mismatch. CFC1/CTC1 are layout-independent and now retain only the CU1 gate.
The next observed startup stop is fault 1 at 800d1be8: a word-8 write to
PIF RAM bfc007fc before any runtime thread or VI. Establish a generic native
PIF access/command contract against pinned references before supporting it;
do not add an address-specific bypass. Four residual sites still require
closure proofs. Keep FPR mismatch and CU1 checks, event/SDK boundaries and
native-frame protections intact. Independent BK/MM regression work remains
owned separately. Receipt: research/status-fr-control-registers.md.
## After continuation pins (ADR-0239)

MM is restored. Banjo-Kazooie still regresses twice: 94a4d7cb (ADR-0205) loses the
table proofs at two sites once a new entry splits their block, and a later
commit adds a 42nd ROM-derived RSP text that makes its task match ambiguous.

## After bounded ERET and aligned load recovery (ADR-0237)

MK64 now produces a residual validation artifact: the four missing functions
belong to ROM 123640..12aae0 loaded at 80280000 by a lone LUI destination.
The first native stop is fault 11 at 800cc0f4, VI/tasks/DMA 0. Preserve the
existing Status/FR checks and coordinate with the separate BK/MM regression
investigation; do not bypass FR to claim gameplay. Its ordinary four blockers
are three indirect sites plus ERET return closure, retained as four residual
sites. General guest exception-vector entry/EPC production and SDK-frame ERET
still require independent contracts; current ERET accepts explicit known return
registers only outside SDK contexts without enabling unmodeled events.
GoldenEye stays OPEN 339 ordinary / 327 residual blockers (12 sites): qualify
mapped table/source/target bounds and the remaining scope effect. Preserve the
byte-identical BK/F-Zero X/MM discovery controls. Receipt: research/eret-lowering.md.

## Continue mapped discovery after ADR-0236

GoldenEye's mapped boot target now has replay-authenticated physical bytes;
its 3,716-block map exposes OPEN 341/331 ordinary/residual blockers. Establish
qualified code/data and table/source bounds in the reached image, and compare
replay-produced slot identity before admitting mapped open-call observations.
Keep fixed executable/binding overlap fail-closed. MK64 stays OPEN 13/10:
ERET needs EPC/ErrorEPC, Status EXL/ERL, LL and event effects with a pinned
native differential contract; four missing targets still need load provenance.
The pinned reset harvester now crosses boot COP0/TLB; the core-only evaluator
still refuses unknown startup state. Do not claim native execution for either
ROM. Preserve byte-identical BK/F-Zero X/MM discovery and leave the independent
BK/MM native regression bisects to their owners. Receipt:
research/mapped-code-discovery.md.

## After ADR-0233

Per-site proofs no longer gate a build. The sweep points at the next universal
work, in order:

1. After ADR-0235's seven checked COP0/TLB forms, authenticate and export
   TLB-mapped instruction fetch/source/lifetime bindings from pinned replay
   so mapped main images can be discovered. Extend the core-only boot evaluator
   only with verified initial CP0 state. Add Random/TLBWR, Count/Compare,
   Cause/EPC/ERET, CACHE and interrupt/exception delivery; expand Status writes
   into SDK contexts with explicit scheduler/IE effects. Unmodeled values fault
   12; they are not emulated. See research/cop0-lowering.md.
   The verified partial leaves GoldenEye OPEN/1 at mapped target 70000510;
   MK64 residual OPEN/10 includes ERET plus four missing target/source pairs.
   Preserve BK/F-Zero X discovery identity and the known unrelated native
   regressions while extending this boundary; do not admit mapped bytes by
   virtual/physical equality alone.
2. Discover overlay code that Star Fox 64 calls into (136 unmapped targets,
   157 unresolved direct targets).
3. Paper Mario: find the shared-slot occupant at `80240310` reached at VI 2908.
4. Mario Party 2: `plaid identify` fails before discovery.

## Paper Mario proof gaps after ADR-0231

No residual site is closed by the TLB host-effect contract. Three switches meet
independent entries that bypass table-base initialization; two require alias-safe
stack pointer/index lineage; three need stronger guest callee value preservation.
The 8082cf20 callee now passes osMapTLB but reaches a guest s3 overwrite at
8002974c. Prove memory separation and exact save/restore value lineage before
accepting it. The two other first overwrites are 8003c680 (s2) and 8004ec70 (s4).
No ABI shortcut or observed-target certificate is valid. Keep default native
emission refused until all required edges have source-rechecked proofs.

## After completed raw slot occupants (ADR-0230)

The previous VI-659 JALR stop is passed. Two visible 60-second Paper Mario runs
reach the time limit with fault 0 and render the opening storybook; the repeat
also captures nonzero PCM. There is no next runtime fault in this coverage scope.
Extend visible validation through controller input/new-game transitions and
longer gameplay, recording the next source-bound stop before implementing a fix.
Intro rendering and a nonzero PCM peak do not establish full gameplay or audio
accuracy. Preserve native_complete: false until the remaining proofs close.

The current map retains eight residual sites: 8003c488, 8004e544, 8082cf20,
8091893c, 809189b8, 80918aa8, 80b1c178 and 80b1c344. Follow their current
source/linked bindings, not historical synthetic slot coordinates. Prove the
missing target sets without turning finite replay observations into closure.
Broaden raw-source discovery only with equally strong completed-effect, full-byte,
cache, alias and native-frame checks; transformed or unsupported producer modes
remain separate work. See research/paper-mario-native-frontier.md for receipts.


## Continue after incomplete-path switch candidates (ADR-0229)

Paper Mario now passes the previous 80a08aa8 switch stop. Next stop: fault 3 at map
80a06450, runtime 802c6450, JALR a2 -> 80240880, VI 659. Its target is not an
admitted function entry. A declared linked-range projection yields 80810880,
inside an existing block, but the actual resident source must be checked before
turning that numeric projection into a call root. Inspect the returned pointer,
slot identity, replay observations and instruction/source bytes; retain entry
and dispatch checks. Do not add the observed numeric address unconditionally.

Incomplete switch witnesses remain residual hypotheses, not closure. Broader
path enumeration or incomplete call-array candidates need separate evidence;
nullable function-call tables keep their prior behavior. PCM remains silent.
See research/paper-mario-native-frontier.md for the exact stop and controls.


## Continue after relocated replay call coverage (ADR-0227)

Paper Mario now passes the checksum call at map 808be154. The next visible
residual stop is JR v0 at map 80a08aa8 (runtime 802c8aa8), targeting runtime
802c8ab8 in the same slot. It has no candidate/observed targets or closure
certificate. Establish the control-flow evidence and lower/admit the reachable
case without treating a computed JR as a function-call root. Keep unknown
transfers fail-closed and observations separate from exhaustive target proofs.

PCM remains silent; establish non-silent audio independently. Extend observation
to other formats only with source-aware binding verifiers: compressed/dynamic
placements and TLB source translation are still conservatively unsupported by
the new slot observer. See research/paper-mario-native-frontier.md for finite
coverage, control comparisons and exact receipts.

## Extend ROM-derived RSP coverage after self-patching

ADR-0219 identifies the OoT type-4 startup conflict as RSP boot microcode also
discovered as possible fixed CPU text. Keep both interpretations safe: revoke
inactive CPU text on writes, byte-check before entry, and pin active native
frames across SDK scheduling. The visible current-map OoT run confirms the
patch and stops at unlowered IMEM 0x080 (image hash 123cbfb9), CPU fault 0,
VI 3, no graphics/PCM. Establish the ROM source or transformation of this
next task image and extend fetch-verified native coverage; keep unknown images
fail closed and require audio for acceptance. See research/rsp-from-rom.md.

## Continue Paper Mario ROM-only closure

The user selected Paper Mario. The frontier is OPEN/7 with 56,851 blocks and
162 loads after ROM-only TLB effect/bridge source inference and guarded tail
cells and scheduled pointer/constant-SLLV proofs. Finish the remaining bounded
indexed dispatch proofs, including matching index values and callee save/restore
effects and captured pointer/index relations. Captured pointer/flag values now
survive same-binding calls only with rechecked no-write effects for every live
GPR; another five-entry dispatch closes. Paired index/offset updates now have a
low-word affine proof, closing a further five-entry dispatch. Mapped callee effects now bind unique declared linked text and rechecked
constant-cell tails, with path-local binding authority and exact source/return
witnesses. Two dispatches close; other predecessor paths still need proof.
Walk-local source-bound callee effect reuse closes two resource-limited sites
without increasing the shared read budget (ADR-0216). The remaining groups are
three independent address-taken entry/base-initialization barriers, two callee
register-effect/save-restore proofs, and two captured stack-cell pointers.
Do not turn the three address-taken roots into internal entries without proving
their independent origins impossible. See research/table-effect-reuse.md for
the scripted final-round classification, mutations and local receipts.
ADR-0217 adds exact frame-local SW/LW table-pointer forwarding with all-path
allocation/SP checks and no intervening write/call/cache/mapping effects. It
closes the synthetic cases; fresh PM remains OPEN/7 with an identical map.
Stack index/cell version relations and nested-callee memory effects remain
unproven. See research/stack-table-pointer.md.
Continue bounded save/restore, stack-cell and captured-index/entry proofs while
retaining mapping generations and active-frame pins. A source binding is not
permission to infer an SDK boundary. See research/mapped-callee-effects.md.
Infeasible flag paths are now pruned only while their GPR value survives.
No-write callees now preserve pending base registers without a guest
ABI assumption. Standalone BREAK paths stop at the existing native abort.
Derived case-entry origins and candidates now survive discovery
rounds, with every incoming indirect case edge checked. Five sites retain
84 newly recovered candidates; the longer bounded path proof closes one
56-entry site. Remaining sites still need closure proofs. Unchanged complete
backward predicates may be proved inductively around loops. The previous 18 table
extents all have qualified ROM-backed bytes; retain source-bound snapshots.
Preserve the CLOSED gate, mapped-code byte/generation/pin checks, and existing
native controls. No Paper Mario native run is accepted.

## Extend automatic coverage beyond the current native games

The fresh five-ROM sweep remains OPEN. After Paper Mario, investigate Mario
Kart 64's four missing code targets: establish their source/load path and bounds,
then add a general recognizer and synthetic regressions. GoldenEye requires
boot COP0/TLB mapping
evidence; Paper Mario and Star Fox require broader executable image coverage;
Rogue Squadron requires qualified pointer-table provenance. The retained
results are in research/remaining-roms-20261018.md. Preserve the CLOSED gate
and the current BK/MM/F-Zero X controls while extending coverage.

## Preserve framebuffer readback coverage (ADR-0201)

BK's black puzzle-piece interiors are corrected by generic completed-renderer
readbacks. Retain the exact-span, byte-order, cache and protected-write tests;
broaden gameplay/overlay validation without equating finite visual success
with pixel-perfect rendering or whole-ROM closure. Remaining BK native-RSP
graphics and higher startup-state work below still applies.

## Continue beyond BK's finite native bring-up (ADR-0200)

BK now passes the normal ROM-only 60-second visible/audio-required pipeline,
with scoped CLOSED/0 and restored opening/intro backgrounds. Preserve the
deterministic startup-prefix, Status/mask, SI, VI and DP regressions. Broaden
gameplay/input/overlay coverage; title-screen execution does not establish a
full playthrough, pixel-perfect rendering or correct mixing.

The current `--rsp-gfx` probe faults at IMEM 0xffc on its first BK graphics
task; establish the exact generated-microcode/entry mismatch before claiming
that path works. Above the modeled scheduler/interrupt/message/timer core,
continue replacing SDK HLE with guest code and pinned-reference register
models, starting with the PI manager and DMA completion. Diff guest-visible
effects and keep mutation-capable tests before retiring each boundary.

SM64's ROM-only OPEN/23 result is unchanged from before the VI move; use its
documented configured build as a separate control. Finish the regression sweep
without treating historical or differently configured runs as current evidence.
Higher startup RDRAM, complete device/cache/register state and whole-ROM
closure remain open. Research: native-bk-graphics.md and native-bk-status.md.

The continuation notes below are historical, superseded by the current state.

## Continue BK after paired-slot discovery (ADR-0192)

The next acceptance sequence and pinned-source observations are in
`research/status-interrupt-model.md`. RestoreInt(0) now has a retained
pinned-ares differential and preserves enabled IE (ADR-0193). Identification
now retains conservative per-copy scalar address bindings (ADR-0194). Next
verify SDK mask variants and carry their required bindings through the program
map/lowering contract, then implement mask, thread state and event delivery.
Missing/unsupported metadata must leave a new mask boundary unresolved.

BK is now scoped OPEN with one genuine Status-read blocker at 80259d30.
Implement and differential-test guest-visible Status, interrupt-mask changes
and thread/event interactions before admitting __osGetSR as a runtime boundary.
Current osSetIntMask/osGetIntMask return fixed masks; __osDisableInt tracks a
separate enable bit. Adding a guessed Status constant would be unsound.

The source catalog now supplies 13 shared-slot executable files with format-owned
text/data bounds. Retain catalog/metadata uniqueness, exact decoded sizes,
instruction/data separation, content checks and native-frame pins. Whole-loader
lifetime and exhaustive execution remain unproven. Once scoped CLOSED, rerun
the normal visible `--rt64 --seconds 60 --require-audio` pipeline and record VI,
fault/PC and PCM. See the continuation receipt in `research/rom-sweep.md`.

The older continuation below records the pre-ADR-0192 state.

## Continue BK closure after ADR-0191

BK is scoped OPEN with 29 blockers. Existing signatures identify its independent
SDK copies across disconnected supplied images; two exception dispatch blockers
and a false osVoiceInit switch-arm boundary are resolved. Next model the actual
__osGetSR/Status interrupt-mask observation (80259d30), without returning a guessed
constant. The existing runtime service set has no verified Status helper.

Seven direct-call targets in 8038xxxx decode as data-shaped/noncanonical words
in the captured generation; seven further targets are unmapped. Establish the
loader/overlay generations or a genuine non-executable proof. Do not suppress
static calls merely because a finite trace missed them. A 500-million-call
neutral-input experiment reaches analysis VI 676 without fetching the seven
missing targets; input dependence remains unproven. Production stays at
100 million calls / 3,600 VI / eight rounds.

Preserve source provenance, replay, cache visibility and native content guards.
BK native lowering, RSP extraction, visible execution and required PCM remain
unreached. PM improves to 164 blockers through the general identification fix
and three newly harvested declarations; SF64/MK64/GE/RS remain OPEN. Repeat the
normal visible, audio-required native pipeline only after scoped CLOSED.
Whole-ROM closure and executable overlay lifetime proofs remain open.

## RSP continuation after ADR-0188

ROM-derived RSP dispatch is accepted for the finite SM64, MM and F-Zero X
runs in research/rsp-from-rom.md; retain startup uniqueness and every fetch
identity check. Next resolve OoT's unsupported bootstrap path without a game
exception, and broaden task/overlay/DMA coverage. The complete:false registry
and general solver RSP-policy obligation stay open. Snapshots may compare
behavior as oracles, never supply the default native build's microcode.

## Milestone plan (ADR-0125, ADR-0126) â€” read this first

This section overrides the per-cluster continuation notes below wherever they
conflict. Those notes record open obligations; they are not a work queue.

Plaid's novelty is automatic discovery and closure proof from an untouched ROM.
Below that, reuse: lower through C (`crates/plaid-lower`), then link generated
code with Plaid's own runtime and RT64 (ADR-0158).
Every claim in issue #4 must name the milestone it advances and report the
effect in its receipt.

| # | Milestone | Done when | State |
| --- | --- | --- | --- |
| 1 | Synthetic ROM -> C -> native | spike096 programs, including nested/recursive calls, match pinned ares exactly; fail-closed cases fault | **done** (spike096, ADR-0127) |
| 2 | SM64 discovery recall | >= 99% of real functions found, scored locally against a decomp symbol map used only as an oracle | **done: 99.03%** (3795/3832, ADR-0152, `--data-roots`) |
| 3 | SM64 closed under declared assumptions | solver CLOSED in an explicit assumption scope; every assumption listed and checked | **done** (`closed` under the address-taken scope, ADR-0153..0156; execution-source and runtime-ABI assumptions are declared, the rest checked natively) |
| 4 | SM64 boots natively to title | lowered code linked with Plaid's runtime + RT64 (ADR-0158); no interpreter linked | **done** (ADR-0163), and into gameplay at full speed with native audio (ADR-0164..0169) |
| 5 | Retire assumptions; OoT | assumptions discharged one by one; OoT via Yaz0 (PR #28) and relocation (PR #31) | in progress: OoT `CLOSED` under the address-taken scope with all 468 overlays (ADR-0180) and draws its title and file select natively (ADR-0182); MM from the ROM alone is `CLOSED` and plays its intro natively (ADR-0183); 0 of 16 assumptions retired |

Next concrete steps, in order:

1. Done: return closure and function-level lowering (ADR-0127). Calls are C
   calls; every return checks `$ra` against its call's continuation. On OoT,
   43 of the 44 unresolved indirect sites are now certified returns.
2. Done: `plaid solve <rom> <map> --guarded-ram` and the 64-bit integer
   subset (ADR-0128). OoT guarded-scope blockers: 143 -> 82.
3. Done: declared runtime functions as a discovery boundary (ADR-0129). On
   OoT a heuristic declaration of 17 system functions leaves 1 guarded-scope
   blocker, but the first thread entry was never discovered.
   Done: runtime callbacks (ADR-0130). OoT now discovers its thread entry
   (613 blocks) and has 6 guarded-scope blockers.
   Done: COP1 data moves (ADR-0131); OoT is at 3 guarded-scope blockers.
   Done: guarded jump tables (ADR-0132). The remaining OoT blockers are
   memory-loaded function pointers inside libultra internals that the
   heuristic declaration leaves as guest code.
   Done: identification evidence (ADR-0133). `plaid identify` declares
   N64Recomp's reimplemented functions from n64sym signature matches. OoT:
   320 blocks, 21 guarded blockers (7 in boot code; 14 from calls into the
   region its code segment is later DMA'd over).
   Done: unaligned loads and stores (ADR-0134).
   Done: COP1 compares and BC1 branches (ADR-0135).
   Done: declared executable loads verified by content (ADR-0136) and a
   shared return-closure context (ADR-0137). OoT with its `code` segment
   declared: 7451 blocks, 748 guarded blockers.
   Done: `BREAK` as a checked abort (ADR-0138); OoT at 566 guarded blockers.
   Done: COP1 arithmetic, conversions and FCSR access (ADR-0139); OoT at
   42 guarded blockers.
   Done: GCC's scheduled jump-table shapes (ADR-0140); OoT at 8082 blocks,
   31 guarded blockers, with no unresolved jump table left.
   Done: runtime identification over declared loads (ADR-0141); OoT at
   7684 blocks, 29 guarded blockers, none of them instruction-scope.
   Recorded negative (ADR-0142): every one of the 21 function-pointer
   `jalr` sites takes its target from memory, and a sound field-store
   census would need whole-program store points-to, so they stay open.
   Store-guarded fixed-address cells would close only 1 of 22.
   Done: host-entry returns hand control back to the host (ADR-0146); OoT
   at 28 guarded blockers.
   **Next:** the 7 64DD calls target a driver that ships on the 64DD disk,
   not the cartridge (no dmadata file places code there). Guarded flag cells
   that prove the guarding flag stays 0 were prototyped and rejected
   (ADR-0147): the writer census misses stores through pointers. OoT is at
   its sound frontier. Prioritise SM64 (step 4), which needs the user's ROM.
   Done: runtime functions named from a reference symbol map (ADR-0148,
   `plaid identify ... --symbols`). Mario Party 2 showed that n64sym's
   database misses some SDK builds: 27 of its 29 boot-window blockers sit
   in an unidentified `osInitialize`. Use the SM64 decomp map for both
   recall and identification.
   Done: the SM64 ROM and a locally built, matching decomp map (CC0, commit
   9921382) are in `target/local-inputs/`. Forwarded callbacks (ADR-0149)
   open SM64's `-O0` thread creation: 2936 blocks, 8 guarded blockers, 8.1%
   recall (`research/sm64-first-measurement.md`).
   Done: disjoint declared loads (ADR-0150). SM64 with its engine and
   goddard segments: 5337 blocks and 12 guarded blockers, all of them
   function-pointer calls loaded from memory. Recall is 11.4%.
   Done: IDO's slot-bound jump tables (ADR-0151); SM64 is at 5580 blocks
   and 10 guarded blockers.
   Done: heuristic data-pointer and layout roots (ADR-0152). **Milestone 2 is
   met:** SM64 whole-map recall is 99.03%.
   Done: the address-taken dispatch scope (ADR-0153). Register calls
   dispatch over the 1313 functions whose addresses appear as data or code
   constants, and native code faults otherwise. SM64 is at 32 blockers
   under `--address-taken`.
   Done: load-delay `nop` tables (ADR-0154), TLB runtime functions and
   in-image address-taken bodies (ADR-0155). SM64 is at **1 blocker**
   under `--address-taken`.
   Done: a table bound before the only branch into the guard (ADR-0156).
   **Milestone 3 is met:** SM64 solves `closed` under
   `DeclaredStaticImagesGuardedRamAddressTaken`.
   Done: `plaid lower-map` (ADR-0157). The closed SM64 map lowers to one
   C file that gcc compiles. Run natively with stub runtime functions, it
   reaches `osCreateThread` for the idle thread.
   **Next (milestone 4), per ADR-0158:** Plaid's own runtime (`runtime/`, C)
   plus RT64 (MIT).
   - Done: runtime core and loop safepoints (ADR-0159), and FR = 0 COP1
     (ADR-0160). SM64 runs natively for 96 frames at 30 fps.
   - Done: declared-load lifetime (ADR-0161). SM64 runs past the goddard
     reload.
   - Done: TLB-mapped data (ADR-0162). SM64 runs natively for 90 seconds
     (1459 graphics tasks) without a fault.
   - Done: RT64 draws its graphics tasks (ADR-0163). **SM64 boots natively
     to its title screen.**
   - Done: controller 1 from `--press` scripts and the window keyboard
     (ADR-0164). SM64 gets past the title into the castle-grounds intro.
   - Done: EEPROM persistence with `--save` (ADR-0165).
   - Done: VI at NTSC rate on Windows (ADR-0166). SM64 runs at full speed
     (59.9 VI/s, 30 fps) into gameplay.
   - Done: RSP scalar microcode lowers to C with closed IMEM dispatch
     (ADR-0167, spike097 matches ares).
   - Done: the RSP vector unit (ADR-0168), ported from ares (ISC);
     SM64's audio microcode lowers completely (904 instructions).
   - Done: RSP tasks run lowered IMEM snapshots (ADR-0169). The game's own
     boot code loads its microcode; no per-game offsets. SM64's audio
     tasks run natively and match ares exactly (spike098); `--wav` writes
     the samples.
   - Done: AI DMA timing as ares models it, and live playback through SDL
     (ADR-0170). SM64's audio keeps pace with the run.
   - Milestone 5, step 1 (ADR-0171): runtime functions are named from the
     ROM's own bytes; SM64's decomp map now backs only `osInitialize`,
     `osContInit` and `osEepromLongRead`, and SM64 stays `closed`.
   - Done: OoT's fixed code `CLOSED` under the address-taken scope (ADR-0175);
     native boot through the RCP I/O model and a lowered RSP task
     (ADR-0176/0177); overlays discovered at link addresses (ADR-0172
     stage 1, ADR-0179) with discovery in 44 s (ADR-0178); jump-table bounds
     proven over every path (ADR-0180), so OoT with its 468 overlays is
     `CLOSED` (154,414 blocks); relocatable overlays run natively through a
     verified binding (ADR-0181); with RT64, lowered audio microcode and
     SRAM, OoT draws its title and file select (ADR-0182); `scripts/native.py`
     takes an untouched ROM to native, and MM plays its intro natively
     (ADR-0183).
     F-Zero X's boot image and segments are inferred from the ROM alone
     (ADR-0184).
     Shared executable slots are now represented and verified as alternates
     (ADR-0185); F-Zero X has 27,621 blocks and zero address-taken blockers.
     Native graphics microcode now renders its vehicles and races through
     RT64 raw RDP output (ADR-0186); the build caches objects and emits a launcher.
     Done: MM's inactive heap-overlay binding can move to a unique verified
     copy while native frames pin active bindings (ADR-0187); an erased-save
     startup passes its former fault. **Next:** MM and OoT into gameplay, then
     prove overlay bases/lifetimes from their loaders and retire assumptions
     one by one (see the ledger in the README and
     `docs/assumptions.json`; 0 of 16 retired).
   - Data-driven roots (level, geo and behavior scripts) for recall.
4. **SM64 recall harness** (milestone 2): the scorer is ready (ADR-0144,
   `plaid recall <map.json> <sm64.us.map> [start end]`). Once the user
   supplies the ROM: discover from the real entry point, then score
   against a locally built decomp map. Keep ROM bytes, maps and traces
   ignored.
5. **Lowered subset growth** pulled by SM64: done for `ROUND/CEIL/FLOOR`
   and the `.L` conversions (ADR-0143), then branch-and-link, `LL/SC`,
   `SYNC` and conditional traps (ADR-0145): 196 of 209 forms. The other 13
   are COP0, TLB, `ERET`, `SYSCALL` and `CACHE`, which stay behind the
   runtime boundary unless a ROM needs them in guest code.
6. **Known-library evidence**: done for runtime boundaries (ADR-0133); PR #50's
   source-bound candidate model is still open for other uses.

Paused until a milestone needs them: RSP/SP lane, producer, task-root and
reverse-DMA provenance beyond spike095.

Unchanged: every AGENTS.md invariant, fail-closed semantics, exact-head CAS,
no ROMs or game-derived bytes in git, no GitHub Actions, and `native_complete`
plus every broad certification flag `false` until proven. Assumption scopes are
added as new scopes; existing scopes are never weakened.

## Historical per-cluster continuation notes

Scoped scalar RSP stores now connect rooted operand facts to DMEM writers and
CPU executable backing (spike094). Continue the graph through DMA/RAM/copy and
computed executable-byte origins, keeping code-read, operand, method and byte-
effect identities separate. Do not infer a writer from temporal overlap or equal
values. External/DMA effects remain cuts unless their own origins are proven.
Task/reset/control roots, general/vector producers, complete writer/backend
coverage, continuous lifetimes and whole-ROM/native closure remain OPEN.

Exact raw RSP consumption now feeds rooted scalar producer facts (spike093).
Continue from these definitions through actual DMEM/RAM writers and executable
consumption, and bind guest task/control/PC/reset producers to operand roots.
The boot recipe emits only the first initial operand root; later discontinuities
without a declared root reject. Captured inputs and unsupported instructions
stay opaque, and roots must cut equal-value held definitions. Do not infer task,
writer census, hardware or continuous lifetime completeness from these facts.

Lower IMEM effects now compose with CPU/RSP executable consumption on raw v8
(spike092). Continue actual register/data/task producer and execution-epoch
composition. Equal-byte writes, fill/load and new installations must not revive
ended parents; preserve reads frozen before those effects. Bulk cuts supply no
producer lineage. Restore/retirement, raw-pointer/backend coverage, complete
writer census, full lifetimes and whole-ROM/native closure remain OPEN.

Performed RSP consumption now joins the existing raw PI/RAM/IMEM state through
exact read receipts (spike091). Continue actual register/data/task producers and
writer/epoch coverage; a fetched instruction's byte parents do not authenticate
its operands or close its future target set. Preserve logical PC versus actual
masked read address, frozen read parents and unperformed lookahead independently.
RSP hardware consensus, full lifetime and whole-ROM/native closure remain OPEN.

Lower DMEM storage cuts now compose on raw history v6, including equal primitive
RSP writes that bypass CPU-window wrappers. Continue authenticating actual RSP
instruction/register/task producers separately; a sink cut supplies no source
parent. Preserve per-lane effects, IMEM independence and frozen DMA reads. Reuse
authenticated old v3/v5 results where this added protocol is unselected; broader
source, mutation, cache/mapping and execution-epoch coverage remains OPEN.

The existing raw-clock PI consumer now composes RAM parents with validated SP DMA
read/install occurrences and actual CPU SP consumption (spike089). Continue into
actual RSP consumption and producer/register definitions using complete histories;
this CPU path does not authenticate an RSP task or scheduler. Preserve frozen
source-read parents, independent SP writer identity and equal-write revocation.
Missing/ambiguous reads remain unknown; general census/lifetime/closure stay OPEN.

Physical PI storage writers now compose with executable consumption. Extend
other actual producer scopes while retaining original effect identity, separate
mapping/root obligations and independent cache residency. The 110-event native
reference fixture uses explicit host descriptor/mapping controls; it does not
prove guest MMIO or mapping ancestry. Reuse the authenticated commercial-prefix
report only when a complete delta check proves all writer selections unchanged.

The v5 boot source now places ordinary storage effects on the original PI/SP/
fetch clock. Continue actual producer/cached operand/mapping/root composition
from its retained69,513,732-record twenty-million prefix. Scalar/equal storage
writes and full backing fill/load cuts revoke RAM parents; surviving I-cache
generations stay independent. Restore/retirement still reject without execution-
epoch evidence. Preserve raw writer identities and externally retained digests;
finite sensor records do not establish mutation completeness or future closure.

The opt-in storage mutation sensor (spike086) reaches ordinary Memory::Writable effects beneath RAM
wrappers, including translated/EBus writes and explicit bulk/restore/retirement
cuts. Preserve actual component splits and unknown parents; bind actual producer
contexts separately. The25-effect/20-checkpoint contract does not cover raw-pointer
backends, hidden RAM or complete scheduling. Reuse its retained controls before
extending local-ROM capture; do not treat identity-only history as a writer census.

Continue the existing RSP producer path from original-clock register definitions
through actual installed-code consumption. Controlled v3 joins CPU IMEM installs
to RSP fetched words; v4 additionally joins original-clock RSP definition/DMEM
parents through separate reverse-DMA RAM writes to actual CPU fetch/decoder
contexts. Controlled v5 also binds promoted-current identity and exact complete
descriptor progression to that graph. Controlled v6 joins the RAM byte writers
through actual Dual read/IMEM installation back to RSP instruction consumption.
Controlled v7 also joins actual two-read/two-store DMEM ingress to RSP load
definitions with distinct lane parents. Controlled v8 also retains actual pending
address mutations and length recommit/supersession through promotion and immediate
handoff to installed-code consumption. Controlled v9 connects an actual decoded
CPU direct-KSEG1 SW through its pending length commit/synchronous promotion to
installed-code consumption. Controlled v10 also joins actual completed I-cache
burst/fill parents to cached CPU execution after changed backing, with explicit
opaque host control roots. Controlled v11 also joins actual guest HitInvalidateI
through fresh DMA writers/refill to cached execution; equal words cannot reuse
ended fill ancestry. Controlled v12 also joins actual SP LW/register/CPU SW RAM
copies through resident-vs-refilled executable ancestry. Controlled v13 also
retains one actual in-place XORI expression from original load parents through
RAM writing/invalidation/refill to transformed instruction consumption. Controlled
v14 also joins an actual copied/transformed BREAK to its exception transfer and
first cached handler fetch with separate writer ancestry. Controlled v15 also
joins the live exception-produced EPC generation through continuous handler
mutation/cache invalidation/ERET to returned instruction consumption. Controlled
v16 also retains an actual MFC0 read and equal-value MTC0 EPC writer, selects the
fresh writer at ERET and rejects held reads of ended generations. Controlled v17
also derives a changed EPC through one actual in-place XORI and connects ERET's
selected target to a separate CPU writer/refill/executable chain. Controlled v18
also binds actual TLBWI/current normalized entries to mapped cached BREAK/EPC/
ERET/returned execution. Equal TLB writes replace mapping operation identity but
preserve I-cache generations. Controlled v19 also binds actual EntryHi/ASID
context writes (including equal rewrites) separately from installed-slot writers
to both mapped consumptions. Fixture20 additionally composes a nonidentity
mapped address with surviving stale hits before/after actual ASID restoration,
then actual invalidation/refill/root/return in the same v19 protocol. Controlled
v20 also binds actual EntryLo0 page writers through TLBWI to changed physical
selection and fresh writer/root/return ancestry. Staging alone leaves the old
installed mapping active; equal page rewrites retain distinct identity. Controlled
v21 also composes actual TLBR loads from installed slot/page ancestry with active
ASID and mapped consumption; equal loads retain occurrence identity. Controlled
v22 additionally joins completed direct-SP SC effects/current LL source reads to
actual IMEM/RSP consumption, preserving failed attempts and equal writer identity.
Controlled v23 also joins SB/SH whole-SP-Word sinks and a held XORI expression
to actual IMEM/RSP consumption, keeping device vs aligned addresses and shifted
lanes' weaker ancestry distinct. Controlled v24 also connects actual decoded
uncached RAM LW/current byte writers through CPU held expressions and RAM/IMEM
copies to RSP consumption; an equal fresh RAM writer changes the next load's
parent without changing the previous load. Controlled v25 also binds actual
cached RAM LW to canonical D-cache resident state, captured backing-read writer
parents and IMEM/RSP consumption. Current backing changes cannot alter old
resident parents; actual HitInvalidateD/refill selects the new RAM writer.
Controlled v26 also binds actual cached SW sources/equal mutation revisions to
complete16-byte HitWritebackD export, including untouched resident lanes, then
RAM/IMEM/RSP consumption. Cached post-export reads retain mutation ancestry.
Fixture28 also composes surviving mapped I-cache execution after equal export,
then actual guest invalidation/refill to CPU consumption of that export. Next
compose other mapping/control producers and broader root/control lifetime with
complete mutation coverage. Keep ERET admission bounded to the uncut ERL0/kernel32/IE0 frame;
ordinary static ERET stays unsupported. Reuse retained748-event/127-control
fixture28 and729-event/124-control v26,
674-event/114-control v25,
610-event/102-control v24,
570-event/94-control v23,
542-event/88-control v22,
506-event/80-control v21,
485-event/77-control v20,
431-event/68-control fixture20,
421-event/66-control v19,
400-event/63-control v18,386-event/61-checkpoint v17,375-event/59-checkpoint v16,
365-event/57-checkpoint v15,
339-event/52-checkpoint v14,
295-event/45-checkpoint v13,
259-event/39-checkpoint v12,
228-event/34-checkpoint v11,208-event/31-checkpoint v10,195-event/
29-checkpoint v9,180-event/26-checkpoint v8,152-event/23-checkpoint v7,
142-event/21-checkpoint v6,136-event v5 and
134-event v4 (same19 controls),97-event/17-checkpoint v3 and all earlier
compatibility sources; no repeat reference build is needed for compatible consumers.
A fetched word or matching final image cannot exclude unsensed writes.

Continue from the complete twenty-million-call CIC6105 PI/fill/consumption join.
Canonical and independent replay agree on2472203 full candidate fetches,
172 samples/27 fills, beginning at seq17527797: ROM0x1000 -> four actual PI
byte writes -> cached RAM0x400/declared entry. Preserve these source clocks and
discrete observations while composing complete mutation coverage and cache/TLB/
mapping/execution-root lifetime. Avoid another equivalent capture or isolated
consumer. Neither unchanged values nor a finite prefix exclude unsensed writes.
The canonical `inspect-sp-pi-fetch-lineage` / `verify-sp-pi-fetch-lineage`
boundary retains independent raw source receipts. Primitive reconstruction also
joins request1/token6 to dispatch event1 and one status transition; its pending
list is empty. The declared ROM entry is observed at seq17527797, cached physical
0x400, with source unknown. Do not infer executable lifetime, mutation coverage
or hardware boot from finite byte agreement. Reuse retained sources and the
release CLI; no additional emulator rebuild is needed for compatible consumers.

The bounded fetch/history capture ceiling is twenty million calls, with the
unchanged 100-million history-record guard. Full repeated sources and disabled/
repeated checkpoints agree. Preserve the earlier million-call report as a
compatibility receipt; exclude the old timed-out partial source. Buffered output
preserves all getters/records and measured about5x improvement. Do not bypass
Random-register disassembly queries or conflate queue clock with CPU Count.

Use explicit verified CIC selection for local ROM capture (ADR-0123). The shared
profiled driver and import gate now admit NTSC/6102 and NTSC/6105; existing
homebrew captures retain their original 6102 scope. Reuse the compatible build
and retained sources to extend the supplied ROM prefix into actual RAM/PI/SP
chronology. The million-call prefix reaches low RAM at PC ffffffff80000004;
its 41 distinct RAM PCs remain source/lifetime unknown. The larger authenticated
prefix now observes the ROM entry. Preserve both boundaries and producer clocks;
larger prefixes do not establish boot completion or executable immutability.

COP1 context consumers must preserve the canonical architectural register-zero
check. Frame callback clocks still need an authenticated join to FPR ancestry
and resident/backing lifetime; equal values or ordinals alone do not supply it.

Primary integration harvest (2026-10-11): static executable-identity hardening is
integrated, along with trace/event integrity, retained raw-fact solver gates and
Region/load/overlay validation, fetch-summary realizability and pointer guards.
Intervening-writer provenance, negative controls and measured merge indexing are
reconciled, along with the bounded two-path join candidate. The 45 branches with
core source/test candidates have been reconciled; remaining research-only evidence
needs source-contract review and composition, not automatic production promotion.
Keep TLB/cache/lifetime, producer and execution-root research separate until its
source contracts compose. Following user steering, prioritize production
consumers of validated findings using authenticated swarm receipts and focused
integration regressions; avoid repeating reference builds without a concrete
need. No new research lane. See `research/integration-harvest-20261011.md`.

1. Observe actual backing read/write transactions and unify fill/cache-operation/
   fetch/copy ordering before constructing contextual executable identities.
   Controlled completed fills, guest tag stores, hit/miss invalidation, explicit
   fill and hit/miss writeback now preserve independent reference checkpoints.
   Successful identity-mapped RAM bursts now supply actual transaction witnesses;
   translated/degraded paths and general store/copy coverage remain unclaimed.
   Remapping/degradation/failure boundary tests now preserve baseline and full
   hidden-memory hashes while retaining unsupported paths as unknown. Unify
   transaction/fill/cache-operation/fetch order now passes on a 43-record controlled
   ledger, with independent checkpoints and forged-history rejection. The parallel
   scalar-fetch, CPU-copy, RSP, exception, restore and 64-bit mutation fixtures now
   reproduce locally. Shared explicit fetch boundaries and scalar reads/writes
   pass a 95-record ledger, its prior projection and independent primitive
   fixtures. The bounded boot prefix now preserves v5 bytes/checkpoints while
   retaining 5,051,089 ordered records and 32 actual RAM-backed fills. Strict Rust
   complete-source inspection/report rechecking now agrees with independent
   Python evidence. Buffered PI component cases now join 95 ROM byte origins to
   successful RAM effects, retaining discarded lanes, failed destinations and
   separate completion. A 481-record composed fixture now preserves actual fetch/
   fill origins through equal/changed reloads, guest SW/invalidation and partial
   words. Versioned boot chronology now retains 8,823,134 records and exact ROM
   origins for 1,638,808 successful PI writes, preserving complete v0/v5 sources
   and independent checkpoints. Original strict Rust v1 inspection and complete
   report source rechecking now agree with every retained count/hash and the exact
   v0 projection. Keep finite PI effects separate from production identities;
   do not certify completion from last-write context: actual queue-container and
   source checks expose duplicate IDs, cancellation and silent insertion failure.
   Actual-container insertion identities now survive heap movement/cancellation,
   including equal deadlines and save; load remains unknown. Compose this sensor
   with actual PI request and CPU dispatch/status boundaries now passes both
   directions in a finite component fixture. The bounded boot extension
   now joins accepted requests, queue outcomes and actual dispatch/status scopes.
   Original strict Rust v2 inspection and CLI rechecking preserve complete nested
   sources; compose broader source/mutation contexts before production promotion;
   keep general cache, byte lifetime and mutation completeness separate.
   Current tags/effective addresses can differ from resident-byte history; keep
   those identities separate. A recovered synchronized-restore/cache-power
   fixture now confirms restored residency without a fill and rejects a latest-
   tuple causal shortcut; broader reset/NMI/restore capture policy remains open.
   Extend additional source-specific contexts and lifecycle sensing beyond the
   current bounded homebrew boot prefix.
   V0/v1/v2/v4/v5 import and complete-source checks preserve all legacy map hashes.
   V5 retains resident context; actual ROM-read witnesses retain canonical sources.
   Production RAM/SP/PIF backing, copy/mutation lineage and executable lifetimes
   stay unknown. Bounded identity-RAM scalar contexts and RSP IMEM fragment lineage
   now have reference evidence; neither establishes a complete mutation census.
   Reproduced SP lifecycle evidence requires actual promotion/pending mutations,
   grouped count/skip rows and modulo-bank spans; BUSY edges and pending length
   commits are insufficient identities. Keep the ares/Mupen/Gopher FULL-policy
   disagreement unresolved until hardware-oriented evidence settles it.
   Actual PIF fetch-stage backing witnesses now pass nine adversaries with supplied
   firmware. Compose declared firmware/device/offset identity with the ordered
   capture; keep physical mirrors separate and require actual in-context reads.
   Keep the supplied-firmware, fixed NTSC/6102/8-MiB/deterministic/PIF-HLE scope
   visible; the finite guest-test prefix proves neither suite completion nor whole-
   ROM coverage. Retain raw sources for chronology and rechecking, with OPEN
   solver gating. Continue RSP/exception/TLB/FPU verification before expanding
   semantic claims; Mupen's pinned homebrew limitations remain documented in STATUS.
2. Model/sense non-PI copies and executable writes beyond PI-backed snapshots.
   The constant aligned cached-RDRAM SW sensor is partial; general addresses,
   other sizes, TLB/uncached paths and CPU-copy provenance remain unmodeled.
   Reproduced COP1 stores require successful mutation sensing below integer-only
   opcode handlers, FR-sensitive payload normalization and distinct cache/backing
   events. Reference callback count is not a hardware transaction/atomicity proof.
   Extend restored target-entry sensing beyond successful dirty lookups; verified
   snapshots now explain pending same-epoch returns, and explicit source-unit
   tags identify older units still executing. Preserve boot-source/lifecycle
   obligations; keep
   speculative compilation distinct from execution.
3. Prove pointer-table data immutability and guard coverage before issuing exhaustive
   table certificates. Extend cross-block joins only with rechecked invariants;
   the current table recognizer and single-predecessor chains are restricted passes.
4. Track decompression, CPU copies, address aliases and overlay unload/reload,
   relocation and instruction-patch snapshots. PI copy sensing alone is insufficient.
5. Implement whole-ROM certificate verifiers for roots/boot, exceptions, execution
   modes, RSP identity and executable mutation. No flags may waive these obligations.
6. Design a provenance-bearing candidate adapter if promoting the partial
   spimdisasm spike; assess known-symbol signatures separately. Measure analysis
   size/cost before making scalability claims.
7. Begin tiny native integer lowering only after discovery beyond the current
   synthetic scope is demonstrably useful, with reference differential tests.
   ADR-0125/0126: the synthetic native slice is done (spike096); see the
   milestone plan at the top of this file.

Commercial-ROM native lowering remains deferred until a commercial scope is
CLOSED; the ADR-0125 synthetic vertical slice is the only exception.

Source-preserving discovery solve admission now rechecks external expectations,
raw primitives, ROM-aware installed entries and compiled roots before emitting a
closure report. Supplied instruction words must match captured compiled snapshots,
including legacy opaque identities (ADR-0117).
Preserve expected sets independently at trusted capture/import boundaries; do not
recreate them from edited submissions. Compose other source domains, remaining
derived projections and complete sensor/lifetime obligations next (ADR-0114).

Cached general-root v1 now composes full-line slot replacement and the canonical
pinned NMI/reset/power profile with word-specific captured backing ancestry.
V2 additionally cuts all prior observer ancestry at successful restore boundaries,
including repeated equal snapshots; snapshot labels supply no byte authentication.
Retain v0/v1 contracts. Connect actual root-entry/fetch chronology, complete
writers/cache/mapping census and authenticated snapshot/component epochs before
using these finite receipts as lifetime or whole-ROM proof (ADR-0115).

The user-supplied Ocarina of Time US revision-2 ROM has an ignored local conditional
entry-window baseline: 293 blocks, 45 indirect sites and an OPEN whole-ROM report.
The explicit initial mapping is a hypothesis, not authenticated boot evidence.
Use it to prioritize real executable discovery; keep game bytes/maps/traces local.

Keep user ROMs in ignored `roms/` and derived maps/traces in ignored `artifacts/`.

SP writer/fetch composition now joins normalized captured sinks to actual CPU
executable bank reads with externally retained complete-source receipts. Same-
value writers replace candidates and contradictory bytes cannot revive from
later equality. Compose decoded CPU/RSP producers, PIF initialization, complete
lower-sink census and lifecycle/request identity before claiming ultimate origin
or RSP closure. Existing v3 reports/CLI remain unchanged (ADR-0116).

The decoded RSP -> DMEM -> CPU register -> IMEM chain now has a generic bounded
Rust consumer for the authenticated unified source (ADR-0118). Preserve the
actual source clock, mixed/unknown byte parents and whole-register definition
cuts. Extend incoming register/initialization ancestry and unify this producer
context with boot mutation/executable-fetch sources before claiming RSP identity,
complete mutation coverage or general executable consumption/lifetime. Controlled
v3/v4 now establish discrete RSP and CPU consumption on their own source clock;
they do not grant whole-ROM execution coverage. Separate RSP
scalar/DMEM-DMA candidate histories cannot be joined by equal labels or payloads.

The supplied game's IPL3 matches the pinned reference CIC-6105 checksum. Explicit
6105 capture/import support and the retained twenty-million-call prefix are now
available. Reuse those authenticated sources; do not relabel a 6102 run or the
conditional static map as game boot evidence.

Cached Word reads now share dcache_writeback's resident state and full-line
export ancestry (ADR-0119). Controlled v25 joins actual decoded LW/register,
backing-writer roots and IMEM/RSP consumption on the original clock. Compose
broader cached mutations/writebacks/dispatch with this normalized operation stream.
Controlled v26 now joins actual Word SW and complete HitWritebackD exports to
both cached/uncached operand consumption and IMEM/RSP execution; wider stores,
other cache operations and general mutation/lifetime coverage remain open.
Current backing content cannot replace the source of a cached pointer. Keep
physical immutability and complete writer/guard/target/cache-lifetime coverage
separate; the finite read/writeback report grants no table certificate. The
physical-immutability prepared histories remain pending composition with an
authenticated snapshot and complete mutation census.

COP1 physical FPR byte lineage now composes with canonical completed uncached
backing-store normalization (ADR-0120). Preserve the same source clock and
independent normalization contexts. Join actual backing writer ancestry and
executable fills/fetches next; cached COP1 loads/stores, arithmetic/other FPR
writers, producer census and context/lifetime still need source evidence. The
96-case fixture's declared instruction/GPR seeds and modeled physical selections
are checked against actual selected-register snapshots and backing effects;
they are not a complete guest instruction/writer capture for arbitrary ROMs.

Ordered cached SD/SDL/SDR subwrites now compose with resident-to-backing ancestry
under the explicit v2 kernel32/BEV1/prefilled direct scope (ADR-0121). Preserve
actual primitive callbacks rather than deriving their clock from final snapshots
or splitting a Double store into invented Word writes. Bind upstream GPR writer
ancestry and subsequent executable fills/fetches to these byte occurrences next.
Uncached/TLB/degraded/cache-miss paths, other actors, lifecycle and complete
mutation coverage remain separate obligations; no whole-ROM gate is promoted.

Target-qualified root classification now preserves VR4300 cache-error exclusion
and existing numeric exception candidates as distinct proof results (ADR-0122).
Carry the explicit target and hardware authority through future root-universe
certificates. Exclusion is not emulator silence and numeric selection is not
reachability, handler provenance or lifetime. Reset/NMI/interrupt/watch/root
census obligations remain OPEN; do not invent a CacheError handler for VR4300
or apply this exclusion/vector contract to generic MIPS III.

EBus hidden fetches require a separate derived-bits source witness or Unknown; retain actual read context and hidden-storage lifecycle before any origin promotion (ADR-0062).

Successful TLB-mapped uncached fetches now have finite source evidence; retain current translated/post-endian addresses in each access context and add mapping-generation/lifecycle evidence before proving alias history (ADR-0063).

Compose the reproduced translated scalar raw-read and delivered-transform witness with actual access contexts; decide degraded executable-image identity explicitly and retain unsupported paths as unknown (ADR-0064).

Retain full per-byte outgoing D-cache lineage before actual writeback and slot replacement. The reproduced clean-lane overwrite counterexample rules out dirty-mask-only provenance (ADR-0065).

General mutation sensing must normalize at the actual storage sink: CPU SB/SH reaching SP IMEM replaces a full Word and can carry upper source-register bytes (ADR-0066).
Bounded `cpu_sp_subword` production normalization now consumes an exact decoded
context plus completed Word effect. Compose it with authenticated ordered
writer/mapping sources; the primitive does not establish those sources' coverage
or executable lifetime.

PI read-side save/load/rejection now has independent actual-reference reproduction. Compose request/queue outcomes with the bounded boot stream while retaining RDRAM-to-PBUS data effects separately from scheduled status.

Carry both resident generation and mutation revision into exact writeback scopes. The primary four-phase fixture and six forgeries pass; compose broader store/epoch sensing before production lineage promotion (ADR-0067).

Compose RDRAM SB/SH successful byte effects with the general mutation sensor and later cache writeback; nominal width remains sink-specific and failed attempts supply no effect.

Distinguish ordinary RSP DMEM stores from CPU/SP-DMA IMEM sinks. Preserve observed lineage if those DMEM bytes are copied into executable IMEM later (ADR-0068).

Bounded boot request/queue/dispatch composition now passes the full prefix under ADR-0069. Original strict Rust v2 inspection and complete-source report rechecking now preserve exact nested v1/v0/v5 validation and unknown/unbound/canceled boundaries. Explicit v2 CLI inspection/rechecking now preserves version separation and input protection. Compose broader mutation/source contexts before promoting scheduling evidence into production identities. Keep finite scheduling facts separate from byte-transfer timing, lifetimes and whole-ROM closure.

Observed PI byte-chain replay now passes full independent corpus/source checks (10,954 fetches, 185 samples). The separate finite CLI inspection/rechecking now passes byte-order/source/report/input gates. Validate actual CPU SP DMEM/IMEM backing-read sensing for the remaining 596,991 SP fetches. Preserve raw writer/fill/read ordinals and mixed/unknown bytes; keep mutation coverage and executable lifetime uncertified. See `research/boot-pi-fetch-lineage.md`.

The controlled actual CPU SP sensor now passes independent baseline/disabled/
repeat state and seven forgeries (ADR-0072). Compose it into a separate boot
history version with exact prior-source projection, then add a strict original
Rust consumer. Keep CPU DMEM/IMEM backing separate from ultimate ROM origin and
RSP-originated DMEM mutations; PIF reads/initialization are the next source gap.

The latest RSP worker closeout now reproduces the nonzero SRV bit-12 adversary
(29 decoded probes); no ordinary RSP store gains an IMEM sink. Include those
actual DMEM mutations if extending CPU-to-SP source lineage.

The v3 SP boot extension now preserves all prior sources/checkpoints on the
10,000-call capture. Finish full-prefix independent replay and strict source-bound
Rust consumption, then compose actual PIF backing and SP producers. Its eleven
standalone forgeries supplement the actual controlled sensor adversaries.

Strict Rust v3 inspection/source rechecking now passes the full retained capture;
finish the independent full Python comparison and expose the tested finite CLI.
Actual PIF reads are the remaining fetch-backing domain; ultimate SP producers,
ordinary RSP DMEM mutations and executable lifetimes remain separate.

The v3 CLI now passes all source/report/version/input gates. Finish the full
independent comparison, then compose actual PIF-ROM backing reads and normalized
PIF backing writes. Keep SI busy-latch/lockout/RAM/cached paths unknown unless an
actual in-context ROM backing read is observed.

Full v3 Python/Rust replay and source binding now agree, including 512 unknown
out-of-range DMA receipts. Compose actual PIF ROM reads/writes next, retaining
current backing separately from supplied-firmware payload equality and ultimate
SP origin. The 2055 PIF fetches remain the last backing-read domain in this prefix.

PIF write probes require a correction to the earlier next-step wording: pinned
ares ROM backing is read-only, so delegated attempts are distinct no-effect
records. Finish complete v4 source/replay comparison and strict Rust integration.
Then pursue ultimate SP producers and actual RSP DMEM mutation chronology;
backing reads alone cannot certify executable lifetimes or whole-ROM closure.

Strict v4 PIF full-source replay and independent comparison now pass. Backing
identity exists for the observed PIF/SP/RAM fetch domains in this fixed prefix;
this does not establish ultimate SP producers or a mutation census. Continue
actual RSP DMEM mutation chronology and producer evidence, keeping executable
lifetimes, boot/exception coverage and whole-ROM certificates open.

SP producer inventory requires subword and FPR producers as well as integer SW:
2256 SB and six SWC1 effects occur in the verified prefix. Preserve actual full-
Word SP normalization and FR-sensitive FPR semantics. Next, validate scoped RSP
DMEM sinks and then compose actual instruction/dataflow evidence; same-PC/value
matching alone is not ultimate source provenance.

Controlled RSP DMEM sink replay now passes actual scalar/vector/wrap/same-value
cases. Controlled CPU SP refetch composition now also preserves scalar/vector
partial writers, neighboring writes, same-value CPU overwrite and unknown
foreign-sink cuts under independent checkpoint checks. Extend actual producer
instruction/dataflow evidence and complete-history source rechecking before
any broader promotion. Keep initial byte snapshots explicit; neither matching
values nor instruction PCs prove ultimate producer dataflow/lifetime.

Adjacent uncached LW/LWU-to-SW source evidence is now reconciled with full captured
GPR continuity, sequential PCs and independent instruction checkpoints. Before
production copy promotion, compose complete execution-attempt/source histories
and eventual executable consumption. Keep cached, transformed, non-adjacent,
interrupt and lifetime cases unknown; the callback alone is not a census.

The one-step adjacent XORI source contract is also reconciled, including explicit
zero-immediate transform identity. Preserve this exact def-use boundary when
composing broader producer evidence; matching transformed values does not select
a source generation. Decompression/relocation and general dataflow remain open.

Actual decoded CPU SW/SB/SWC1-to-SP context now replaces caller-supplied operand
metadata in the controlled fixture. Compose this precise GPR/FPR source witness
with complete boot histories and earlier register lineage before production
promotion. Keep unscoped writes unattributed; preserve guest-byte snapshot view
and reference-specific full Word normalization without inferring hardware truth.

RSP DMEM through actual CPU LW/GPR/SW to IMEM now has a reconciled finite
composition contract with mixed/unknown source bytes separate from sink
generations (ADR-0091). Before promotion, compose actual executable consumption
and complete lifetime/attempt histories. The reference fixture's source register
operands are measured; their ultimate ROM/DMA ancestry remains unresolved.

The XORI/cache branch's unmodified four-scenario behavior probe is now retained.
Compose actual captured transform definitions with cache resident/revision,
completed writeback and fill/fetch events before issuing ancestry certificates.
Abstract generation chains and identical final payloads cannot fill missing
measured edges; preserve stale and early-refill controls (ADR-0092).

Large-PageMask/cache-remap behavior is now retained under spike 049. Bind actual
historical translation and mapping/context operations to measured fill/writer
receipts before production promotion; a miss flag cannot authenticate new
resident or backing generations. Preserve temporary-unreachability controls and
the unresolved ares/Gopher index-source disagreement (ADR-0093).

PI copy/cache visibility now retains complete finite source/sink/fill/fetch
regressions under spike 050. Compose actual queue-container lifecycle identities
only for completion claims; do not require completion to retain successful byte
writes or use completion to refresh cached code. Extend general writer/census/
lifetime evidence before production origin promotion (ADR-0094).

Forward DMEM ingress now retains strict paired Word lane/source-read contracts
under spike 051. Compose actual request identities, RDRAM storage ancestry and
RSP consumer definitions before issuing executable provenance certificates.
Missing successful source reads remain unknown; nearest equal-valued reads
cannot identify a lane. Directly staged component calls do not close scheduler,
writer-census or executable-lifetime obligations (ADR-0095).

RSP store-domain behavior now retains all scalar/vector store families in the
finite spike 052 matrix, including aligned SRV's zero-byte control. Preserve the
pinned interpreter/source DMEM-only classification when composing RSP writers,
while retaining CPU-window, DMA and out-of-band IMEM mutations independently.
Hardware/recompiler, task activation/retirement and lifetime completeness remain
separate obligations (ADR-0096).

Guest EntryHi/cache reactivation now retains the finite spike 053 controls.
Compose measured context writers with installed mapping, backing and resident
histories before issuing certificates; internal snapshot equality and miss counts
are insufficient. Preserve inactive residents until a verified replacement or
invalidation boundary, and retain the ares/Gopher index disagreement (ADR-0097).

The finite TLBR/cache controls now share that obligation under spike 054.
Keep successful context loading distinct from operation occurrence: TLBP and
out-of-range TLBR do not supply a successful EntryHi load at the pin. Compose
actual histories before production promotion; repeated snapshots do not recover
same-value writer identity (ADR-0098).

Original Rust CPU-copy replay now consumes the validated adjacent LW/LWU and
one-step XORI history protocol through inspect/verify CLI commands. It preserves
source-read and sink-write ordinals under an external complete-source receipt.
Compose those witnesses with storage writer ancestry and eventual executable
consumption next; a bounded copy witness is not a mutation census or solver
certificate (ADR-0099).

The separate captured-definition consumer now retains live read identity through
unrelated register reads/NOP and one XORI, with phase/ORI/failed-read cuts. Compose
these qualified read/write identities with storage and executable consumers;
do not infer general source census from a contiguous captured sequence (ADR-0100).


Production now has a bounded general/TLB exception-root selector (ADR-0101).
Whole-ROM root work must next authenticate the exception classification plus
BEV/EXL/address-mode chronology, compose each selected root with handler-byte
provenance and cache/mapping lifetime, and independently justify interrupt,
watch, reset/NMI and cache-error roots. Numeric vector derivation is neither
reachability nor a complete execution-root certificate.

Production now has source-bound TLBWI operation generations (ADR-0102). Compose
them with authenticated mapping content, PageMask/ASID/global state, TLBWR and
other mapping/context operations, actual fill/resident histories and save/restore/
reset chronology before using them in executable-lifetime or translation proofs.
A same-content legal TLBWI remains a distinct operation; snapshot inequality and
equal payloads cannot recover occurrence or selected-slot identity. Complete
sensor coverage and a full TLB mutation census remain OPEN.


The bounded BEV=1 general-root PIF composition now authenticates one exact
singleton observed handler fetch from complete PIF sources (ADR-0103). Next root
work must bind that fetch to authenticated exception occurrence/classification and
BEV/EXL/address-mode chronology, then compose cache/mapping executable lifetime.
Reproduce BEV=1 refill/XTLB source behavior separately before extending the rule,
and independently discharge interrupt/watch/cache-error/reset/NMI roots. Repeated
coalesced PIF observations, equal returned bits and matching mirrors stay OPEN
without per-occurrence same-fetch backing identity.

Production now also has a bounded source-bound cached BEV=0 general-root Word replay
(ADR-0104). Compose it with authenticated exception classification and BEV/EXL/mode
chronology, complete backing/cache/mapping mutation histories and full handler spans
before treating a selected root as executable provenance. ADR-0103 separately binds
one BEV=1 root occurrence to exact PIF backing; neither decision proves root
reachability or census completeness. Extend separately to TLB refill/XTLB roots,
interrupts, reset/NMI and other execution roots. Missing residency stays UNKNOWN;
equal current bytes never recover a writer or fill generation.


## PI interrupt producer composition remains open

Production can replay an authenticated bounded PI completion -> raw MI.PI -> MI mask/poll -> CPU RCP-pending chain without borrowing PI-copy equality or latest-request state. Next work must independently bind accepted request/queue dispatch to completion observations, compose with the generic CPU interrupt eligibility/root gate, account for other MI/timer/software producers plus reset/save/restore chronology, and prove source/sensor completeness for the declared scope. Unknown chronology remains OPEN; this is not a producer census or root-closure waiver.

The bounded generic maskable gate now exists in `interrupt_roots` (ADR-0106).
Join authenticated producer/status/BEV chronology to the same boundary before
using its numeric candidate for executable-root evidence. Suppression at one
boundary does not exclude that root from the execution model. Actual transfer,
handler-source/lifetime and complete root census still require separate proof.

Bounded PageMask half/offset geometry now exists in `tlb_geometry` (ADR-0107).
Compose it only with an independently selected/authenticated mapping and retain
the actual translated transaction address. Geometry alone does not establish
ASID/global/valid/dirty/CCA, overlapping-entry selection, operation generations,
resident/backing lineage or executable lifetime; larger unvalidated masks reject.

Bounded guest Cause-write operation replay now exists in software_interrupt
(ADR-0108). Connect authenticated raw operand/source history and actual
producer/Status/BEV chronology to the same interrupt boundary before root
composition. Preserve successful same-value writes as distinct operations and
keep hardware pending producers independent. Saved state-row adapters do not
establish callback chronology or complete sensor coverage.

Mapped uncached fetch/backing joining now exists in tlb_fetch (ADR-0063), using
strict tlb_geometry. Compose its opaque mapping/context references with actual
TLB-operation and CP0 writer history before claiming mapping ancestry/lifetime.
Preserve virtual aliases and same-address remaps as independent fetches. Cached
residency and unsupported region/endian geometry still need separate evidence.

TLBWR operation replay now exists beside TLBWI/TLBR (ADR-0109). Compose explicit
selection/write generations with authenticated normalized mapping content and
the same fetch context; neither Index nor equal content supplies that ancestry.
Keep the source/census, ASID/global/CP0, cache and reset/restore obligations OPEN.

Resident-to-backing writeback replay now exists in dcache_writeback (ADR-0067).
Compose actual CPU copy/transform/store ancestry with its mutation ordinal and
byte lanes, then bind exported bytes to subsequent executable fills/fetches.
Cached mutation alone cannot refresh instruction residency; TLB/alias and epoch
transitions require independent authenticated context and lifetime evidence.

CPU copy's captured-writer chronology now records phase-scoped successful Word
stores (ADR-0110). Complete writer coverage is still required before turning a
compatible captured candidate into actual source ancestry. Compose external
device/RSP/DMA and cache/epoch cuts explicitly; observed contradictory reads
already revoke stale candidates and equal later values do not restore them.

Completed Word SC -> SP normalization now exists in cpu_sp_conditional
(ADR-0111). Compose its context/effect identities with an independently complete
writer stream and actual IMEM execution before granting executable ancestry.
Missing sinks are absence of evidence without source completeness. SCD, cached/
mapped aliases and reservation lifetime remain separate unvalidated obligations.

Bounded observed Count/Compare operation replay now exists in timer_interrupt
(ADR-0112). Compose independently authenticated timer transitions with Status/
BEV at the same interrupt boundary and the actual handler source. The v0 schema
has no elapsed-time event: unrepresented Count progression rejects. Resolve
reference scheduling disagreements with stronger evidence before extending it;
finite replay does not authenticate decoded guest writes or complete the census.

Source-available discovery-trace manifests now exist in evidence_manifest
(ADR-0113). Preserve the expected exact source set at the trusted import/build
boundary before edits; do not regenerate it from an edited map or trace. The
explicit primitive verifier rejects missing/unexpected sessions and reuses full
source projection checks. Integrate that preserved input at future certificate
boundaries and retain stronger entry/ROM checks plus typed adapters for other
domains; a manifest over an incomplete sensor does not establish closure.

## After ADR-0218

The Paper Mario residual-dispatch run faults 3 at the boot stub jump: the
target is main-program code that no lowered entry covers (apparently generated
or relocated at boot). Next: discover and lower that code (boot-generated text
capture) so the run proceeds to the remaining residual sites.

## After ADR-0220

Boot text capture now carries the Paper Mario run past the boot stub to a
computed call (154 PI DMAs). Its target is a real function that only a ROM
checksum names, so discovery never reaches it and the native dispatch faults 3.
Next: record the targets that unproven indirect calls take during the
analysis-time pinned-ares replay and add them as discovery roots, never as
target certificates, so code reached only through computed calls is lowered.

## After ADR-0222

Paper Mario now passes its integrity check and stops at a residual `jr`
switch. The map already holds the five case labels as candidates; residual
dispatch covers only function entries. Next: let a residual site also
dispatch over its own candidate and observed targets (labels for a jump,
functions for a call), still validation-only and fail-closed otherwise.

## After ADR-0224

Paper Mario's residual run reaches VI 3 and submits its first audio task,
whose RSP microcode is not among the ROM-derived texts. Next: find where that
microcode comes from in the ROM and extend extraction generally (compare the
unfinished OoT microcode work on `experiment/oot-rsp-0221`).

## After ADR-0226

Observed call targets after non-return layout code can now pass discovery and
the guarded address-taken solver when replay evidence is present and
`executed_start` succeeds. The synthetic regressions and mutation checks pass.
The landed-tree visible rerun passes the former target; continue with the
relocated-call and silent-audio frontiers documented above and in research.


### GoldenEye native refill continuation

After the ADR-0300 exact-tree gate and controls, establish verified guest
SDK kernel-global bindings and synchronize the host scheduler current-thread
state so the general pager can continue beyond PC 808101e4 toward logos/title.
Mapped data misses, delay-slot fetch retries, handler host calls and
redirecting/nested execution remain explicit refusals in the prepared scope.


### GoldenEye guest kernel interoperability

Continue verified SDK current-thread publication, raw MI interrupt-mask
access, and guest fault-event/dispatch interoperability. The guest general
handler must wake and run the pager through checked native context handoffs;
its final engine mapping must result from guest paging. Preserve exact
source and continuation guards when suspending an exception scope.


### Native guest pager continuation after ADR-0302

Expose the modeled MI interrupt mask through a verified raw register interface,
then bridge source-verified SDK fault-event delivery and dispatch. A native
exception scope must suspend with its owning context while the pager runs,
restore checked Status/EPC and register state, then reapply mapped-source
guards. Test ownership/retirement, source mutations and refusal paths against
the pinned reference before another integration.
