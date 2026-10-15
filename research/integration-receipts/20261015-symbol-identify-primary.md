# Primary integration: runtime functions from a reference symbol map

Base: f1fd0f9. Milestones 2 and 3, toward SM64. Worker: Claude co-integrator,
user-authorized on main, running autonomously.

ADR-0148 adds `plaid identify ... --symbols`, which reads a reference symbol
map (GNU ld map or splat) instead of n64sym signatures. It declares
N64Recomp's reimplemented functions found inside the image. A name at more
than one address is ambiguous and stays undeclared. The trigger was a local
Mario Party 2 measurement (`research/mario-party-2-boot-window.md`): 29
guarded blockers, 27 of them behind an `osInitialize` whose SDK build
n64sym's database lacks.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`, including the new
  `symbol_maps_name_runtime_functions_inside_the_image`
- `python scripts/test_cli.py`, including the new identify `--symbols`
  check
- spike096: PASS. `driver.cpp` is unchanged, so it ran without `--rebuild`.
- `tools/progress.py --record` and `--check`

No ROM bytes are committed, and Actions were not used. `native_complete`
stays false.
