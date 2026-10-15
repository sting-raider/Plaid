# Primary integration: load-delay tables, TLB runtime functions, in-image bodies

Base: b20cc64. Milestone 3 (SM64 closed under declared assumptions).
Worker: Claude co-integrator, user-authorized on main, running autonomously.

ADR-0154 accepts the `lw; nop; jr` table shape that unscheduled IDO emits;
goddard's `switch` statements use it.

ADR-0155:
- declares N64Recomp's ignored TLB functions (`osMapTLB`, `osUnmapTLB`,
  `osUnmapTLBAll`, `osSetTLBASID`) as runtime functions;
- requires an address-taken body's direct transfers to stay inside the
  image, which rejects the RSP boot microcode.

SM64 blockers under the address-taken scope: 32 → **1** (the
`audio_signal_game_loop_tick` table).

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`, including the new `tables` and
  `data_roots` tests
- `python scripts/test_cli.py`
- spike096: PASS. The new `delay_table` program matches pinned ares
  9408cb43. `driver.cpp` is unchanged, so it ran without `--rebuild`.
- `tools/progress.py --record` and `--check`

No ROM bytes or maps are committed, and Actions were not used.
`native_complete` stays false.
