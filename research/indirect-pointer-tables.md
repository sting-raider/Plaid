# Bounded pointer-table candidates

2026-10-08. Hypothesis: recognizing a common guarded dispatch shape can improve
code traversal without claiming snapshot data is immutable or exhaustive.

The first recognizer handles an immediate SLTIU index bound, selected BEQ/BNE
edge, scalar constant base construction and contiguous SLL by two, ADDU, LW and
JR/JALR. It checks known incoming boundaries and index writes, reads up to 256
entries from the supplied image and stores prefix/data hashes and assumptions.
Targets are candidate facts only. Duplicate pointers coalesce; unaligned pointers
and incomplete snapshots produce diagnostics. Recognized table sites retain an
immutability blocker and no closed-target proof.

Synthetic tests cover successful enumeration/traversal, duplicate entries,
snapshot changes, missing bytes, malformed pointers, entry bypass, wrong guard
direction, changed indices and absent/excessive bounds. Solver tests confirm that
discovering every listed target does not close the declared scope. Other dispatch
shapes, table relocations and mutation/guard certificates remain outstanding.
