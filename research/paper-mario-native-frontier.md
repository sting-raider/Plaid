# Paper Mario ROM-only native frontier

Latest scoped result: OPEN/11, 56,813 blocks and 162 loads (ADR-0214).
Native Paper Mario emission remains refused.

A low-word affine proof relates separately updated byte offsets and guarded
indices. Exact fixed-text JR RA sources are checked against callee no-write
witnesses when returning to a placed caller. This closes the five-entry site
8093c2e0 and adds six blocks, without new blocker sites. The first private probe
was OPEN/15 because the final table verifier could not read a fixed callee's
return; that failed proof also invalidated a dependent return certificate.
The corrected final probe is OPEN/11. See research/affine-table-index.md.

Captured pointer/flag values survive bounded guest calls only when each live
GPR has a rechecked no-write effect. Same-alternate source reads are admitted;
other alternate reads remain refused. This closes the five-entry dispatch at
80aac6f0, with four distinct targets and no new blocker sites. See
research/captured-callee-values.md for the authored reference contracts and
remaining proof limits.

Base: `8566a88dfe08d17d700a1800b18e5c7283f1229d`, 2026-10-18.
User input is only the local, ignored ROM `target/local-inputs/pm.z64`:
SHA-256 `9ec6d2a5c2fca81ab86312328779fd042b5f3b920bf65df9f6b87b376883cb5b`.
No symbols, load declarations, snapshots or per-game addresses are builder inputs.

## Copy-source refinement (ADR-0204, 2026-10-19)

Starting from production base `1a465af`, the fresh automatic pipeline now finds
34 files and 47,892 blocks. All three formerly missing code targets and their
four direct edges resolve. The scoped result improves from OPEN/142 to
OPEN/136: every remaining blocker is an indirect site. The original 125 JR-at
effect wrappers and ten JR-v0 dispatches remain; newly discovered partner code
adds one JR-v0 site at 0x802bd850 (ROM 0x317770). No native C or executable is
emitted, and no Paper Mario gameplay, graphics or audio success is claimed.

The new source candidates are two heap-loader files, ROM
[0x316c00,0x316d90) and [0x316d90,0x316f30), linked at 0x802ae000, and eleven
world-partner files linked at 0x802bd100. These are receipt observations only.
The heap wrappers pass constant source/end/destination arguments to a common
copy helper and immediately call the loaded destination. Its conditional-loop
layout supplies chunk and remainder copy-call shapes. The indexed partner
consumer supplies the same helper arguments from fields 0/4/8 of a row selected
with an index scaled by 64. Its leading null record is skipped; trailing fields,
including flags, remain opaque. Source order in the table need not be ROM order.

The general recognizers require aligned bounded sources, compatible adjacent
files and surviving argument provenance. Helper analysis is a 128-word linear
affine scan with delay-slot effects and call clobbers, not a control-flow proof.
The indexed catalog scans at most 256 records; this is a resource budget, not
a valid-index or completeness certificate. Existing raw text-bound heuristics
and exact native byte bindings remain mandatory. No assumption is retired.

`infer-call-loads` reconstructs the map's source images, checks ROM identity and
unchanged original declarations, and appends deterministic slot candidates.
It preserves newer fixed declarations and is idempotent even against the older
map after an append. The builder refines before another boot harvest; supplied
`--loads` files retain their existing behavior. Authored tests cover alternate
addresses/strides, clobbers, delay slots, unknown calls, branch aliases, scan
bounds, malformed runs and stale/foreign CLI sources. Removing the immediate
destination-call equality kills the corresponding negative regression.

The fresh pipeline takes 492.322 s including its release rebuild; this is not
a controlled speed comparison with the smaller earlier frontier. Iteration
also exposed a repeated failed overlay probe: a ROM's negative file-table
result is now retained between rounds. A controlled later discovery round
took 60.517 s with the repeated probe and 55.778 s with the known-negative
result. Both serialized maps have SHA-256
`9cd0b1bca2dc42e5594c8f6a1bc53335404571d427809c6796e677fc032faf5c`.
The successful-overlay path still probes each changed image; other discovery
errors still stop the builder. Retained orchestration tests cover these paths.

