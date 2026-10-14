# Primary integration: guarded jump tables

Base: 880f089. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main.

ADR-0132:
- The table recognizer accepts the scale `SLL` in a non-likely guard's delay
  slot.
- Complete aligned snapshots become closure claims, rechecked by
  `tables::verify` and shared through `indirect::verify_static`.
- Only `DeclaredStaticImagesGuardedRam` accepts them, discharging the table
  immutability and identity obligations under a listed read-only-table
  assumption.
- `plaid-lower` store-protects table bytes (fault 2) and dispatches over the
  snapshot targets only.
- Every other scope still reports tables OPEN.

Spike096 on pinned ISC ares 9408cb43: `table` (s1 = 1111 over three cases and
a default) and the ten earlier programs match exactly. The five negatives
(`self_modifying` 2, `cache_alias` 4, `bad_return` 5, `overflow` 6,
`table_write` 2) fail closed. `crates/plaid-core/tests/tables.rs` now checks
that the guarded scope closes the table and that `DeclaredStaticImages`
stays OPEN.

OoT US 1.2 local measurement, same heuristic declarations: the table at
`0x80003acc` closes and its cases are discovered (628 blocks). Six guarded
blockers remain: the boot return and five memory-loaded function-pointer
calls (`0x80000f10`, and four `jalr t9` in the PI manager thread that the
heuristic leaves as guest code).

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096 differential run,
`tools/progress.py --check`: all PASS. No Actions. `native_complete` stays
false everywhere.
