# Primary integration: table bound across a branch; SM64 CLOSED (milestone 3)

Base: 6bbb342. Milestone 3 (SM64 closed under declared assumptions): **met**.
Worker: Claude co-integrator, user-authorized on main, running autonomously.

ADR-0156 handles a table bound that is computed before the only branch into
the guard's block. The table walk continues through that branch's delay
slot. Bypass checks cover both pieces of the path, and the branch may not
write the flag or the index.

SM64 (main, engine and goddard segments) under
`DeclaredStaticImagesGuardedRamAddressTaken` gives **`status: closed`**:
- 0 blockers;
- 45419 blocks, 4385 indirect sites and 1341 address-taken functions;
- 14 assumptions, all listed in the report;
- `native_complete` false.

The guarded scope still has 91 register-call blockers. Reproduce with the
commands in `research/sm64-first-measurement.md`; the ROM and decomp map are
local only.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`, including the new hop test in `tables`
- `python scripts/test_cli.py`
- spike096: PASS. The new `hop_table` program matches pinned ares 9408cb43.
  `driver.cpp` is unchanged, so it ran without `--rebuild`.
- `tools/progress.py --record` and `--check`

No ROM bytes or maps are committed, and Actions were not used.