## Earlier section-overlay improvement (ADR-0202/0203)

The previous automatic pipeline was scoped OPEN/164 with 41,816 blocks and
19 loads. The new discovery finds two additional raw-section slot files and
identifies three SDK cache routines. The resulting frontier is OPEN/142 with
45,140 blocks and 21 loads: three missing code targets, four direct edges to
them and 135 indirect sites. Native emission is still refused. No Paper Mario
native gameplay, graphics or audio success is claimed.

The two files are the pause and file-menu overlays, both linked at 0x80242ba0.
Their source descriptors at ROM 0x52d5c and 0x52d8c supply source ranges
[0x135ee0,0x163400) and [0x163400,0x16c8e0), with text sizes 0xc3c0 and
0x6fe0. These are observations in this receipt, not production constants.
The caller passes each descriptor in a JAL delay slot to the same loader;
the loader reads the source, linked address and section-bound fields.

The general recognizer checks two adjacent 48-byte descriptors, independently
passed to a common section-reading loader, sharing a linked slot and adjacent
ROM source ranges. It verifies the text/data/BSS relationships, ROM extents,
alignment and RAM bounds. The callee witness is a bounded linear structural
scan with pointer-copy tracking and call clobbers, not a proof that every read
or load executes. Every candidate remains a content-guarded slot alternate.
Decoding re-reads the descriptor and rejects changed source, size, link or
text bounds. Only descriptor-owned text supplies instructions or slot targets.

The SDK bridge stores six address-independent size/SHA-256 identities for
osInvalDCache, osInvalICache and osWritebackDCache, covering locally verified
variants also found in SM64. It retains no complete SDK body or ROM code.
Hashes cover the complete executable body including terminal delay slots.
In particular, the invalidate-D extent is 0xb0, correcting the old symbol's
0xac truncation. Equivalent copies remain valid; conflicting names at one
entry remain ambiguous. Reviewed variants use equivalent line/range branches
and cache operations; the existing runtime ABI remains an explicit assumption.

## Replay cost

Composition used to reset the pinned ares oracle separately for each accepted
entry. It now requests all missing entries in one exact-entry replay, validates
the complete response, then commits it to the process-local memo. No disk cache
or runtime guest executor is introduced. Existing harvest range-cover behavior
remains separate: exact composition must capture each entry at its own first
fetch even when another entry's produced range already contains it.

A controlled local replay compared all three accepted Paper Mario entries:

| Measurement | Independent resets | Exact batch |
| --- | ---: | ---: |
| Wall time | 15.292 s | 7.557 s |
| Interpreter calls through final required fetch | 76,282,317 | 27,609,595 |

Each entry's bytes, destination, capture step, SHA-256, CPU-write ranges,
PI-DMA ranges, oracle revision, ROM identity and budget matched exactly.
The whole pipeline still has three bounded 100-million-call harvest attempts;
the measured reset improvement is not a claim that every analysis phase halves.
The harvest stop is in a guest idle loop, with normal reference synchronization;
stopping at that loop without interrupt/event evidence would be unsound.

## Remaining work

The formerly missing targets 0x802ae000, 0x802bd7dc and 0x802be070 now resolve
through the guarded raw source candidates described above.

Of the 136 indirect sites, 125 effect wrappers load function pointers from
a table whose targets use E000 virtual addresses. The table has 135 six-word
rows, with 127 executable candidates fitting one 4-KiB page each. Its loader
maps physical effect slots through the TLB before copying code. The present
KSEG slot model cannot safely represent this by merely accepting E000 as RAM.
Resolve the executable sources, virtual/physical binding and mapping lifetime,
then close the finite function-table dispatch with immutable provenance or
checked dispatch/write guards. The other eleven sites are indexed dispatches
whose table bounds and target identities still need proof.

