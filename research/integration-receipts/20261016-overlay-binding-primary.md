# Primary integration: relocatable overlays run natively through a verified binding (ADR-0181)

Base: 42513ef. Milestone 5. Worker: Claude co-integrator, user-authorized on main.

Overlay code is lowered at its link address. It runs only where the
ADR-0172 verifier finds its relocated bytes in RAM. Relocated immediates
are read from the bound copy. Return addresses are the bound copy's.
Writes into bound text revoke the binding.

| Measurement | Before | After |
|---|---|---|
| OoT native boot (PLAID_RSP) | fault 3 at 0x800a151c, call into relocated overlay | first graphics task, 686 PI DMAs, no fault |
| OoT + 468 overlays, `--address-taken` | CLOSED, 140,154 blocks, 13 assumptions | CLOSED, 141,268 blocks, 14 assumptions |
| OoT + overlays, whole-ROM | 14,812 blockers | 14,917 |
| SM64 `--address-taken` | CLOSED, 45,419 blocks, 1,341 address-taken | CLOSED, 45,419 blocks, 1,343 address-taken |
| OoT fixed image | CLOSED, 29,511 blocks | unchanged |

The OoT run also needed `--fr0` (ADR-0160) in the local loop. Without it,
a `div.d` read its FR=0 register pair as FR=1 and faulted 7.

spike096 adds `overlay`, which matches pinned ares at two bases, one with
a LO16 carry. It also adds three programs that must fail closed:
`ovl_tamper` (3), `ovl_self` (2) and `ovl_callback` (8).

Gate on the exact tree, all passing:
- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace` (695)
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- `python runtime/test_overlays.py`
- spike096 (51 s; driver.cpp unchanged, no rebuild)
- `tools/progress.py --record` and `--check`

ROMs, maps and lowered C stay local. Actions were not used.
`native_complete` stays false. Next: an RT64 build of OoT past its first
frame, and retiring assumptions.
