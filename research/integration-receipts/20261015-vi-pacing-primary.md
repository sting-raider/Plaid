# Primary integration: VI pacing on Windows

Base: 90467df. Milestone 4. Worker: Claude co-integrator, user-authorized on
main, running autonomously.

**ADR-0166:** the event pump sleeps on a high-resolution waitable timer on
Windows, because mingw `nanosleep` rounds 1 ms up to 15.6 ms. VI retraces
fall on fixed NTSC deadlines.

Result:
- SM64 went from 32.7 VI/s to 59.9 VI/s and 29.7 fps over 60 s, with no
  fault, and reaches gameplay.
- `test_runtime.py` asserts about 60 retraces per second (60, 60 and 61 in
  three runs).

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096: every program matches pinned ares 9408cb43; the fault codes are
  unchanged.
- `tools/progress.py --record` and `--check`

The ROM, the binaries and the screenshots stay local. Actions were not used.
`native_complete` stays false.
