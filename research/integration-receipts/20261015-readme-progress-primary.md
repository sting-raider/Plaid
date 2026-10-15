# Primary integration: README and progress maps refresh

Base: f6dd176. Worker: Claude co-integrator, user-authorized on main. The
user asked for the README and its maps to be brought up to date.

Changes:
- `docs/progress.json` matches the landed work. The SM64 milestones, the
  lowering, runtime and renderer items, and identification are now verified,
  backed by ADR-0127..0169. Five items were added, among them declared loads,
  assumption-scoped CLOSED, FPU lowering and RSP lowering. The evidence cards
  and the atlas frontier line were refreshed; the frontier now comes from the
  data instead of being hardcoded. Result: 50 verified and 18 partial out
  of 73.
- `plaid rsp-coverage`, with a unit test, lowers a sample of each of the 119
  instructions in the RSP manual. `tools/progress.py --record` stores the
  result in `docs/rsp-coverage.json`, and `docs/coverage.svg` gains a third
  treemap from it: RSP 119/119. Reserved vector encodings and LWV are left
  out (ADR-0168).
- The README gains a milestone table and a pipeline diagram, plus current
  per-ROM numbers and the audio rows of the native-run table. In
  `docs/NEXT.md`, milestone 4 is marked done.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096 and spike097
- `tools/progress.py --record` and `--check`

Actions were not used. `native_complete` stays false.
