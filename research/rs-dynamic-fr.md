# Dynamic Status.FR and Rogue Squadron continuation (ADR-0276)

Prepared base: `39f8494630a887fcc0ec6f06d214f84507c10ee9`.
Worker: `rs-dynamic-fr-3-135e319b`, branch `t3/rs-dynamic-fr-3`.
The uncommitted candidates in `t3-a06cc1bc` and `t3-f154da9f` were read and
recovered, without modifying or removing either worktree. Checkpoints include
`a190d978`, `eba66d76`, and `ad9c7a29`; the canonical landing is recorded in
issue #4 and ignored `target/receipts/rs-dynamic-fr/integration.json`.

## FR pattern and reference semantics

The first refusal is MTC0 Status at `80013c34`, requesting `2400ff01` from
`2000ff01`. Its function at `80013c14` is a bounded leaf: save even FPR pairs
in FR0, set FR, operate on independent single-precision registers including
odd indices, clear FR at `80013e14`, restore the saved pairs and return.
The FR1 region uses single-precision operations, rather than double-precision
arithmetic; the register storage is nevertheless 64 bits per independent FPR.

Resident ROM inspection finds these related routines. Register sets describe
encoded accesses in the FR1 region, not a claim that every branch was executed.

| Entry | Set FR | Clear FR | FR1 registers | FR0 FPR work | Calls in region |
|---|---|---|---|---|---|
| 80013268 | 800132bc | 80013790 | 4..11,16..31 | save/restore 20,22,24,26,28,30 | 80013164,800131c8,80013238 |
| 800139e8 | 80013a18 | 80013be8 | 0..12,16..19,28..31 | save/restore 20,22,24,26,28,30 | none |
| 80013c14 | 80013c34 | 80013e14 | 0..27 | save/restore 20,22,24,26 | none |
| 80013e38 | 80013e44 | 80013ee8 | 0..14,16..19 | none | none |
| 80013ef4 | 80013f00 | 80013f8c | 0..8,12..14,16..19 | none | none |
| 80013fe4 | 80013ff0 | 800140ec | 4..19 | none | none |
| 800140f8 | 80014104 | absent | 0..14,16..26 | none | none |

