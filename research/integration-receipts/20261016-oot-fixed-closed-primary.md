# Primary integration: OoT's fixed code is CLOSED under the address-taken scope

Base: 5d71321. Milestone 5. Worker: Claude co-integrator, user-authorized on main.

**ADR-0175:**
- Address-taken roots come from Yaz0 streams' decoded words, not their
  compressed bytes.
- `osYieldThread` is a runtime function, implemented in `plaid_rt.c`.
- OoT's cartridge 64DD driver segment is declared as a local load.

| OoT 1.2 (local) | Before | After |
|---|---|---|
| blocks | 9,764 | 29,511 |
| address-taken functions | 55 | 425 |
| `solve --address-taken` | open, 13 blockers | **closed**, 0 blockers |
| discover time | 1 s | 8 s |

- The OoT map lowers to C in 2 s and compiles in 31 s across 16 parts.
- Linking with the runtime still needs 13 runtime functions, which is the
  next step.
- The SM64 map is byte-identical.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace` (new: Yaz0 root scan)
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py` (new: osYieldThread scheduling order)
- spike096
- `tools/progress.py --record` and `--check`

ROMs, loads files, maps and lowered C stay local. Actions were not used.
`native_complete` stays false.
