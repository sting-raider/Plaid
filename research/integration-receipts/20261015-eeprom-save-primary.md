# Primary integration: EEPROM save file

Base: 634ed94. Milestone 4. Worker: Claude co-integrator, user-authorized on
main, running autonomously.

**ADR-0165:** `--save <file>` loads a 512-byte EEPROM image at start.
- After every EEPROM write, the image is written to `<file>.tmp` and renamed
  over `<file>`.
- A leftover `.tmp` is recovered.
- A wrong-size file is refused and never overwritten.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`, including the new save check: counters
  0 then 1 across two runs, the exact 512-byte image, no leftover temporary
  file, a malformed save refused unchanged
- spike096: every program matches pinned ares 9408cb43; the fault codes are
  unchanged.
- `tools/progress.py --record` and `--check`

Actions were not used. `native_complete` stays false.
