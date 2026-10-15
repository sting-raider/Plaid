# Primary integration: RSP vector unit

Base: 03bdc2d. Milestone 4 (audio). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

**ADR-0168:** the RSP prelude gains the vector unit, ported from the scalar
paths of pinned ares `interpreter-vpu.cpp` and the tables in `rsp.cpp` (ISC).
COP2, LWC2 and SWC2 lower to calls into it. Encodings that ares runs as VZERO,
LWV and unknown opcodes are refused.

Result:
- spike097 has 25 programs, 20 of them new vector programs, and all match
  pinned ares 9408cb43. The comparison covers the scalar registers, DMEM,
  RDRAM, the vector registers, the accumulator and the flags. The oracle
  runs ares's SIMD paths, so the ported scalar paths are checked against
  them.
- A mutation check broke six details of the port, and all six were caught.
- SM64's audio microcode lowers completely: 904 instructions. The result
  compiles without warnings.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096: unchanged and passing.
- spike097 with `--rebuild` (the driver changed): passing.
- `tools/progress.py --record` and `--check`

The ROM and the lowered microcode stay local. Actions were not used.
`native_complete` stays false.
