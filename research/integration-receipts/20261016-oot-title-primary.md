# Primary integration: OoT reaches its title and file select with RT64 (ADR-0182)

Base: bf40711. Milestone 5. Worker: Claude co-integrator, user-authorized on main.

Five general gaps stopped the RT64 build of OoT after its first frame:
- AI registers read directly by a lowered `osAiSetNextBuffer`;
- an ambiguous `osViGetCurrentFramebuffer`, which left the scheduler
  waiting forever for a swap;
- overlay first functions missed by the layout rule;
- pointers built across blocks;
- SRAM.

A sixth, ignored VI special features, washed out the colours. All are
fixed in general terms (ADR-0182).

| Measurement | Before | After |
|---|---|---|
| OoT native with RT64 | 1 graphics task, then stall | boot logo, title and file select; 32 KiB SRAM save written |
| OoT + overlays, `--address-taken` | CLOSED, 141,268 blocks | CLOSED, 154,414 blocks, 14 assumptions |
| OoT + overlays, whole-ROM | 14,917 | 16,239 |
| OoT fixed image | CLOSED, 29,511 blocks | CLOSED, 29,542 blocks |
| SM64 `--address-taken` | CLOSED, 45,419 blocks | unchanged |
| OoT identification | 62 names, 2 ambiguous | 64 names, 0 ambiguous |

Diagnosis used two new runtime reports: thread states and wait queues in
the stop JSON, and `PLAID_TRACE_MQ`. They showed RDP-done delivered and the
next task notified but never started. The cause was the scheduler's
`osViGetCurrentFramebuffer` check.

Gate on the exact tree, all passing:
- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace` (698)
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`: 7 of 8 runs passed. Two failed while
  OoT ran in another window: the scheduling scenario must reach its yield
  within one 16 ms VI, and the base tree passed 4 of 4 when idle.
- `python runtime/test_overlays.py`
- spike096
- `tools/progress.py --record` and `--check`

ROMs, maps, saves and lowered C stay local. Actions were not used.
`native_complete` stays false. Next: play into gameplay.
