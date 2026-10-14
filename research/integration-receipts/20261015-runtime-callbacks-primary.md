# Primary integration: runtime callbacks

Base: 5c9e586. Milestones: 3 and 4. Worker: Claude co-integrator,
user-authorized on main.

ADR-0130: runtime declarations may name argument registers carrying guest
code. `crates/plaid-core/src/callbacks.rs` proves each such argument at every
call or tail jump after the delay slot, reusing the local prefix rule (now
`indirect::prefix_state`, a behaviour-preserving refactor of the local
constant certificate). Proven targets become discovery roots. Their returns
are certified as `runtime_entered`, unproven arguments are
`unresolved_runtime_callback` blockers, and `plaid-lower` emits a fail-closed
`plaid_enter` dispatch over proven targets only.

Spike096 on pinned ISC ares 9408cb43: `callback` (guest function passed to a
runtime `spawn`, result 43) and the eight earlier programs match exactly; the
four negatives still fault 2, 4, 5 and 6. New lowering tests cover a callback
set in the `jal` delay slot and a memory-loaded pointer that stays OPEN.

OoT US 1.2 conditional window, local measurement only. Runtime declarations
are still a heuristic: functions containing system instructions, plus
`0x800030e0` as `osCreateThread` (callback `a2`), identified by its call
shape. The thread entry `0x8000063c` is now discovered, and coverage rises from
190 to 613 blocks. 28 runtime functions; guarded-scope blockers: 6 (boot return
at `0x8000058c`, `jalr v1` at `0x80000f10`, `jr t2` at `0x80003acc`, and
`MTC1`/`SWC1`/`SWC1` at `0x80000654..0x8000067c`).

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096 differential run,
`tools/progress.py --check`: all PASS. No Actions. `native_complete` stays
false everywhere.
