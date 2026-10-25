# Rogue Squadron renamed table bases and short RSP descriptors (ADR-0277)

Prepared base: `51e5aaf9d06e400976739dd604610d2b642b9670`.
Worker: `rs-title-4821f3a3`; branch: `t3/rs-title`.
Checkpoint commits preserve the failing regression, implementation and contracts.
Final canonical SHA and exact-tree gate/control receipts are recorded in issue4
and ignored `target/receipts/rs-title`.

## CPU jump and byte provenance

JR v0 at8003dc58 loads a guarded76-word switch from80031740. The selector is
LHU v1,0(a0) at8003dc40; SLTIU v0,v1,4c and BEQZ at8003dc48 bound the
in-range edge. SLL v0,v1,2 is the branch delay slot. ADDU v0,v0,t4 and LW
v0,0(v0) select the target. LUI v0,8003 at8003dbc4 and ADDIU t4,v0,1740
at8003dbc8 establish the table base, before v0 is reused for other work.

This is resident initialized data, not a BSS-built table or overlay relocation.
ROM32340..32470 supplies the304 bytes. The native image loader installs that
resident ROM window before guest entry; the observed stopped RDRAM matches
all76 words, SHA2567ad5f872f627d297944c5fd0e0d27ba2689610e3a6299a6e6dbcf739d07e7016.
There is no evidence of a later table writer at this site. Target counts:
8003dc60 once,8003dc68 sixty-one times,8003dc94 fourteen times.

The backward table proof previously accepted ADDIU only when destination and
source were the same register. It therefore lost t4's constant lineage.
The general change follows ADDIU's actual source and accumulates signed word
offsets modulo2^32, whether the base is formed before or after the scale.
Unknown sources, overwritten scales, CFG entries, call effects and other
existing proof barriers retain their conservative behavior.

8003dc68 already existed as a directly decoded local branch destination, with
a native label. It was not a callable entry in the residual global dispatcher,
nor a candidate of this JR. Recovering the ROM-derived candidates adds local
native switch cases; it does not invent an independent function ABI entry.
Some predecessor paths remain unproven, so this site retains candidate-only
evidence and residual native dispatch. Its loaded target is checked against
emitted native destinations; every other target faults. No table-immutability
or whole-program closure theorem is claimed from the observed equality.
Fresh discovery reduces residual sites19->16; native_complete remains false.

Pinned ares9408cb43d4948fc3ea6e152a307a34348df3fe04 agrees in an analysis-only
bounded replay at this point: stopped low-word GPRs are sign-extended, FPRs and
HI/LO initialized to zero, and the captured RDRAM is replayed from8003dc40
through8003dc94. Selector1 loads8003dc68 and executes both JR/J delay slots
without an exception. This is not whole-game natural-boot agreement or proof
of unobserved register high halves. The snapshot is an oracle input only,
never a discovery/native-build input. The pinned CPU JR/J, load and D-cache
handlers were consulted read-only (ares ISC); no reference implementation,
SDK/game instruction body, ROM or asset is committed.

## Deterministic verification

The renamed-base Rust regression fails on the original implementation. The
14 dispatch-extension and91 table-related integration tests pass with the
change. Cases include renamed LUI/ADDIU registers, signed chained offsets,
scheduling after the scale, unknown source, overwritten scale and changed
proof bytes; retained guard/loop/generation contracts remain required.

runtime/test_table_base.py is part of runtime/test_runtime.py. Five synthetic
native/ares full-state comparisons cover selectors0,1,2,3,ffff. They compare
all32 GPRs/FPRs, HI/LO, PC, FCSR/FCC and64 output memory words, reject oracle
exceptions, and assert the JR delay-slot effect and default-path behavior.
A guest write to the selected table cell faults2 before corruption. Moving
only its protection interval out of the way in a private generated C mutation
allows the corrupted pointer to reach the native target guard, which faults3.
No runtime guest decoder, interpreter, JIT or fallback is added.

## RSP continuation

Passing the CPU switch reveals a new native RSP db0 placement. The first30s
request stops VI352,CPU fault0/PC00000000,gfx263,audio325,PI150 with
stop=unlowered RSP code. Readback is black,400x240. A second diagnostic run
stops VI364,gfx205,audio290 with the same IMEM identity. The64-byte prefix at
db0 uniquely matches ROM20840; its full sampled216 bytes also match.
RDRAM1fc40 holds the same prefix, at task ucode1ebe0+1060.

