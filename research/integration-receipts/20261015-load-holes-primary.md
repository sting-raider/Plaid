# Primary integration: disjoint declared loads (holes)

Base: 9f6bbec. Milestones 2 and 3 (SM64). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

ADR-0150 lets declared loads sit apart from the base window. Gaps become
`CodeImage` holes that supply no words, and the image identity covers the
hole layout.

SM64 with its engine and goddard segments declared: 2936 → **5337 blocks**,
**12 guarded blockers** (all function-pointer calls), whole-map recall
**11.4%**. OoT (28) and Mario Party 2 (29) are unchanged.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`, including the new
  `tests/load_holes.rs` and the updated `declared_loads` unit test
- `python scripts/test_cli.py`, where a gapped load now discovers and solves
- spike096: PASS, including the new `load_gap` program. `driver.cpp` is
  unchanged, so it ran without `--rebuild`.
- `tools/progress.py --record` and `--check`

No ROM bytes or maps are committed, and Actions were not used.
`native_complete` stays false.
