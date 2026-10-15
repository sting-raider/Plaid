# Primary integration: COP1 compares and BC1 branches

Base: 7665c7e. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main.

ADR-0135:
- All 32 `C.cond.S/D` compares lower to `fcc = (lt && a < b) || (eq && a ==
  b)`, matching pinned ares for ordered operands.
- A NaN operand aborts with fault 7, because its result depends on the
  unmodeled FCSR Invalid Operation enable.
- `BC1F/BC1T/BC1FL/BC1TL` branch on `fcc`.
- The guarded scope admits these opcodes and lists the no-NaN-compare
  assumption.
- N64Recomp's compare lowering was not ported: its unordered forms are
  marked TODO and are wrong for NaN.

Spike096 on pinned ISC ares 9408cb43 (oracle driver rebuilt to print the
FCSR condition bit): `fcompare` covers 16 conditions × single/double over
1/2, 2/1, equal, -0/+0, denormal/0 and -inf/+inf. Each condition is recorded
through `BC1TL` and `BC1F`. The resulting masks are 0xf0f0 for less-than,
0xcccc for equal and 0 for greater-than, as IEEE predicts. The run matches,
as do the twelve earlier programs. The six negatives fail closed, including
`fpu_nan` with fault 7.

ISA coverage: 94 -> 130 of 209 measured forms. OoT US 1.2 local measurement:
16 guarded blockers. In boot code only the boot return and the
`0x80000f10` pointer call remain; 14 lie past the code-segment DMA boundary.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096 (`--rebuild`),
`tools/progress.py --check`. No Actions. `native_complete` stays false.