The effects also call E020 shims: a JAL executing at E000 uses that PC region
and targets E020, whose wrappers dispatch through pointer words to resident
KSEG functions. These are valid original instruction words, not evidence for
rewriting JALs to KSEG. The shim sources/mappings and effect data dependencies
must join the executable model. Binding must distinguish virtual link, physical
frame and mapping generation; writes and remaps must revoke it, with active
native frames pinned. The existing KSEG masks in overlay binding/verifiers
cannot provide those guarantees by themselves.

The existing native data path already translates through the 32-entry TLB,
including page masks, valid/dirty checks and even/odd selection (`plaid_tlb`
and `plaid_addr` in plaid-lower). The missing composition is executable lookup:
`plaid_link`, overlay verification, write revocation and active-frame pins still
derive backing RAM from KSEG addresses. `osMapTLB` and `osUnmapTLBAll` currently
have no executable mapping-generation protocol. Retained operation-generation
research is not a runtime lifetime implementation.

The next synthetic contract should preserve virtual PCs and JAL return values
while binding candidate text to a separately translated physical frame and TLB
generation. Cover E000-to-E020 calls, two frames at one virtual link, same-value
TLB rewrites, inactive remap/reverification, active remap refusal, unmap/invalid
odd pages and text writes through aliases. A first implementation may refuse
unsupported mappings, but cannot silently mask E000 into a physical address.

## Validation and provenance

Retained synthetic tests cover section inference and malformed/unnamed records,
unrelated or clobbered descriptor pointers, exact text exclusion, declaration
tampering, SDK full-body mutations/truncation/delay slots and identity conflicts.
Deleting the descriptor/text equality check kills the declared-load regression.
The CLI contract exercises inference, consumption and rejected text/slot edits.
The pinned ares synthetic batch fixture mutates a later entry between first
fetches; exact-batch rows equal independent captures and legacy range-cover
mode still emits one row. Missing, duplicate, rejected, unrequested, malformed,
wrong-revision/range/budget and unkeyed payload responses fail closed.

The local gate includes format, locked Clippy/workspace tests, CLI, runtime
contracts and the pinned ares adapter test. Local receipts and ROM-derived
diagnostics remain ignored under `target/paper-mario/`.

The cache boundary fixture compares supported writeback/invalidate cases with
pinned ares at 1/16/32/8191/8192 bytes and checks signed/nonpositive and wrapped
no-op lengths. Reads after discarding a dirty full line remain a deliberate
fault-4 model boundary, with a progress marker proving the call returned before
the guarded read. This does not claim reconstruction of discarded hardware RAM.
Current solver controls remain CLOSED: BK 80,850 blocks, MM 215,126 and F-Zero X
27,759. These are fresh solves of retained maps, not new visible game runs.

