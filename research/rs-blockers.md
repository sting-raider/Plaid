# Rogue Squadron: infeasible paths and guarded slot call identities

Worker `rs-blockers-2c1a5b33`; base main
`7347a9ec1bfc5af811c43163bed194085831d8ed`; ADR-0270.
The requested branch name was occupied. The seven-file uncommitted candidate
in worktree `t3-d5756315`, last modified about seven hours earlier, was
recovered without changing that worktree. Its issue #4 claim was inspected
and a recovery claim posted. No child agents were used. README is untouched.

## Fresh reproduction and all thirteen blockers

Local user-supplied Star Wars - Rogue Squadron (USA) (Rev 1), canonical SHA-256
`4813551d01d3a3474df3a51f84c31059cd2a9d1eeae7885dda51a88ee6b9f88d`.
No ROM bytes, game assets, saves, maps or screenshots are committed.

```powershell
$env:SDL_AUDIODRIVER = 'dummy'
python scripts/native.py <rom> --rt64 --seconds 30
```

The fresh baseline reproduces 50,862 blocks, 28 address-taken blockers,
13 residual blockers and 15 residual sites. No executable is emitted.

| Cause | Sites | Blocker kinds | Count |
| --- | --- | --- | --- |
| Impossible BLTZAL-zero taken path decodes data as JAL | `80091a48`, target `8334b334` | `unmapped_target`, `unresolved_direct_target`, `unsupported_delay_slot` | 3 |
| Fallback ROM window contains data at a linked slot call offset | `80096d50` | `exception_or_unsupported_instruction`, `unsupported_scope_effect` | 2 |
| Data at the same offset in two alternate files | `80806d50`, `80876d50` | invalid/unsupported pair at each site | 4 |
| Float-valued data reached in the third alternate | `808b1148`, `808b12b8` | invalid/unsupported pair at each site | 4 |

## General rules and closed-world limits

`branch_never_taken` recognizes BLTZ/L/AL/ALL with zero source, BGTZ/L zero,
and BNE/L with identical registers. Discovery retains only executable
control-flow paths. Link-register writes still happen before ordinary
delay slots; untaken likely slots are absent from that block's executable
words. A separately rooted slot is still checked normally. Unknown and
known-taken branches retain their required targets. Lowering shares the
same predicate and never emits a reference to an impossible branch target.

A direct call into a declared linked slot selects a placed identity through
the existing runtime binding. Its overlapping fallback ROM window is not
another alternate. Discovery considers every supplied text alternate, but
does not seed one whose straight-line prefix contains a reserved encoding
or leaves supplied instructions before a transfer. This bounded 64-word
admission heuristic is neither a section boundary nor proof of unreachability.
Unsupported transfers/effects still enter ordinary fail-closed analysis.
Explicit roots, branch targets and non-call discovery are not filtered.

The solver records every call missing any alternate entry as
`unresolved_slot_call_identity` in strict scope. In residual scope the call
site is explicitly residual, and its existing native dispatcher contains
only lowered alternatives. Binding the excluded alternate faults 3; it
never executes those bytes through an interpreter/JIT. With no lowered
alternate, the direct target remains unresolved even in residual scope.
The architectural edge and full content-bound slot declarations are retained.

Independent testing found and fixed a recovered-candidate bug: asking
`source(images, target)` skipped the obligation when the linked address lay
in a base-image hole. Matching the target image/generation's slot metadata
instead covers both holes and overlapping fallback windows. A generated C
indentation warning found by the new verifier was also fixed.

## Measurements and native result

Matched-input discovery plus residual solve, same load declarations and
identification, old main binary followed by candidate binary:

| Measurement | Before | After |
| --- | --- | --- |
| Blocks | 50,862 | 47,866 |
| Indirect sites | 2,861 | 2,699 |
| Map unresolved facts (not solver blockers) | 534 | 511 |
| Address-taken blockers | 28 | 19 |
| Residual blockers / residual sites | 13 / 15 | 0 / 19 |
| Discovery seconds | 18.364 | 15.847 |
| Discovery + residual solve seconds | 19.575 | 16.971 |
| Executable emitted | no | yes, `native_complete: false` |

This is one ordered timing sample under concurrent compilation, not a
controlled universal speedup claim. Speculative code traversal is reduced.

The emitted visible silent run is requested for 30 seconds but terminates
after about 0.72 seconds with VI 0, fault 12, fault PC `8000041c`, RA
`80001eb0`, framebuffer 0, graphics/audio/PI counts all zero. There is no
rendered title/menu and no opportunity for menu presses. Instruction
`0xbd0d0000` is CACHE Create Dirty Exclusive. The pinned ares implementation
retains cache-line bytes, can write back a dirty victim, and retags the
line; Plaid's current cache subset refuses it. Supporting it needs cache
state verification, not an invented no-op or RAM fill. Rogue Squadron
gameplay therefore remains OPEN.

## Verification and integration receipt

Deterministic Rust tests cover all eight untaken branch encodings, ordinary
and likely slot coverage, missing targets for unknown/taken branches,
ordinary invalid-slot refusal and separately entered annulled slots.
The native verifier compares complete GPR/FPR/PC/HI/LO/FCSR and the harness
RAM slice against pinned ares, including RA observed by delay-slot stores.
Deleting the first link write makes that comparison fail.

The slot CLI/native contracts check raw, paired-stream and catalog identity
switching against ares, invalid fallback-window bytes overlapping the linked
slot, tampered/ambiguous text, BSS, partial identity strict
refusal/residual emission, omitted identity runtime fault 3 and no decoded
identity remaining OPEN. Mutating the residual-scope guard to accept every
guarded scope fails the strict-scope assertion (27.702 seconds, restored).
The full runtime suite includes both new contracts.
Its retained ERET fixture now uses distinct registers for its static
alternate path: BNE-zero-zero correctly no longer supplies a target root.
The initialized register keeps that path untaken in both native and ares.

Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`,
`ares/n64/cpu/interpreter-ipu.cpp` branch and CACHE handlers. ISC reference
source was read only; no upstream code was copied or linked into native mode.
The synthetic oracle is a private copy of the current pinned build with
checked revision/driver hash. Only this worktree's oracle junction was
unlinked nonrecursively; its shared target was untouched. Shared `.refs`
were not fetched and the shared RT64 shim was not rebuilt.

Local receipts live under ignored `target/receipts/rs-blockers/`, including
before/after maps and solves, timing JSON, mutation logs, native stdout and
scene captures. Controls use retained load declarations rechecked against
ROM content and regenerate CPU code with the final compiler; source/compiler/
flag hashes gate object reuse. Redundant ROM-alone control inference was
stopped before a game launched. The native windows stay visible and all
native processes use `SDL_AUDIODRIVER=dummy`.

The exact-tree integration gate is:

```text
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

Required visible silent controls are PM, BK, MM, SF64 and OoT for 30 seconds,
plus MP2 with Start at VI 600/1250 and A at VI 1360/1440/1520/1600/1680/1760,
each for four retraces. The 60-second OoT saved-SRAM reproduction uses Start
at VI 1200 and A at VI 1400/1550/1700/1850, each for four retraces. Exact
observed counters, scene evidence, per-command gate timings and the validated
base/tree/landed commit are recorded in the canonical issue #4 closeout and
local `*-run.json`, `final-gate.json` and `integration.json` receipts.