The last routine returns with FR1. The first is not a leaf. Five of these
writers appear in the retained emitted map; the last two are ROM candidates,
not newly certified executable entries. The implementation does not assume
that all FR regions are leaves, that calls preserve FR, or that returns reset
it. Unknown entry/call/join facts retain the map layout with its runtime check;
an incompatible path still faults. Interprocedural FR1 specialization remains
outside this bounded change.

Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` was inspected read-only:
`ares/n64/cpu/interpreter-fpu.cpp` and `interpreter-scc.cpp`. Its FR mode setter
does not move FPR bits. Transfer, arithmetic source, second source and destination
access rules differ in FR0; simply pairing every odd operand would be wrong.
Plaid retains its existing canonical `f[32]` storage and exact access helpers.
FR changes update Status/mode without shuffling or clearing any FPR bits.

Reference license: ares ISC, with its upstream notices preserved by the existing
separate oracle builder. No upstream implementation, SDK/game instruction body,
ROM, trace payload or game asset was copied into production or committed.

## Compiler and scheduler contract

`crates/plaid-lower/src/fr.rs` computes known low-word GPR bits and Status.FR
over the actual emitted CFG. It models Status reads/writes, logical masks,
moves/shifts, GPR clobbers, joins, loops, linking instructions, jump delay slots
and annulled likely slots. Relocated immediates are unknown. Calls kill facts;
the map default is never seeded as a constant. Functions without Status writers
avoid allocating the full analysis state. Every emitted FPR access still checks
the selected mode before touching FPRs, memory or floating-point state.

An SDK-owned raw Status write may change only FR. Any simultaneous IE, interrupt
mask, CU1, privilege or other Status change refuses before modifying state.
Existing kernel/CU1 and non-SDK Status rules remain. Thread save/restore preserves
all canonical FPR bits and FR mode, including plain runtime contexts; new SDK
threads still begin in FR0. Saved SDK Status is the authority when available.
No native artifact gains a runtime guest decoder, interpreter, JIT or fallback.

The deterministic verifier `runtime/test_dynamic_fr.py` compares 12 native/ares
full states: three fixtures, both map defaults, with and without SDK ownership.
It initializes all 32 FPRs with nonzero distinct hidden halves, writes in FR0,
reads in FR1, writes independent odd FR1 registers, returns to FR0 and observes
aliasing. It covers odd double transfers/arithmetic, single source/ft/fd rules,
repeated loop switches, a jump slot and taken/annulled likely slots. Compared
state includes GPRs, all FPR bits, PC, HI/LO, FCSR/FCC, Status and every output
memory word; successful oracle runs also reject exceptions. Inverting an inferred
FR1 guard produces fault11. A conflicting-mode join accepts the checked FR0
path and refuses FR1 before the FPR access. The scheduler fixture verifies
preemption between FR1 and FR0 threads; the Status contract also verifies rejected
writes leave the entire state and interrupt enable unchanged. Retained 256-case
pinned-ares Status/event tests remain required.

## Measured bottleneck and the next write refusal

FR support initially ended a 30s run at VI122/fault0,57 graphics/65 audio tasks.
The input run ended at VI120/fault0. RDRAM readback shows the copyright screen
with a rendered Expansion Pak model, 28024 nonblack pixels. The old fault12 at
VI114 is passed, but this alone does not establish title/menu progress.

A private timing-only runtime measured 30.990s in native RSP execution, of which
30.889s was 25713 synchronous raw RDP calls; presentation took only 0.008s.
A private bridge narrowed 20000 calls to 23.317s total,22.473s RAM synchronization,
0.126s RDP handling,0.020s writeback. The RSP DPC callback was routed through the
CPU bus, marking every RAM page dirty on every register write. During a synchronous
native RSP task no CPU executes. Suppress only that CPU-wide invalidation while
RSP code runs; task entry and actual CPU submissions retain full invalidation,
and RSP DMA still marks every affected page. Commands, synchronization boundaries,
DPC events and framebuffer readback order are unchanged.

`runtime/test_rsp_dirty.py` executes real lowered RSP code and asserts submission
page counts 2048,0,1,2048, including exact page4 DMA, unchanged command bytes,
RDRAM DMA output and a subsequent CPU write. Restoring the unconditional guard
changes the census to 2048,2048,2048,2048. The mutation uses a private runtime copy.
The ordinary native graphics frozen/wrapped-command and automatic-LLE tests remain.
No RT64 production patch or shared DLL rebuild is required; the private bridge
profiler is not deployed as an artifact dependency.

With sparse dirtiness, the game reaches VI344 in about5s native execution
(7.047s including full-RAM JSON readback),281/282 graphics tasks, then refuses a
runtime clear starting at `800960e0`. A diagnostic-only guard identifies the first
offending proof byte at physical`96660`,overlay1,active count0,caller RA`80003d18`.
This is overlay retirement/reuse after the fade, not an active instruction write.

Proof inputs now have the same lifetime as their overlay binding. A write to
inactive bound proof data revokes that binding; any active or suspended native
frame still refuses. Every subsequent bind must compare all original code and
proof ranges again. Fixed base-image proof data remains immutable. Existing
relocation, ambiguity, alias/mapping and unknown-target guards remain.
`runtime/test_slot_data.py` compares actual guest proof write/restore/reentry
against pinned ares full state, and checks altered proof refuses binding,
restored proof rebinds, active code/proof writes refuse and guard removal is killed.
This extends ADR-0275's permanently immutable idle-proof policy without letting a
live native dispatch use changed evidence.
The first full runtime gate also caught the old permanent-idle policy in the
retained mapped/TLB overlay contract. That contract now verifies active refusal,
idle revocation, changed-proof reentry refusal and restored-proof rebinding at
the same physical mapping, alongside all previous alias/generation guards.

## Final continuation and acceptance receipts

After idle-proof revocation the 30s requests stop earlier on a new fault:

| Run | VI | Fault/PC | Graphics/audio | PI DMA | Elapsed including readback |
|---|---|---|---|---|---|
| ordinary | 351 | 3 / 8003dc58 | 276 / 329 | 58 | recorded in rs.json |
| Start/A | 349 | 3 / 8003dc58 | 214 / 275 | 58 | 7.297s |

The transfer is JR v0 to`8003dc68`, reached through a halfword selector bounded
by`4c` and a table based on runtime t4=`80031740`. The retained map already records
this as an unresolved site, with no certified targets. No address is added by
hand. Establish table-base provenance and discover its internal targets next.
The final sampled framebuffer is mostly black with a noisy lower portion after
the transition; it is not a title/menu or gameplay claim. The earlier readable
copyright/model image is saved separately as `copyright-native.png`. Stop JSON,
RDRAM and PNGs are ignored under `target/receipts/rs-dynamic-fr`.
CPU `native_complete:false` and19 residual sites remain, as does incomplete RSP
coverage. Finite differentials do not certify every FR program or whole-game closure.

All native/game runs use `SDL_AUDIODRIVER=dummy` and visible windows. VI/fault/PC
come only from stop JSON; visuals come only from framebuffer/RDRAM readback.
Control builds use retained content-bound maps, current solver/lowering/runtime
and newly generated RSP registries, with ordinary source/compiler/header/flag
object checks. This is not a fresh-discovery claim for those controls.

The final gate driver records exact commands, exit codes, timings, base and tree
in `gate.json` and per-command logs. Required commands are:

```
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

Controls are PM/BK/MM/SF64/OoT30s; MP2 uses Start600/1250 and
A1360/1440/1520/1600/1680/1760 (all4VIs); OoT save-load uses60s,Start1200 and
A1400/1550/1700/1850 (all4VIs). Their stop JSON, commands, timings and MP2/OoT
readback PNGs are retained alongside the gate. The issue #4 closeout records the
observed results and final canonical SHA after all gates and visual checks pass.

Default GCC15.2 is used. Writable debug/release/native artifacts live in this
worker's private `X:/Plaid-worker-artifacts/rs-dynamic-fr-3` backing; previous
worktrees and shared reference/shim junctions remain untouched. No child agents,
README changes, shared reference fetch, force push or protected recursive deletion.
Integration requires an immediate refetch, exact-base equality, one direct-child
validated commit, ancestry check and plain `git push origin HEAD:main`.
