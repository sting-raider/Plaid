# Heap overlay binding investigation

Milestone 5, starting from `64fe72b`. The retained Majora's Mask build stops
at a call into a heap-loaded executable overlay. Reproduce it visibly before
changing production code; keep ROM, RAM captures and generated output ignored.

Implementation claim (2026-10-17): isolate the rejected heap binding using
the retained executable's dump interface, then change only the general
verification policy demonstrated by a synthetic regression. Candidate paths:
`crates/plaid-lower`, its native synthetic contracts, and milestone documentation.
Local and fetched `origin/main` both start at
`64fe72b71cb201035f0a365558cbb8f0364675e3`; no push is authorized.

The first fresh visible 75-second run with the supplied FlashRAM path ended at
the time limit (4,480 VIs, 3,041 graphics tasks, fault 0), rather than reproducing
the retained fault. Its capture is not evidence of reaching the rejected call.
A separate erased-FlashRAM run is being checked before production edits.

Hypotheses to distinguish:

- executable text or a relocation differs from the declared source;
- the target is absent from the discovered/lowered function set;
- multiple overlay/base pairs match;
- initialized mutable data or BSS causes the first-entry verifier to reject
  otherwise correct executable text;
- an existing binding or protected range prevents a valid load lifetime.

Any correction must preserve executable-byte identity, unknown/ambiguous-target
faults, native write revocation, and the declared closure scope. It must be
general and backed by a synthetic regression plus relevant pinned-reference
checks. A title screen or a longer finite run is not whole-ROM completion.

## Root cause and candidate (2026-10-17)

The retained 8 MiB captures do cover the target (the earlier dump requested
2,097,152 **words**, not bytes). An ignored instrumented native build reproduced
fault 3 at PC `800b6928`, target `805665e0`, VI 3190 (retained run: VI 3188).
At that call `prot[target >> 2] == 0` and the unchanged generated verifier 11
returns 1. Overlay 11 is linked at `80866800`: ROM source `00b672a0`, Yaz0,
file 5056 bytes, text 3536, BSS 16. Its first lowered function is `80866800`.
The scan of all 612 overlays/670 candidate probes finds exactly one match.
It is neither a missing target, ambiguous identity, nor initialized data/BSS.

The captured binding table instead has `ovl_ok[11] == 1`, delta corresponding
to the old heap base `8053b600`. Both old and new copies verify, including data
and BSS. No write has invalidated the old text, so its binding survives heap
reuse/lifetime changes. `plaid_link` explicitly rejects `hit && ovl_ok[hk]`:
it cannot select a second copy even when the first has no native frames.
Ignored evidence: `target/mm-heap/diag.log`, `diag-state.bin`, `scan-old.exe`,
`scan-verifiers.exe`. No captured bytes are tracked.

Candidate: preserve one selected binding per overlay, but permit a unique,
fully verified copy to replace an inactive binding. Check destination protection
before releasing the old text protection. Native overlay function wrappers
balance an active-frame count on every return/fault/tail path; suspended frames
also retain their pin. A different base while pinned still faults 3. Existing
full-file/BSS verification, text-write revocation, same-target ambiguity checks,
return guards and closure scope are unchanged. No loader-lifetime proof is
claimed: assumption 12 remains assumed, and native_complete remains false.

Pinned N64ModernRuntime `cdf5abbd5026fef5c364c676e4667c45e42b6863`,
`librecomp/src/overlays.cpp` explicitly unloads and replaces loaded function
mappings. Plaid lacks that game's loader boundary and instead uses verified
identity plus native-frame pins. This is a design comparison only; no source
code was copied. Behavioral verification uses original synthetic inputs and
the pinned ares CPU oracle, not game-specific symbols or patches.

## Regression and local gate

`runtime/test_heap_overlays.py` constructs original synthetic relocated images
and compares B1 -> B2 -> B1 execution with pinned ares, including all GPRs,
PC, HI/LO, FPR/FCSR and the observed RAM window. It keeps mutable data unchanged
so that each new binding must still pass the existing full-file/BSS check.
It also checks that a nested call to a second copy fails while the first has a
native frame, tampered text fails, protected destination bytes prevent a move
without releasing old protection, all pins unwind on fault, and a runtime write
revokes the new binding. It is part of `runtime/test_runtime.py`.

