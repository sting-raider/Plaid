# Bounded native COP0 state (ADR-0235)

Claim: COP0 staging moves and deterministic indexed TLB operations can use the
existing guarded native TLB mutation/binding path, with explicit refusal of
unknown CP0 state and unmodeled timer, Random, ASID and exception effects.
Prepared base: 1cf11337453e490dce6c81ade318566de4858a49 (rebased from 76692ed6).

Pinned ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 ISC source inspected:
interpreter-scc.cpp (moves, register masks, TLBWI/TLBR/TLBP), tlb.cpp
(synchronization), interpreter-fpu.cpp (FR change preserves backing registers).
No upstream implementation is copied or linked into native code.

This is a partial implementation. Mapping-backed instruction discovery,
analysis-only boot_execution expansion, TLBWR/Random, Count/Compare,
Cause/EPC/ERET and general interrupt/exception delivery remain open.

Review hardening: SDK boundaries and context restores invalidate CP0 staging
knowledge, because existing runtime contracts do not certify those latch side
effects. Guest reads must not reuse a latch value from before an HLE call.
Status remains governed by its separate complete-state contract.

## Continuation and integration receipt (2026-10-22)

The stopped candidate was 3b73a1c5 on 1cdb8253. Its retained gate log failed
at the generated runtime-call string assertion in plaid-lower/tests/lower.rs.
The committed candidate already contains the required cp0_known invalidation
in that assertion; a fresh focused run passes (1 passed, 18.94 s build).
Reconciled onto exact main e9d1ccf08e3808ac62b38805e1ee2813ceeb2128,
keeping main's README regression warnings, dispatch description and name fix.
Only this milestone's game rows, coverage explanation and ADR row are reapplied.

ISA coverage: **196/209 (93.8%) -> 203/209 (97.1%)**. The seven additions are
MFC0, DMFC0, MTC0, DMTC0, TLBWI, TLBR and TLBP. No assumption is retired.
The exact pinned ares checkout is clean at
9408cb43d4948fc3ea6e152a307a34348df3fe04; the runtime gate reruns the complete
native/reference state, RAM and all-32-entry comparison. Changing the native
Index mask from six bits to five causes the TLB-generation assertion to fail
(exit 3221226505). This mutation affects only an ignored generated copy;
production sources remain unchanged. The existing remap/clear, tampered-text,
active-frame, Status/FR, event and runtime-boundary contracts stay mandatory.
The historical DECISIONS git blob is an exact byte prefix of the candidate;
its CRLF working-tree representation and non-UTF-8 byte are preserved.

Fresh normal commands, both with --rt64 --seconds 60 and user-local ROMs:

| ROM | ADR-0233 ordinary / residual blockers | ADR-0235 ordinary / residual blockers | Pipeline seconds | Result |
| --- | ---: | ---: | ---: | --- |
| GoldenEye 007 | 7 / 7 | 1 / 1 | 6.812 | 348 blocks; unresolved indirect target 70000510 has no mapped instruction source |
| Mario Kart 64 | 30 / 27 | 13 / 10 | 215.547 | 40,610 blocks; ERET contributes two blockers, four unmapped targets and four unresolved direct edges |

Both commands return 1 at analysis refusal, before lowering/build/validation.
No native game window exists for either; VI, rendered frames and audio are
unmeasured. The 60-second setting is a requested native duration, not a claim
that either game ran. No mapped instruction provenance or boot evaluator
extension is claimed. GoldenEye's core boot evaluator still stops at MTC0;
the analysis-only ares replay can execute it but cannot yet export the mapped
code with the required binding/lifetime evidence. MK64's harvest supplies no
new accepted executable image. No game constants were added to production.
Pipeline timings are operational observations with concurrent local work,
not controlled speed comparisons (ADR-0233 MK64 was 156 s).

BK and F-Zero X discovery regenerate byte-identically against the retained
ADR-0234 baselines (analysis code is unchanged between that base and main):

| ROM | Blocks | Prior prepared seconds | Continuation seconds | Complete-map SHA-256 |
| --- | ---: | ---: | ---: | --- |
| BK | 81,465 | 134.797 | 90.234 | b41011d9f0a7d626a49ca6cebfe0b042dd27c606cf69cec7efb427745b2b9467 |
| F-Zero X | 28,119 | 8.266 | 25.157 | 92ef76696f942aa543b11f43bd073fb25137937cb7ab93039135e221d850c05f |

These noisy wall times do not establish a speed change. The existing four-job
CPU compiler limit avoids the previous worker's memory-pressure problem;
there is no controlled cold-build before/after result. No unrelated native
regression is repaired. The retained candidate MM RT64 executable was rerun
visibly: its complete reported state is identical to the prepared candidate
and legacy-Status controls, fault 2 at 80089668, VI 0, four PI DMAs, zero
GFX/audio tasks. Source verification is retained under
target/native/cop0-mm-sourcecheck/receipt.json. BK native gameplay was not
rerun in this continuation; discovery and the shared runtime verifiers are
the regression evidence, not a claim of a new BK playthrough.

Ignored continuation evidence: target/continuation-0235/{games.json,
blockers.json,ge.log,mk64.log,ge-solve.json,mk64-solve.json,discovery.json,
mm-visible.log,mutation/receipt.json}. The canonical five-step local gate is
python X:/Plaid/target/paper-mario/0222/gate.py with GATE_TREE pointing to this
worktree and GATE_OUT=X:/Plaid/target/cop0-0235-gate. gate.json and the five
logs retain return codes and timings; all five must be zero before CAS.
The Rust suite reports **905 passed, one ignored**; tools/progress.py --check
passes. Final exact-tree validation is rerun after this receipt is written.

Remaining: authenticated mapped instruction discovery/source/lifetime export;
known initial CP0 state for the core boot evaluator; Random/TLBWR,
Count/Compare, Cause/EPC/ERET, CACHE and interrupt/exception delivery; Status
writes in SDK threads with scheduler/IE effects. Rogue Squadron was not rerun;
its broader pointer/overlay/instruction gaps remain open. This landing is a
verified partial, never a native-complete or new-game acceptance.

The first reconciled-tree gate passes all five steps: fmt 1.1 s, Clippy 5.8 s,
workspace tests 26.2 s, CLI 4.3 s, runtime 413.1 s (450.5 s summed). Its logs
are preserved as target/continuation-0235/initial-*. Final exact-tree results
replace the canonical cop0-0235-gate logs. The stopped pre-continuation gate
had workspace rc 101; its assertion update is now confirmed by the full suite.

MM discovery also regenerates byte-identically: 214,963 blocks, 217.782 s
(prepared measurement 310.265 s), SHA-256
a52eb0e427e338a178a99b82d1fd8e996ac203c94f48905317b1b734cefc0603.
As with the other timings, concurrent work prevents a causal speedup claim.
