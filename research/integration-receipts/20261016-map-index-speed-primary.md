# Primary integration: one map index for per-site proofs

Base: eec93a8. Milestone 5 tooling. Worker: Claude co-integrator,
user-authorized on main.

**ADR-0173:** `indirect::MapIndex` replaces whole-map scans in four places:
- local-constant, jump-table, callback and return-closure proofs;
- the solver's per-site and identity-overlap checks;
- lower-map's per-function block walk.

AGENTS.md rule 8 now reads "Speed is a priority".

SM64, release build, same inputs. Every output is byte-identical to the
previous code's (`cmp`).

| Step | Before | After | Output |
|---|---|---|---|
| discover `--address-taken --fr0` | 14 min 56 s | 17–30 s | map identical (45419 blocks, 4385 sites) |
| solve `--address-taken` | 55 s | 3 s | report identical |
| lower-map | 130 s | 4 s | 46,820,873-byte C identical |

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096 (driver.cpp unchanged, so no rebuild)
- `tools/progress.py --record` and `--check`

ROMs, maps and the lowered C stay local. Actions were not used.
`native_complete` stays false.
