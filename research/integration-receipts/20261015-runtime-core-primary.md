# Primary integration: runtime core, loop safepoints, FR = 0 COP1

Base: d2a35ad. Milestone 4 (SM64 native boot). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

**ADR-0159** adds:
- `runtime/plaid_rt.c`, Plaid's own libultra runtime: baton-scheduled host
  threads, message queues, events, PI DMA, controllers, EEPROM and 64-bit
  helpers;
- `PLAID_SAFEPOINT` at loop headers in `plaid-lower`;
- a per-word executable protection map that replaces the linear
  `plaid_code` scan.

**ADR-0160** makes the COP1 register mode a declared map property
(`--fr0`). Under FR = 0, lowering follows ares's pair semantics.

SM64 stays `closed`, now with an FR = 0 assumption. Natively it runs 96
graphics tasks at 30 fps, then fails closed (fault 2) when the menu reloads
goddard.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`, including the new safepoint and FR = 0
  `lower` tests
- `python scripts/test_cli.py`, including `--fr0`
- `python runtime/test_runtime.py`: libultra order `1,2,3,7,4,5,0x99`, 6 of
  6 runs
- spike096 with `--rebuild`, since `driver.cpp` gained the `fr0` argument.
  All programs, including the new `fpu_fr0`, match pinned ares 9408cb43.
  The fail-closed fault codes are unchanged.
- `tools/progress.py --record` and `--check`

The ROM, the lowered C and the binaries stay local. Actions were not used.
`native_complete` stays false.
