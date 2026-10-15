# Primary integration: parallel lowered units and shared JALR dispatchers

Base: b12da43. Milestone 5 tooling. Worker: Claude co-integrator,
user-authorized on main.

**ADR-0174:**
- Multi-target JALR sites call one `plaid_call_<k>` dispatcher per target
  set instead of inlining every case.
- `lower-map --parts N` splits the program into units that compile in
  parallel.

SM64:
- C size: 47 MB in one unit → 33 MB, as a main unit plus 15 parts of
  about 1.6 MB.
- Native build (gcc -O1, 20 threads): 784 s → 48 s.
- `--parts 1` keeps one unit.
- The old single-unit executable and the new split executable produce
  identical output for 30 graphics tasks and 58 audio tasks: every task
  line, the RAM dump and the stop state.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py` (new: parts compile with `-Werror` and link with the runtime)
- `python runtime/test_runtime.py`
- spike096 on a fresh debug `plaid` (`addrtaken` now goes through the dispatcher and matches ares)
- `tools/progress.py --record` and `--check`

ROMs, maps, lowered C and executables stay local. Actions were not used.
`native_complete` stays false.
