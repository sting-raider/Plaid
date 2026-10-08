# Bounded indirect analysis

2026-10-08. Hypothesis: a target constructed in a dominating straight-line prefix
can receive a finite certificate; runtime samples alone cannot.

Analysis tracks optional 64-bit constants through a small integer/address subset.
Unknown destination writes kill constants; register zero and 32-bit sign extension
are preserved. JR/JALR reads the target before delay-slot or link-register effects.
The certificate hashes prefix bytes and records block/site/target identities.
Verification re-runs the analysis on current CFG and supplied instruction bytes.
New entries, candidate bypasses, changed bytes or observed disagreements revoke
closure. A certificate is local to the declared image/CFG, not whole-ROM coverage.

Rabbitizer getters assert semantic operand presence: querying rs for LUI panics.
Transfer code uses raw bitfields and Rabbitizer's destination classification,
after decoding validity. Regression tests cover this API boundary as well as
loads killing constants, zero/sign extension, slots, re-entry and disagreements.

26 Rust tests and strict Clippy pass. Cross-block fixed-point propagation,
jump/pointer tables, return-stack/ABI proofs and discovered-target traversal are
follow-ups. Unsupported 64-bit execution/address modes remain a solver blocker.
