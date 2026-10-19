# Paper Mario ROM-only native frontier

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
