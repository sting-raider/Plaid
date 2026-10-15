# Primary integration: RSP scalar microcode lowering

Base: 0e9d2fe. Milestone 4 (audio). Worker: Claude co-integrator, user-authorized on
main, running autonomously.

**ADR-0167:** `plaid lower-rsp` lowers RSP microcode to C. The scalar unit and
COP0 are covered, with semantics from pinned ares. Every text word gets a
label, so register jumps dispatch over a closed set; anything else faults 3.
DMA completes as soon as it starts. DMA into IMEM faults 2, DMA outside RDRAM
faults 1, and the RDP registers fault 4. The vector unit is refused for now
and is ADR-0168.

Result:
- spike097: the alu, mem, branch, dma and halt programs match pinned ares
  9408cb43 in PC, the broken flag, all registers, DMEM and RDRAM
  0..0x2000.
- The four negative programs fault with codes 3, 2, 1 and 4.
- `crates/plaid-lower/tests/rsp.rs` has 5 contracts.
- On SM64's audio microcode, lowering stops at the first vector
  instruction (IMEM 0x1f0).

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096: unchanged and passing.
- spike097 with `--rebuild`: passing.
- `tools/progress.py --record` and `--check`. "RSP runtime/native path"
  is now partial.

The README gains a "Per-game inputs and known gaps" section. The ROM and the
lowered microcode stay local. Actions were not used. `native_complete` stays
false.
