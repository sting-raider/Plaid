# Primary integration: forwarded runtime callbacks and the first SM64 measurement

Base: 09ccdce. Milestones 2 and 3 (SM64). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

ADR-0149 proves runtime callbacks that a wrapper forwards from its own
argument, such as SM64's `-O0` `create_thread`, by following the argument
to every direct caller's constant. The solver records the assumption that
pointer stores do not write argument homes. Natively, `plaid_enter` still
faults 3 outside the proven set.

With the user's SM64 ROM and a locally built, matching decomp map, SM64's
main segment goes from 13 to **2936 blocks**, with **8 guarded blockers** and
**8.1% recall** (`research/sm64-first-measurement.md`). OoT (28) and Mario
Party 2 (29) are unchanged.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`, including the new
  `tests/forwarded_callbacks.rs`
- `python scripts/test_cli.py`
- spike096: PASS, including the new `forwarded` program. `driver.cpp` is
  unchanged, so it ran without `--rebuild`.
- `tools/progress.py --record` and `--check`

No ROM bytes, maps or decomp code are committed, and Actions were not used.
`native_complete` stays false.
