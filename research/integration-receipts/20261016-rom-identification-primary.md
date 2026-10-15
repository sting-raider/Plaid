# Primary integration: runtime functions named from the ROM

Base: f5103fa. Milestone 5, step 1. Worker: Claude co-integrator,
user-authorized on main.

**ADR-0171:** signature identification is settled by three rules:
- call relocations must reach identified callees;
- relocation-free signatures name identical copies at every address;
- `identify --reference-map` adds a reference map's names only where the
  ROM leaves them open.

Each declared function records its evidence, and the solver states the
map-only names as their own assumption.

Result:
- SM64's decomp map now backs 3 runtime names (`osInitialize`,
  `osContInit`, `osEepromLongRead`) instead of 56.
- Discovery plus the solver still reach `closed` over 45419 blocks under
  the address-taken scope.
- OoT under the same scope: 9764 blocks, 13 blockers. Its overlays are the
  next piece.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096
- `tools/progress.py --record` and `--check`

The native SM64 build was not relinked for this change; its lowered code
differs only where `__ll_rem` became a runtime call. ROMs and maps stay
local. Actions were not used. `native_complete` stays false.
