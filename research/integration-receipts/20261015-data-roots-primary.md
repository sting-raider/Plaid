# Primary integration: data-pointer and layout discovery roots (milestone 2 met)

Base: 62958c7. Milestone 2 (SM64). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

ADR-0152 adds opt-in heuristic discovery roots (`discover --data-roots`)
from three sources: function pointers stored as ROM data, `lui`/`addiu`
code constants, and a second pass over function layout after `jr ra`. They
are roots only, so a wrong root can only keep a map OPEN.

SM64 whole-map recall: 11.5% → **99.03%** (3795/3832, `meets_target:
true`), scored locally against the matching decomp map. Milestone 2 is met.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`, including the new `data_roots` unit
  tests
- `python scripts/test_cli.py`, including the new `--data-roots` run
- spike096: PASS. `driver.cpp` is unchanged, so it ran without `--rebuild`.
- `tools/progress.py --record` and `--check`

No ROM bytes or maps are committed, and Actions were not used.
`native_complete` stays false.
