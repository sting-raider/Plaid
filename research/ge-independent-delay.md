# Independently guarded native delay instructions

Worker: ge-closure-r3-e11a43ae. ADR-0288 follows mapped runtime boundaries.
Commercial inputs, maps, replay caches, executables and PNGs remain ignored
under target/. No child agents, README edits, shim changes or reference copying.

## Contract

A transfer at the end of its source does not get its delay instruction from the
next analysis allocation. The architectural slot PC selects independent declared
TLB raw/replayed sources. Their complete image/generation identities and words
must agree; reserved, trapping, control-transfer, missing and conflicting slot
instructions refuse. Solver admission also checks slot metadata and the native
effect subset. Normal contiguous slots retain their existing handling.

Lowering emits the one verified instruction as host-native code. Its helper
binds the actual virtual slot address, selects only an admitted source, pins
that source for the complete instruction, and balances the pin on success and
fault. Guarded text includes the slot word even if it is not a normal function
entry. No guest decoder or runtime MIPS execution is introduced.

Straight-line copy/table/callback/return proofs cannot borrow neighboring storage
for an independent slot. Functions crossing that boundary use the existing live
FPR mode checks. Slot COP effects contribute to the solver's scope assumptions.
Branch conditions, likely annulment and architectural PC+8 link values retain
their existing native ordering.

## Reproduced reduction

Using exactly ADR-0287's 227 engine pages and data declarations, blocks stay
49,241 and residual blockers fall 44 -> 1. All 43 unsupported delay slots are
discharged. TLBWR at analysis 80801b94 / guest 70001b94 remains unsupported;
five residual transfer sites also remain recorded. Emission is still refused.
There is no GoldenEye executable, VI, logo or title claim at this milestone.

The retained release before receipt is 25.828/4.719 seconds for discover/solve;
the isolated debug after receipt is 39.875/5.734 seconds, with concurrent gates.
Different compiler profiles and workloads prevent a speed comparison. Inputs
and machine-readable maps/timings are target/ge-expanded-input and
target/delay-worktree/target/ge-delay-after in the producing checkout. Final
release measurements and integration gates belong under
target/receipts/ge-independent-delay before the canonical write.

## Verification

Thirteen synthetic programs match pinned ares across every GPR/FPR, PC, HI/LO,
FCSR and output RAM: JAL/JALR, ordinary/likely/linking taken and untaken arms,
slot loads/stores and an FPR transfer. Callee, slot and continuation use separate
analysis allocations and physical pages; virtual RA remains PC+8. Corrupt slot
bytes and an invalid odd-page mapping refuse at the slot PC before its register
or memory effects. Removing the slot call changes output RAM; removing the
source check defeats the source-corruption refusal. Both mutations are retained.

Core contracts check exact virtual/source identities, wrong image/generation,
missing declarations/bytes, nonrelocatable sources, invalid/control/trap slots,
equal-word alternatives and conflicting-word alternatives. Ordinary contiguous
analysis and the retained mapped continuation/branch contracts remain in the gate.
The full exact-tree fmt/clippy/workspace/CLI/runtime/progress checks and all eight
silent visible controls precede integration. Default GCC 15.2 and separately
built pinned ares 9408cb43 ISC/SLJIT notices are unchanged.

## Remaining refill semantics

The remaining TLBWR belongs to a guest Context-based refill routine, not an
accidental decoding. Random/Wired selection, Context/EPC and exception delivery
need their own native contracts. The NEC manual describes a decrementing Random
register, while pinned ares samples its selection; those are distinct models.
No arbitrary index, permanent page mapping or counterfactual reachability is
substituted here. A singleton Random domain at Wired=31 can be timing-independent;
lower Wired values require additional evidence. See NEC U10504EJ7V0UM00,
sections 5.4.2/5.4.4, https://hack64.net/docs/VR43XX.pdf, and the exact pinned
ares interpreter-scc.cpp and n64-systemtest Wired/Random tests. No upstream body
is copied into Plaid.
