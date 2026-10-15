# Primary integration: branch-and-link, LL/SC, SYNC and conditional traps

Base: b42b116. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main, running autonomously.

ADR-0145:
- `BLTZAL/BGEZAL` and their likely forms are lowered as calls that link
  unconditionally.
- `LL/LLD/SC/SCD` use an exact LLbit.
- `SYNC` is a no-op.
- Conditional traps are discharged under the guarded scope with a
  never-taken assumption and fault 10. Discovery continues past them.

Spike096 on pinned ISC ares 9408cb43: `system` matches, as do all earlier
programs. `trap_taken` faults 10. Mutations killed: `SC` ignoring the
LLbit, zero-extended `TGEIU`, the likely slot always run, no link when
untaken. `tests/traps.rs` covers the discovery fallthrough and the scope
split.

ISA coverage is 196 of 209. OoT is unchanged at 29 guarded blockers.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096, `tools/progress.py
--record` and `--check`. No Actions. `native_complete` stays false.
