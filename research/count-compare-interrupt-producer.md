# VR4300 Count/Compare interrupt producer composition

Status: RUNNING checkpoint, claimed in issue #4 as `gpt56sol-count-compare-interrupt-producer-20261010`.

Canonical integration base: `211176e7a489fecf8331d02915ee982cd279cb62`.

Exact reference pins are taken from `refs.lock.toml`: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`, Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`, and n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`.

## Checkpoint findings

The already-validated interrupt-root result proves that a pending IP bit intersecting Status.IM with IE=1 and EXL=ERL=0 enters the BEV-sensitive general vector at `base+0x180`. Its closeout explicitly left timer-producer reachability open.

Exact pinned ares implements the timer producer in `CPU::stepCount`: it computes modular remaining distance from internal shifted Count to Compare, latches `Interrupt::Timer`/IP7 when a positive advance crosses that distance, and leaves pending latched until an acknowledgement. `MTC0 Count` flushes elapsed Count and replaces Count; `MTC0 Compare` flushes Count, replaces Compare, and explicitly clears Timer pending. Therefore a same-value Compare write is still a causal acknowledgement event even though the visible Compare value does not change.

The exact references disagree on one important Count-write scheduling detail. Ares compares future progression against the rewritten Count and fixed Compare. Mupen's `translate_event_queue` removes and recreates `COMPARE_INT` at the Compare register after a Count rewrite, likewise making the new Count relevant to the deadline (with its own event-order shim). Gopher64 instead shifts every enabled event by `new_count-old_count`, including the existing Compare event, which preserves the old relative deadline. This disagreement is being retained rather than promoted to hardware truth.

Pinned n64-systemtest names Cause bit 15 as `interrupt_compare`, but this worker has not found a dedicated Count/Compare timing test at that pin. Hardware/system-test timing evidence therefore remains a likely gap even if the bounded ares execution matrix passes.

Executable artifacts are under `experiments/count-compare-interrupt/`; branch-only CI is `.github/workflows/research-count-compare-interrupt.yml`.
