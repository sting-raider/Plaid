# Primary integration: address-taken dispatch scope

Base: 7f5e981. Milestone 3 (SM64 closed under declared assumptions).
Worker: Claude co-integrator, user-authorized on main, running autonomously.

ADR-0153 adds a new scope, `DeclaredStaticImagesGuardedRamAddressTaken`
(`solve --address-taken`). Its one new assumption: a register call with no
other proof targets a function whose address the program takes. The
address-taken set comes from aligned ROM words and from code constants
inside decoded blocks, and `discover --address-taken` records it in the map.
The solver re-checks every member as a plausible, decoded function start.
Lowered code dispatches over the set and faults 3 on any other target.

SM64 blockers: 120 under the guarded scope, **32** under the address-taken
scope.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`, including the new `address_taken`
  test
- `python scripts/test_cli.py`, including the `--address-taken` discover and
  solve run
- spike096: PASS. The new `addrtaken` program matches pinned ares 9408cb43,
  and `at_bad` faults 3. `driver.cpp` is unchanged, so it ran without
  `--rebuild`.
- `tools/progress.py --record` and `--check`

No ROM bytes or maps are committed, and Actions were not used.
`native_complete` stays false.
