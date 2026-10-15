# Primary integration: controller input

Base: 7ea0302. Milestone 4 (SM64 native boot). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

**ADR-0164:** `osContGetReadData` reports controller 1 as the OR of two
sources:
- `--press <buttons>@<vi>:<frames>` scripts, keyed to VI frames;
- the RT64 window's keyboard, through the bridge (`plaid_gfx_input`).

Controllers 2 to 4 report absent.

Result: SM64 gets past the title and file select natively into its intro
(Peach's letter, Lakitu over the castle grounds). A 60-second run has no
fault: 2014 VI frames, 994 graphics tasks. Checked by local screen captures,
which are not committed.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`: scheduling, the renderer bridge, and the
  new controller merge check
- spike096: every program matches pinned ares 9408cb43; the fault codes are
  unchanged.
- `tools/progress.py --record` and `--check`

The ROM, the binaries and the screenshots stay local. Actions were not used.
`native_complete` stays false.
