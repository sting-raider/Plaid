# Primary integration: ROUND, CEIL, FLOOR and the .L conversions

Base: 2dfb418. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main, running autonomously.

ADR-0143: the guarded scope admits `ROUND/TRUNC/CEIL/FLOOR` to W and L, and
`CVT.L`, from S/D. They are lowered with exact integer rounding: ties to
even, ares's input ranges, inexact exactly when a fraction remains.

Spike096 on pinned ISC ares 9408cb43, built with `-msse4.1`: `fround`
matches, as do all earlier programs. `fpu_round_range` faults 7. Mutations
killed: L results written as 32 bits, wrong mode decode, ties rounded away
from zero.

ISA coverage is 175 of 209. OoT is unchanged at 29 guarded blockers.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096, `tools/progress.py
--record` and `--check`. No Actions. `native_complete` stays false.
