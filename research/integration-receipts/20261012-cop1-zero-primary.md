# Canonical COP1 architectural context integrity

Base: a09eccffd570f392d5f02b2b3cfb6667fc55d2bc. Claim: 6118222189.

A new deterministic regression failed on canonical main: a nonzero GPR[0]
could act as the decoded address base and create a completed COP1 mutation
witness. The canonical normalizer now rejects impossible register-zero state
before either creating a witness or accepting an absent sink. The same check
also applies when the instruction uses another base register; architectural
context validity cannot depend on which operand is selected.

Focused six-test suite passes. Full local fmt, strict locked workspace/all-target
Clippy, locked workspace tests, CLI pipeline and diff gate pass. The retained
96-case source replays without rebuilding a reference: 72 store joins, ten mixed
origins, six equal-value counterexamples and 72 CU1 forgeries. Source SHA256
773673751c6735cb4c4f7b66c736eb18f2d59ddcac7c8ad817caf2d81a41291a and
report set 3258808138a6fa61a229beed4e4ae2e34a3fdd5f6f00057529a589beb7551503
remain unchanged. No Actions execution.

This tightens ADR-0120's existing canonical normalization boundary. It is not a
new mapping, FPR ancestry, capture/census, lifetime or native certificate. No
progress milestone changes. PR #10 frame chronology remains pending a meaningful
source composition; independent frame and FPR clocks cannot be joined by labels.
