# Primary integration: COP1 arithmetic and FCSR

Base: 2ea71fc. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main, running autonomously.

ADR-0139:
- The guarded scope admits COP1 `ADD SUB MUL DIV SQRT ABS MOV NEG` (.S/.D),
  `CVT.S/CVT.D/CVT.W/TRUNC.W` (listed source formats), `CFC1` and `CTC1`.
- `plaid-lower` models FCSR as pinned ares: host rounding mode, cause and
  sticky flags, FS flushing, default NaN. Compares and `BC1` now clear the
  cause bits.
- Fault 7 now covers any COP1 operation outside the modeled subset.

Spike096 on pinned ISC ares 9408cb43, oracle rebuilt because `driver.cpp`
now prints FCSR: `farith` matches, as do the fifteen earlier programs.
`fpu_enabled` and `fpu_range` fault 7; the other negatives are unchanged.
Mutations killed by `farith`: cause reset removed, wrong tie rule,
`fesetround` removed, wrong RP flush, sticky flags removed.

OoT US 1.2 local measurement (identified runtime, declared `code` load):
42 guarded blockers, down from 566 (33 indirect sites, 4 direct targets, 3
unmapped targets, one COP0, one CACHE). ISA coverage is 159 of 209.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096 `--rebuild`,
`tools/progress.py --record` and `--check`. No Actions. `native_complete`
stays false.
