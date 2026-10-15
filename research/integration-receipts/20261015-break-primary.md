# Primary integration: BREAK as a checked abort

Base: 1851809. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main, running autonomously.

ADR-0138:
- The guarded scope admits `BREAK` and discharges its discovery fact on the
  map and on the re-derived facts. It lists "BREAK is never executed" as an
  assumption.
- `plaid-lower` aborts with fault 9.
- `SYSCALL`, `ERET` and the conditional traps stay unsupported.

Spike096 on pinned ISC ares 9408cb43: `divcheck` (a `div` with an untaken
GCC divisor check) matches, as do the fourteen earlier programs.
`break_reached` faults 9; the other negatives are unchanged.

OoT US 1.2 local measurement (identified runtime, declared `code` load):
566 guarded blockers, down from 748. ISA coverage is 131 of 209.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096, `tools/progress.py
--check`. No Actions. `native_complete` stays false.
