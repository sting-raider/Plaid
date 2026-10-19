# Scheduled indexed dispatch (ADR-0206)

The guarded table producer now starts from the surviving LW definition of the
JR/JALR target register. It recovers the table-pointer ADDU through the existing
bounded predecessor walk, even when scheduling places it before the guard.
Independent scalar instructions may separate the load and jump. Source bytes,
image/generation, CFG prefix, exact table snapshot and target identities remain
part of verifier recomputation; slot-view remapping remains site-specific.

The scaled operand may use SLL or SLLV with an exact proven shift amount of 2.
Supported backward constant definitions include LUI, ADDIU and restricted
zero/immediate moves. Unsupported definitions, shared unresolved obligations,
unbounded predecessor paths and unresolved cycles stay unknown. This does not
assume that guest callees preserve registers or that loop-preheader values
survive arbitrary backedges.

Two authored counterexamples reproduced false positives in the prepared
candidate and now fail closed:

- A pointer formed from an old index, followed by an index overwrite and a
  guard on the new value. Bound-index writes are rejected while the pointer
  definition is still unresolved.
- Shift-constant propagation sharing a register with the table-base proof.
  Consuming the current definition previously let the base proof read an older
  LUI. Shared unresolved obligations are now rejected rather than skipped.

Retained Rust contracts cover these cases, current-index rechecking loops,
stale flags/indices, nearest-load clobbers, constant changes, annulled likely
slots and byte/generation edits. The proposed guard-delay-slot overwrite from
independent review is also retained: its exact fixture already rejects the
changed index through the existing index-definition check.

`python runtime/test_indexed_dispatch.py` assembles only authored words. Its
precomputed-pointer and SLLV loops exercise out-of-range -1 and all three valid
indices, with independent work between LW and JR. Native registers, PC, HI/LO,
FPU state and RAM checkpoints equal pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`. A table write faults 2; changing the
stride from 2 to 3 refuses native emission. The full runtime gate includes this
contract. Additional TLB contracts retain earlier-index shadow and late
clear-all overflow atomicity, pre-entry pointer-cell tampering, and writable
unrelated data.

The selected Paper Mario ROM remains unaccepted; native emission still requires
scoped CLOSED. The fresh ROM-only pass is OPEN/17, 56,495 blocks and 162 loads
(previously OPEN/18, 55,666 blocks). The 95-entry dispatch closes and exposes
829 additional blocks; no new blocker sites appear in this round. Ignored
analysis receipts are under `target/paper-mario/0206/`. The semantic-edit release
rebuild took 74.181 seconds; inference 11.136, identification 8.922, discovery
43.178 and solve 13.738 seconds. This edit timing is separate from the controlled
unchanged-source build-cache experiment.
All 18 prior table extents had qualified ROM sources; the remaining work is
control/dataflow proof, including loop-preheader values and calls. No game
addresses or external game metadata enter production analysis. See
`native-build-iteration.md` for the separately measured local build speedup.