Oracle: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` (ISC), built separately
with its existing notices. No additional reference code is copied or linked.
Paper Mario symbol/layout metadata at pmret/papermario commit
`1104f1f71b824042a5fa1f958f2d861b603320fd` oriented diagnosis only. That
repository has no root license; none of its source or game code is reused,
and its metadata is neither a production dependency nor a native-build input.

## ADR-0205: mapped source and tail-cell frontier

ROM-only refinement adds 128 unchanged TLB source alternatives: 127 sparse
effect records and one shared bridge. Discovery now has 55,666 blocks and 162
loads, scoped OPEN/18 (all remaining blockers are indexed JR dispatches). The
125 prior effect wrappers close through rechecked constant-cell proofs and
content/generation-bound native dispatch. No native artifact or accepted game
run is emitted. See native-tlb-executable-bindings.md for authored reference
contracts, runtime lifetime guards, measurements and limits. Ignored receipt:
`target/paper-mario/0205/frontier-result.json` and `solve.json`.

## ADR-0206: scheduled indexed dispatch

The fresh ROM-only pass is scoped OPEN/17, 56,495 blocks and 162 loads.
Recovering scheduled pointers before guards and exact constant SLLV shifts
closes the prior 95-entry site and exposes 829 more blocks. All remaining
blockers are indexed JR dispatches; loop-preheader values, current-index
relations and calls need further proof. Native emission remains refused.
Authored native/ares contracts and retained clobber/definition counterexamples
are documented in scheduled-table-dispatch.md. Receipts remain ignored under
`target/paper-mario/0206/`.

## ADR-0207: unchanged loop predicates

The corrected fresh ROM-only pass is scoped OPEN/16, 56,799 blocks and 162
loads. The 42-entry dispatch now closes with nine distinct targets, exposing
304 additional blocks; no new blocker sites appear. Exact complete backward
predicates can be inductive across a repeated block/start/anchor/end frame,
provided non-cycle paths ground the proof. A base-only shortcut was rejected
by a retained guard-count counterexample. Native preheader and captured-value
loops match pinned ares. Remaining sites still block native emission; see
loop-table-dispatch.md. Receipts are ignored under `target/paper-mario/0207/`.


## ADR-0208: retain internal-entry origins through discovery

The fresh ROM-only pass remains OPEN/16 with 56,799 blocks and 162 loads.
Five sites now retain 84 previously lost candidate edges, but the current
all-path proof still rejects their remaining predecessors. Discovery preserves
inferred case roots and candidate evidence through outer address-taken rounds;
ordinary external entry facts and current SDK callbacks remain barriers. A
tag-only forgery after merging an explicit entry was reproduced and retained
as a regression; independent entry evidence prevents that reclassification.
The authored native case-backedge loop matches pinned ares. Calls and some
other loop paths still need proof; finite candidates are not closure. See
derived-entry-discovery.md and ignored `target/paper-mario/0208/` receipts.


## ADR-0209: longer bounded predecessor paths

The fresh ROM-only pass is OPEN/15 with 56,799 blocks and 162 loads. The
call-free 56-entry dispatch at 800e9de4 had reached the previous 16-frame proof
limit; the general 32-frame limit permits a fresh certificate and complete
re-verification. No blocker sites are added. Native long-chain state matches
pinned ares, while clobber, unknown-entry and resource-limit negatives remain
rejected. No native Paper Mario artifact or run is accepted. See
table-path-budget.md and ignored target/paper-mario/0209 receipts.


## ADR-0210: no-write guest-callee summaries

The fresh ROM-only pass is OPEN/14, with the same 56,799 blocks and 162 loads.
A pending table base can now cross a direct call whose bounded, source-rechecked
callee traversal proves that no reachable instruction writes the register.
This closes the 24-entry dispatch at 80132e00, with four distinct targets and
no new blocker sites. Unknown effects and save/restore of the required register
still reject; no guest ABI exception is introduced. Native leaf/nested call
loops, RAM stores and stack effects match pinned ares. No native Paper Mario
artifact or run is accepted. See callee-register-preservation.md and ignored
target/paper-mario/0210 receipts.


## ADR-0211: terminate checked BREAK paths in callee proofs

The fresh ROM-only pass is OPEN/13 with unchanged block/load counts. The
five-entry dispatch at 80131e30 now closes; its callee chain has guarded BREAK
paths that cannot return normally. The proof hashes each BREAK word and ends
that path under the existing guarded-scope native fault-9 contract. Ordinary
scope still rejects BREAK; delay-slot and BREAK-only callees remain refused.
No new assumption or guest ABI rule is introduced. Native normal paths match
pinned ares; the taken BREAK fixture aborts at the exact PC. No native Paper
Mario artifact or run is accepted. See checked-break-callee-paths.md and
ignored target/paper-mario/0211 receipts.


## ADR-0212: branch-flag values and infeasible predecessor paths

The fresh discovery/solve pass remains OPEN/13 with 56,807 blocks and 162
loads, exposing eight more blocks without changing the blocker sites. A path
cannot require an unchanged flag register to be both zero and nonzero. Every
non-SLTIU GPR write now clears old flag constraints before pointer/scale
transfers return early. Retained tests catch an unsafe naive pruning rule and
an existing stale-guard counterexample even without a cycle. Native valid and
invalid-index paths match pinned ares. Candidate target recovery is still not
closure: additional callee/entry effects remain unresolved. No native Paper
Mario artifact or run is accepted. See branch-flag-feasibility.md and ignored
target/paper-mario/0212 receipts.


## ADR-0215: traversal-local mapped callee effects

Fresh canonical-main and candidate discovery/solve use only the ROM-derived
loads/runtime declarations: scoped OPEN/11 -> OPEN/9, 56,813 -> 56,851 blocks,
162 loads unchanged. Two indexed dispatches close; no new blocker site appears.
Raw linked callees can now bind exact unique declared text and follow rechecked
constant-cell tails with all-target no-write effects. Source cells, declaration
identity and actual return witnesses remain in the table proof. Binding authority
is local to each traversed path and restored after calls: the inherited red test
proved a real leak into later placed calls/fallthrough and remains a negative.

Discovery must carry declared provenance before analysis, including every fresh
outer round; attaching it only to the final map loses the proof opportunity.
Other predecessor paths and save/restore/stack-cell relations remain unresolved.
No native Paper Mario artifact, VI/fault/PCM result or accepted run is produced.
See mapped-callee-effects.md and ignored target/paper-mario/0215-recovery/ for
baseline/candidate timings, map/solver controls, mutation and local gate receipts.

## ADR-0216: reuse immutable callee effect queries

The fresh ROM-only pass improves scoped OPEN/9 to OPEN/7, retaining 56,851
blocks and 162 loads. Two dispatches close, with three distinct targets each;
no new blockers appear. The final-round refusal classification is scripted in
ignored `target/paper-mario/0216/classify.py` and `classification.json` from
`traced/discover.log` plus the exact map and solver result:

| Sites (diagnostic only) | Missing proof before ADR-0216 | Result |
| --- | --- | --- |
| `80a0893c`, `80a089b8`, `80a08aa8` | Base initialization across independent address-taken case entries | Still refused: unknown entry state must not be relabeled internal. |
| `80ac21d4`, `80ae427c` | Repeated mapped-callee effect traversals exhaust the shared read budget | Closed by walk-local effect reuse; five/six entries. |
| `8003c488`, `8082cf20` | Callee register preservation, including save/restore memory effects | Still refused. |
| `80b2c178`, `80b2c344` | Stack-cell pointer/index provenance and intervening writes | Still refused. |

The three-site group was examined first; its independent origins prevent a
sound relaxation. The next largest actionable group closes with one general
rule: reuse successful source-bound effects for the same target/GPR within an
immutable map/image/caller-slot walk. Misses retain the existing bounded source
traversal; hits keep all source words/bindings and exact return witnesses in
the table certificate. Verification always starts a fresh cache. No ABI rule,
runtime fallback, budget increase or game-specific production fact is added.

The authored budget positive is red before implementation. Four mutants are
killed, including a target-key counterexample whose two entries share the
same return. Repeated-call native CPU/PC/FPU/RAM state matches pinned ares.
See research/table-effect-reuse.md and ignored target/paper-mario/0216 for
operational before/after timings, controls and the exact-tree gate receipt.
No Paper Mario native artifact or accepted VI/fault/PCM run is emitted.


## ADR-0217: frame-local pointer reloads (partial)

The fresh warm ROM-only map is identical to baseline: scoped OPEN/7, 56,851
blocks and 162 loads. Independent address-taken entry/base initialization
remains a barrier. Callee save/restore still needs width-aware and nested-memory
proofs from actual instructions. Exact frame-local SW/LW pointer forwarding now
proves authored synthetic dispatches only with unchanged SP, all-path enclosing
allocation and no intervening potentially aliasing write or call. Even different
virtual stack offsets are refused without physical non-aliasing evidence.
The two PM stack sites still lack the complete index/alias relation; no site is
closed and no new blocker appears. Four native index/SP-base cases match pinned ares;
five semantic mutants are caught. No PM artifact or VI/fault/PCM run is accepted.
See research/stack-table-pointer.md and ignored target/paper-mario/0217 receipts.

## Residual-dispatch run (ADR-0218)

`native.py --residual-dispatch --rt64 --require-audio` on the selected ROM:
solve closes with 0 blockers and 7 residual sites; the artifact builds and runs
(VI 1, gfx tasks 1, audio tasks 0, PI DMAs 12, framebuffer 00000280) then faults
3 at the boot-stub dispatch site: its target is not a lowered entry. The stub
reads a cartridge word, adds it to a constant and jumps; the target region is
not covered by any lowered entry (entries end before it). Hypothesis: main
program code is produced at boot (relocation/decompression) and must be
captured by the boot-generated-text path. The fault is the correct fail-closed
result. PCM peak: n/a (no audio task). Receipts: target/paper-mario/0218.


## ADR-0220 investigation claim (in progress)

Hypothesis: an indirect boot transfer reaches completed executable RAM outside
the inferred image ranges, so ADR-0190 misses it because no known missing target
names it. Test with the pinned ares reset replay, stopping at the first uncovered
KSEG0 RAM fetch after boot entry. Preserve completed-producer and instruction-cache
checks, then replay and content-guard any new declaration through `ares_boot`.
No per-ROM production facts or native guest executor will be added.

Predecessor review reproduced a fail-open residual gate: a known unmapped candidate
was suppressed along with its unproven site. The commit "Keep known missing targets blocking residual validation" retains this target
blocker in every scope (three focused tests pass). Residual manifests must also be
written when the ordinary scope happens to close. Cartridge-write latch/timing
effects and untested absent-Pak/full-address EPi paths remain under review.

## ADR-0220 result (2026-10-21)

`native.py --residual-dispatch --rt64 --require-audio` on the same ROM, base
main `8095e9a9`. Each analysis-time boot harvest round extends discovery
(42,601 -> 53,094 -> 56,791 -> 56,825 -> 58,624 -> 58,642 blocks) and the
address-taken solve goes from 14 to 11, 10 and 8 blockers. The residual solve
closes with 0 blockers and 8 residual sites. The whole pipeline, including an
incremental release build of 73 s, took 10.5 minutes.

The artifact passes the former boot-stub fault (PI DMAs 12 -> 154, 11 threads
created) and faults 3 at `802001f0` (VI 2 in the window build, 1 gfx task,
0 audio tasks, no PCM). That `jalr` is in 0x190 bytes the game DMAs from ROM
`0x316a70` to `80200080`. The routine sums ROM `0x3169f0..0x316a70` as halfwords,
cancelling relocated `lui`/`addiu`/`jal` fields, and combines the sum with the
cartridge word at `0x504` into the call target. Native execution computes the
same sum as an offline replay of the routine (`0xddd20`), giving `80026ddc`: a
function inside the main image (it calls `8002973c` with ROM-range/RAM-address
pairs) that no instruction names directly, so discovery has no block there and
the address-taken set (2,241 entries) omits it. The fault is the correct
fail-closed result. Next blocker: analysis-time targets of unproven indirect
calls are not discovery roots. Receipts: ignored target/paper-mario/0222.

## ADR-0222 result (2026-10-21)

With observed call targets as discovery roots, the six harvest rounds record
19 call targets, among them the integrity check's `802001f0 -> 80026ddc` and
the boot stub's `80200064 -> 8004ab00`. Discovery grows to 58,735 blocks; the
residual solve still closes with 0 blockers and 8 residual sites. The run
passes the integrity check (PI DMAs 154 -> 235, VI 2, 1 gfx task, 0 audio
tasks) and faults 3 at residual site `8004e544`, a five-case `jr v0` switch
(`sltiu v1, 5`, table base from `lui/addiu s4`). Its map candidates are the five
case labels, all block starts, and the fault value `8004e5a8` is one of them;
residual lowering dispatches only over function entries and ignores them.
Pipeline time 13.2 minutes. Receipts: ignored target/paper-mario/0222.

## ADR-0223 and ADR-0224 results (2026-10-21)

With residual sites dispatching over their own candidates (ADR-0223), the
five-case switch at `8004e544` runs natively and the run continues to 260 PI
DMAs, then stops with "runtime write refused": `osEPiStartDma` targets
`e0200000`, a TLB-mapped buffer (ROM `0x325ad0`, 0x940 bytes). With the host DMA
writing the TLB-translated physical page (ADR-0224) the run reaches VI 3 with
one gfx task, submits its first audio task (261 PI DMAs) and stops cleanly with
"unknown or ambiguous ROM-derived RSP microcode": the audio task's microcode is
not among the 16 ROM-derived RSP texts. CPU fault 0. Receipts: ignored
target/paper-mario/0222.


## ADR-0225 integration claim (2026-10-21)

Base main: `0d003fc0d1d07f4651ac6568f839c941e819e920`; candidate
`1107ed7d`. Hypothesis: ROM-backed PI DMA ranges outside the CPU images can
supply missing RSP task boots without granting CPU discovery or closure.
Review, synthetic execution, source-removal mutation and the full local gate
are required before exact-head CAS integration.


## ADR-0225 result and validation receipt (2026-10-21)

The earlier visible residual-validation run with candidate `1107ed7d` reached
VI 4, two compiled RSP audio tasks and 261 PI DMAs, then fault 3 at
`800602d8 -> 8002605c`. The audio task's boot at `800d9780` is 0x100 bytes
copied by PI DMA from ROM `0xb70`; its candidate is
`rom_41a5f4f68d34a88f_0`. No visible gameplay or non-silent PCM is established
by this observation, and this integration does not rerun the visible game.
The next call target follows a `j .` wait loop and fails the existing
function-start layout filter; ADR-0226 remains separate work.

Review corrected DMA roots that could otherwise come from the source's own
data, tightened source bounds to nonempty aligned 8 MiB RDRAM ranges, and
corrected the synthetic fixture: it originally used a source inside the CPU
image and a 64-byte boot below the retained 128-byte plausibility minimum.
The contract now uses an externally named 128-byte source outside the image,
executes its compiled boot and audio program, and checks exact output words.
Without the source it refuses the task with no output writes. An unnamed
source containing an internal boot pointer is ignored; empty, overflowing
RDRAM and out-of-ROM ranges are refused.

`python scripts/test_ares_boot.py` passes the pinned ares synthetic replay and
harvest contracts. The focused `runtime/test_rsp_rom.py` run passes in 51.2 s.
Fresh extraction from retained CPU maps and loads reproduces identical ordered
(text SHA-256, IMEM placement) lists: BK 41 (14.4 s), F-Zero X 50 (1.2 s),
MM 34 (6.3 s). Inputs and generated assets stay in ignored local directories.

Build recovery: cached plaid-core objects initially failed MSVC linking;
`cargo clean -p plaid-core` followed by the same locked build succeeded in
145 s. No source or build-setting workaround was needed. This is a cold-cache
recovery cost, not a production performance change. Full exact-tree validation
uses `target/paper-mario/0222/gate.py` with GATE_TREE pointing to this worktree
and GATE_OUT at `target/paper-mario/0222/gate-0225`; per-step timing and logs
are retained there. No runtime guest interpreter/JIT or closure relaxation is
introduced.


Mutation check: after successful source parsing, temporarily clearing the
source list and rebuilding kills the focused contract at its expected DMA
candidate assertion (`AssertionError: []`), in 35.3 s including rebuild.
The original source bytes were restored before the final full gate.
