# Primary integration: declared-load lifetime

Base: 3a9f318. Milestone 4 (SM64 native boot). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

**ADR-0161:** a store or runtime write into a verified declared load's code
revokes its verification instead of faulting. The next block entered in that
load compares its bytes again (fault 8 on a mismatch). A load writing its own
code still faults 2. The solver's declared-load assumption text is updated.

Result: SM64 runs past goddard's reload (395 PI DMAs, from 269). It now fails
closed with fault 1 on goddard's TLB-mapped dynlists (next: ADR-0162).

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`: libultra order `1,2,3,7,4,5,0x99`
- spike096, without `--rebuild` (`driver.cpp` is unchanged since 3a9f318):
  - every program matches pinned ares 9408cb43, including the new
    `load_reload`;
  - `load_patch` now fails closed with 8;
  - the new `load_self` fails closed with 2;
  - the other fault codes are unchanged.
- `tools/progress.py --record` and `--check`

The ROM, the lowered C and the binaries stay local. Actions were not used.
`native_complete` stays false.
