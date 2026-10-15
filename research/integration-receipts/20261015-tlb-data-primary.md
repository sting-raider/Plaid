# Primary integration: TLB-mapped data

Base: 0f77ce0. Milestone 4 (SM64 native boot). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

**ADR-0162:**
- `plaid_state` holds a 32-entry TLB.
- The runtime's `osMapTLB`, `osUnmapTLBAll` and `osVirtualToPhysical` use
  it.
- `plaid_addr` translates mapped data accesses as pinned ares does.
- Non-global entries, invalid pages and stores to clean pages fault 1.
- A mapped page that caches a line at a different D-cache index than KSEG0
  is a third cache class: mixing it with another class faults 4. The solver's
  memory assumption text says so.
- The README now describes native runs and the fix loop.

Result: SM64 runs natively for the full 90-second limit without a fault
(1459 graphics tasks, 9861 PI DMAs).

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096 (`driver.cpp` unchanged, so no rebuild):
  - every program matches pinned ares 9408cb43, including the new `tlb`;
  - `tlb_invalid` and `tlb_clean` fail closed with 1;
  - `tlb_alias` fails closed with 4;
  - the other fault codes are unchanged.
- `tools/progress.py --record` and `--check`

The ROM, the lowered C and the binaries stay local. Actions were not used.
`native_complete` stays false.
