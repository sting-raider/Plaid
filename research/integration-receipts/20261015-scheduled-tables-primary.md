# Primary integration: GCC's scheduled jump-table shapes

Base: 8909cc6. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main, running autonomously.

ADR-0140: the pointer-table recognizer accepts:
- instructions between the `SLTIU` bound and its branch, provided they
  preserve the index;
- the base `LUI` between the scale and the add, provided the scaled index is
  preserved;
- a branch re-entering the guard whose delay slot is the identical `SLTIU`.

Any other entry into the interval is still a bypass.

Tests:
- `crates/plaid-core/tests/tables.rs`: the scheduled shape closes, and four
  rejections hold.
- spike096 `scheduled_table` matches pinned ISC ares 9408cb43, as do all
  sixteen earlier programs. The negatives are unchanged.

OoT US 1.2 local measurement (identified runtime, declared `code` load): all
12 jump tables close. 8082 blocks, 31 guarded blockers, down from 42.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096, `tools/progress.py
--record` and `--check`. No Actions. `native_complete` stays false.
