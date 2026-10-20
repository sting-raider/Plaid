# Frame-local table-pointer reloads (ADR-0217, partial)

Base: `7f09341eae3a3cf41e50192988430ae66b4e31e2`.
Branch: `experiment/pm-closure-0217`; no canonical write authorized.

Hypothesis: an exact SW/LW stack-cell pair may carry a captured table pointer
when all predecessor paths prove an unchanged SP, an enclosing negative ADDIU
frame allocation, and no intervening potentially aliasing store or call.
The forwarded value must still satisfy the existing ADDU/scale/base/index
proof; a word spill is not evidence of full 64-bit GPR preservation.

Attack order: the three independent address-taken entry/base barriers remain
unknown-state entries. The two callee-effect sites require width-aware
save/restore and memory effects through nested calls and unknown heap stores;
no ABI assumption can discharge those requirements. The two stack-cell sites
are considered next, retaining refusal of every unproven alias/index relation.
Diagnostic addresses and instruction output are ignored under
`target/paper-mario/0217/diagnosis.txt`. No ROM bytes enter git.

## Implemented rule and limits

The backward table predicate may replace a pending pointer LW from a nonnegative,
word-aligned SP offset with an exact-cell obligation. The first preceding store
must be SW to that same offset using unchanged SP. Every other store, CACHE or
COP0 operation while the cell is pending refuses, including stores at different
virtual stack offsets: no physical non-aliasing assumption is made. Calls refuse
until the cell and frame obligations are discharged; register-only callee effects
are insufficient. Every predecessor must establish a negative ADDIU SP,SP frame
allocation enclosing all four bytes. Independent entries, unsupported SP writes,
missing definitions and nonmatching cycle predicates remain barriers.

The saved source must still pass the existing ADDU, scaled-index, matching guard
and constant-base proof. ADDU produces a sign-extended word, so the SW/LW round
trip preserves this pointer; it does not preserve arbitrary 64-bit values.
Source clobbers after SW are allowed; the certificate still hashes their words,
the allocation, spill, reload and every traversed instruction. The verifier
recomputes from current bytes and CFG. No runtime instruction is skipped or
replaced; native mode gains neither a decoder nor an ABI fallback.

This rule is independent of ROM identity, addresses, table sizes and symbols.
It handles one pending pointer cell at a time, deliberately excluding stack index
identity, multiple live cells, nested-call memory summaries and general aliases.

## Evidence and outcome

The positive Rust fixture is red on the base; four new Rust tests cover source
clobber, source rechecks, guarded predecessor edges, independent entries, wrong
cells, frame bounds, SP changes, partial/floating/unknown stores, cache/COP0 and
calls. Four mutants are killed by semantic failures (exit 101): absent forwarding,
ignored aliasing writes, ignored frame bounds and ignored call barrier. Restored
focused suites pass. Three new native fixtures (indices 0, 1 and invalid 3) are
refused by the base and match pinned ares checkpoint CPU/PC/FPU/RAM state on the
candidate. Existing fault and protected-table-write contracts remain retained.
Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` ADDU/LW/SW source
was inspected (ISC); no implementation is copied or linked into native artifacts.

Fresh ROM-derived discovery and solve remain scoped OPEN/7, 56,851 blocks,
162 loads. The complete warm candidate ProgramMap equals the fresh baseline;
no blocker is added or closed. The three independent entry barriers remain
refused, the two callee-effect cases still lack width/alias/nested-effect proofs,
and the two stack-cell cases still lack the complete index and alias proof.
No Paper Mario native artifact or VI/fault/PCM run is emitted while OPEN.
This is a validated partial implementation, not PM closure.

Baseline discovery/solve took 25.654/9.956 s; warm candidate 30.796/17.077 s
with other work running. These are operational samples, not a controlled speed
claim. A cold helper build made the first discovery take 304.543 s; a subsequent
redundant rebuild was stopped (its solve exited 1 after 86.014 s). Reusing the
retained reference cache after matching exact input hashes and line endings
removes that setup bottleneck. The cache remains guarded by the reference builder.

Receipts and scripts live under ignored `target/paper-mario/0217/`, including
`baseline/`, `candidate/`, `candidate-cold-reference/`, `pm-map-diff.json`,
`mutations.json`, `native-baseline-red.json`, `native.log`, paired retained/fresh
control comparisons, diagnostic disassembly and `gate/result.json`. The final
exact-tree gate receipt records counts and results; no progress data or README
change is made.
