# Bounded callee no-write proofs (ADR-0210)

Base: `bbf99fcbb320912a9cabf44df6eb978476b561f6`.

The backward table proof previously rejected every call continuation. Some
dispatch loops require only a table-base register's earlier value after their
index and guard obligations have already been discharged. A direct guest
callee can carry that obligation when none of its reachable instructions
writes the required register. This is a static effect proof, not an ABI rule.

The private callee traversal checks decoded fixed-image words, all direct
branch paths and delay slots, nested JAL calls and canonical JR RA returns.
It rejects register writes, indirect calls/jumps, recursion, unsupported traps,
missing blocks and placed-slot code. Every callee read, including repeated
nested-call reads, consumes the caller's shared 4,096-word budget. Call depth
is bounded by eight; the predecessor walk retains its separate 32-frame cap.
All inspected words enter the table certificate's source hash. The complete
pending predicate remains the cycle-induction state.

The caller checks its JAL and delay slot and traverses all predecessors as
before. Final return annotation adds canonical return candidates to call
continuations; each such incoming source must occur in a no-write callee
summary for a JAL into that exact continuation. Unrelated return sources reject.
Return-target correctness remains subject to the existing checked-return
contract and independent control-flow closure. This proof does not establish
memory or timing effects and never removes execution of a callee instruction.
Save/restore of the required register is deliberately not accepted yet.

Authored integration fixtures initially failed without the consumer. Retained
checks cover leaf and nested calls, writes in caller/callee/return delay slots,
changed non-writing callee bytes, missing decoded blocks, unknown indirects,
external caller delay-slot entries and unrelated incoming returns. Eight
module tests cover branching, nested calls, unsupported words, recursion and
resource limits. The native call-loop fixture equals pinned ares over full
register, PC, FPU and RAM checkpoint state, including callee RAM writes and
nested-call stack saves. No additional reference code was copied or linked.

The fresh ROM-only Paper Mario pass improves from OPEN/15 to OPEN/14, still
56,799 blocks and 162 inferred loads. Site `80132e00` closes with 24 table
entries and four distinct targets; no new blocker sites appear. Production
code was probed at `6a37b3fb79bda283e068537ce91f3e94ea464644`; local receipts
are ignored under `target/paper-mario/0210/`. Discovery took 25.614 seconds
and solve 16.224 seconds, versus 28.258 and 16.785 for the previous milestone.
These single runs are operational timings, not a controlled speed claim.
Optimized incremental compilation took 34.571 seconds for this module change;
the prior constant-only change took 7.27 seconds and is not comparable.

Paper Mario native emission remains refused. Canonical acceptance still
requires independent review and the exact final tree's complete local gate.
