# Primary integration: hardware-level RCP I/O; native OoT boots to its first overlay

Base: 1d778c8. Milestone 5. Worker: Claude co-integrator, user-authorized on main.

**ADR-0176:**
- libultra runtime functions, all generic: threads/timers, memory size, PI
  handles and I/O, VI framebuffer queries, SI queries, rumble pak absent.
- The D-cache coherence rule lets an uncached-only line become cached. It
  is differential-tested against ares (spike096 `uncached_first`).
- The stop report prints `$t9`.

**ADR-0177:** uncached CPU loads and stores to RCP memory and the PI bus go
to a runtime hardware model (`plaid_state.io`):
- SP DMEM/IMEM, PI status/timing, ROM words and the absent 64DD's open bus;
- SP memory is unknown after an unexecuted task and fails closed;
- anything else faults.

Function naming is no longer how hardware access gets supported, so unknown
library variants work. `osDriveRomInit` and `LeoDriveExist` need no
identification.

| OoT 1.2 native (local) | Before | After |
|---|---|---|
| link | 13 missing runtime functions | links |
| symbol map needed | (decomp list named `osDriveRomInit`) | none |
| boot | — | 680 PI DMAs, 2 VIs, 1 lowered RSP task |
| stop | — | fault 3: call to relocated game-state overlay 0x803b4df0 (ADR-0172) |

Gate on the exact tree, all passing:

| Check | Notes | Time |
|---|---|---|
| `cargo fmt --all -- --check` | | |
| `cargo clippy --locked --workspace --all-targets -- -D warnings` | | |
| `cargo test --locked --workspace` | 688 passed | |
| `python scripts/test_cli.py` | | |
| `python runtime/test_runtime.py` | new: `rcp_io` | |
| spike096 | new: `uncached_first` | |
| `tools/progress.py --record` and `--check` | | |
| whole gate | | 121 s |

ROMs, symbol lists, maps, lowered C and RSP snapshots stay local. Actions
were not used. `native_complete` stays false.