The retained spike096 `overlay`, `ovl_tamper`, `ovl_self`, `ovl_callback` contracts
pass (normal execution matches pinned ares; faults 3, 2, 8 respectively).
The runtime suite also retains shared-slot ambiguity rejection. Mutation review:
restoring `hit && !ovl_ok[hk]` in the generated synthetic C fails the positive
move fixture; the unmodified candidate passes.

Local production gate on this candidate (seconds, logs ignored under
`target/mm-heap/gate-*.log`):

| Command | Result | Seconds |
| --- | --- | ---: |
| `cargo fmt --all -- --check` | pass | 1.646 |
| `cargo clippy --locked --workspace --all-targets -- -D warnings` | pass | 1.735 |
| `cargo test --locked --workspace` | 710 passed, 0 failed, 1 ignored, 80 suites | 40.815 |
| `python scripts/test_cli.py` | pass | 7.838 |
| `python runtime/test_runtime.py` | pass, including the new heap contract | 83.310 |

Review: one selected binding per overlay is retained, and an active native
frame (including one suspended in a callback or thread yield) prevents moving
its delta. Protection checks precede all binding/protection mutations. Failure
paths balance pins through the wrapper. No verifier bytes, target sets, solver
scope, runtime guest execution path or third-party code were added or relaxed.
The generated native state gains 4096 bytes for the counters.

## Lowering iteration bottleneck

A bounded GDB stack sample, resolved with the compiler's local PDB, found the
slow MM lower-map inside `returns::function_bodies` collecting/sorting repeated
callee identities. Address-taken call sites append the same functions to the
callee vector many times; emission already keeps only the first per PC. The
candidate now filters exact duplicate CodeAddresses before body analysis,
preserving first occurrence and all emitted function/dispatch order.

Before: one run hit the 180-second tooling limit; a second was stopped after
approximately 449 seconds, still in body analysis, with over 2 GiB resident.
After: the same MM map lowers in 14.215 seconds (more than 31x faster than that
unfinished baseline). Four retained overlay contracts emit byte-identical C
before/after this deduplication (`dedup-output-check.json` contains hashes under
the ignored evidence directory). All five gates were rerun after the change;
the table above records that final gate. This optimization changes no analysis
result or generated instruction. The slow run was cancelled before emission,
so full-MM before/after C equivalence was not measured; it is covered by the
same tests and the exact-tree native validation below.

## Exact-tree native acceptance

Rebuilt from the retained MM map with production `lower-map --parts 16`,
rechecked scoped closure, compiled all guest parts and the runtime, and linked
its existing lowered microcode with RT64 (the same HLE graphics path as the
repro). `target/mm-heap/rebuild.py` follows `scripts/native.py`'s build/cache
rules without repeating established discovery or snapshot collection.
Lowering took 14.215 s; lowering plus all part compilation took 254.885 s;
the complete window build and link took 498.589 s. The running game exposed
a normal `RT64` window (PID 41624), and exited on its own time limit.

Fresh `fixed-erased.fla` contains 131072 bytes of FF before launch. Visible
`mm-rt64.exe --rom target/local-inputs/mm.z64 --flash
 target/mm-heap/fixed-erased.fla --stop-at none --seconds 90` stops at
**time limit, VI 5358, graphics 2401, audio 4990, fault 0**. The game has an
explicit 90-second runtime limit and 110-second external kill timeout.
Ignored receipts: `rebuild-fast.log`, `fixed-run.log`, `fixed-state.json`.
No input script or per-game production workaround was used. No background
native game/debugger/compiler process is retained after completion.

Assumption 12 is advanced but not retired: the native-frame pin proves the
selected binding cannot move under a native frame; the game's own loader's
complete bases, deallocation chronology and future execution remain unproved.
Full-file/BSS checks still apply whenever selecting a different copy, including
a previously used one. Mutated data can therefore conservatively prevent a
later selection; this policy was not relaxed by the fix.