The rooted packed table in task data contains descriptors d3/d38,21f/e10,
2b/1030,22f/1060,... . The third record requests48 bytes after doubleword
rounding; it is a valid SP DMA record but smaller than the candidate filter's
64-byte minimum. The scanner incorrectly broke the whole table there, so the
following560-byte db0 overlay and later records were never proposed.
Continue traversal past structurally valid short records and pass them to
contextual content filtering. Keep invalid-selector/source/destination,
missing-word, bounds, rooted-loader and minimum-two-descriptor checks, plus
all content/startup/per-fetch native guards. No captured bytes seed candidates.
A synthetic short record between two valid overlays verifies traversal in
both the core descriptor parser and actual ROM-to-native RSP registry test;
a short scalar DMA/return path executes correctly, copies the expected RAM word
to DMEM and preserves its continuation; altered live text still refuses.

## Run and integration policy

All game/native runs use SDL_AUDIODRIVER=dummy with visible windows. VI/fault/PC
come from stop JSON; visual evidence comes from RDRAM/framebuffer readback,
never desktop capture. Controls are PM/BK/MM/SF64/OoT30s, MP2 destination
selection with the exact supplied Start/A list, and the60s OoT save-load repro.
Retained control maps bind their ROM contents; current solver/lowering/runtime
and newly generated RSP registries are rebuilt using ordinary compiler keys.
This is not a fresh-discovery claim for those controls. RS discovery is fresh.

Default GCC15.2 is used. C: exhaustion during the first Rust build was recovered
by moving only this worker's generated debug/native artifacts into private
X:/Plaid-worker-artifacts/rs-title backing. Initial compile cost and subsequent
cached builds are kept in ignored logs. Shared .refs, RT64 shim and oracle
junctions are read-only; no ref fetch/rebuild, protected recursive deletion,
README edit, child agent or forced push is used. No shared RT64 rebuild is needed.
Final full gate, controls, images, timings and remaining blocker are recorded
below and in the issue4 closeout after validation.


## Final bounded milestone and remaining cache contract

The next real descriptor is1b/1d38:32 bytes atROM21518, runtime80020918,
IMEMdb0. It adjusts a structure pointer, loads OSTask.ucode, sets a DMA
source/length/destination, then tail-jumps into the resident SP-DMA helper.
A standalone minimum-size/RSP-opcode filter cannot recognize this scalar span.
The short-overlay filter now composes its exact bytes with the rooted resident
text and walks direct control flow from the actual placement. It requires
aligned bounded8..60-byte text, the complete resident080..fff context,
no direct exit or unsupported reachable word, and a reachable RSP operation.
Register jumps remain unknown and native guarded; this is candidate discovery,
not an indirect-control-flow closure certificate. Long-overlay filters and
startup uniqueness stay unchanged. Synthetic tests reject absent/bad helpers,
out-of-range targets, invalid slots, unsupported words and indirect-only spans.
The runtime fixture additionally executes a48-byte scalar trampoline through
its resident DMA helper and back, checking DMEM results and corruption refusal.

Final registry:51 ROM-derived RSP texts (27 before short-record traversal),
including two48-byte and two32-byte placements. The ordinary30s request
reaches the readable N64 logo,VI362/fault4/PC80095040,274 graphics,332 audio,
161 PI DMAs. VI-derived readback is400x442 (400x240 would crop the logo);
rs-vi.png and rs-logo-vi.png show the complete frame. The supplied early-input
experiment stopsVI221/fault4/PC80095040,90 graphics,183 audio,163 PI DMAs,
with the same logo. Exact attempted list: Start100,A110,Start115,A125,
Start150,A200,Start300,A400,Start600,A1000, each4 VIs. No title/menu appears;
there is no verified working gameplay press list.

A private diagnostic-only CPU unit identifies the remaining refusal:
CDE p0017da60,line_lost1,tag0022b001,other00138001,dirty0,unknown0000,stale0000
atVI216/fault4/PC80095040. The routine walks CDE over an object range; the
VI timing is sensitive to scheduling. The original task's prior receipt stopped nearVI350;
this worker's baseline stoppedVI487/fault3/8003dc58 in10.672s including readback.
After CPU provenance, the first new RSP refusal stopsVI352/fault0/PC00000000 in
8.078s. After short-overlay support, the logo run reaches a different cache
refusal, not a performance claim. Full measurements remain in per-run JSON.

The existing cache model marks RAM lost when dirty unknown slot bytes are
written back. The CDE target lost-line guard is therefore a provenance refusal,
not an unsupported opcode. A future change must establish recovery/retained
invalid-slot bytes and verify partial writes, aliases, writeback/DMA and cache
read behavior. This worker does not remove the guard or claim title/gameplay.

All six required local commands and final silent controls must pass on the
sealed candidate tree. Their full output, command lines, durations and hashes
are retained in gate.json and all-controls.json. MP2 and OoT-save use exactly
the task's lists. The final issue4 closeout records their measured VI/fault/PC
and framebuffer reviews; no copyrighted payloads are committed.
