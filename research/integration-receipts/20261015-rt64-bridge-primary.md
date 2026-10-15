# Primary integration: RT64 bridge, SM64 native title screen

Base: 3cb2f8b. Milestone 4 (SM64 native boot). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

**ADR-0163:**
- `runtime/rt64/` builds `plaid_rt64.dll`: pinned RT64 4337374 as a static
  library behind a C ABI. One renderer thread owns RT64 and its window.
  Guest RAM changes reach RT64 swapped to its RDRAM layout.
- `plaid_rt.c` with `-DPLAID_RT64` hands graphics tasks to the bridge and
  presents VI registers derived from `osViSetMode`, `osViSwapBuffer` and
  `osViBlack`.
- `docs/progress.json`: runtime and boot items move to partial.

Result: **SM64 boots natively to its title screen**: the animated goddard
head, the backdrop and "PRESS START", rendered by RT64 under D3D12. A
25-second run has no fault: 404 graphics tasks and 818 VI frames (the
33 VI/s speed baseline). This was checked by local screen captures, which
are not committed.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace` (78 suites)
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`, including the new GPU-free renderer
  bridge check
- spike096 (no Rust or lowering change):
  - every program matches pinned ares 9408cb43;
  - the fault codes are unchanged.
- `tools/progress.py --record` and `--check`

The RT64 build is local (MSVC 14.40, DirectX-Headers v1.616.0 under
`target/`). The ROM, the lowered C, the binaries and the screenshots stay
local. Actions were not used. `native_complete` stays false.
