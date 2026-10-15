# Primary integration: IDO slot-bound jump tables

Base: f03fc51. Milestone 3 (SM64). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

ADR-0151 accepts IDO's jump-table guard, where the `sltiu` bound sits in
the delay slot of the previous non-likely branch. SM64 goes from 5337 to
**5580 blocks** and from 12 to **10 guarded blockers**, with 2 of its 3
audio tables closed. OoT (28) and Mario Party 2 (29) are unchanged.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`, including the new IDO shape test. Its
  positive case fails without the change.
- `python scripts/test_cli.py`
- spike096: PASS, including the new `ido_table` program. `driver.cpp` is
  unchanged, so it ran without `--rebuild`.
- `tools/progress.py --record` and `--check`

No ROM bytes are committed, and Actions were not used. `native_complete`
stays false.
