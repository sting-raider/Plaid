# Primary integration: lower a discovered ROM map; COP1 move guard

Base: 9f628dd. Milestone 4 (SM64 native boot), the part that needs no
license decision. Worker: Claude co-integrator, user-authorized on main,
running autonomously.

ADR-0157 adds `plaid lower-map <rom> <map.json> <entry> <exit> <out.c>`,
which lowers a CLOSED discovered ROM map. It also fixes the COP1 data-move
guard, which wrongly captured `add.s $f0, …`.

SM64:
- 45419 blocks become 47 MB of C, which gcc `-O0` compiles.
- With local stub runtime functions, the native run reaches
  `osCreateThread(&gIdleThread, 1, thread1_idle)`, with addresses as in the
  decomp map.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`, including the new `lower-map` closed and
  OPEN cases
- spike096: PASS. `farith` now includes `add.s $f0`, which faulted the
  lowering before the fix. `driver.cpp` is unchanged, so it ran without
  `--rebuild`.
- `tools/progress.py --record` and `--check`

The ROM, the generated C and the harness stay local. Actions were not used.
`native_complete` stays false.
