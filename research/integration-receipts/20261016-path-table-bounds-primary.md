# Primary integration: jump-table bounds over every path; OoT + overlays CLOSED (ADR-0180)

Base: 9e652ab. Milestone 5. Worker: Claude co-integrator, user-authorized on main.

When the ADR-0140 shape matcher fails, `tables::guarded` proves a jump
table's bound on every CFG path into the dispatch. The paths are walked
backwards through the delay slots each edge executes, and the walk fails
closed on interior entries, slot entries on the fallthrough, entry
points, calls and returns, loops and out-of-range guard senses.

| OoT 1.2 (local), `--address-taken` | Before | After |
|---|---|---|
| fixed image | CLOSED, 29,511 blocks | byte-identical |
| + 468 overlays (`discover --overlays`) | OPEN, 29 blockers, 138,829 blocks | **CLOSED**, 0 blockers, 140,154 blocks |
| + overlays, whole-ROM (no assumptions) | 14,642 | 14,812 |
| SM64 map | — | byte-identical |

Of the 29 blockers:
- 28 were jump tables, proven by this ADR;
- one was a false 8-byte signature match inside an overlay. It disappears
  when identification runs over the static images, as the pipeline does.

Three proven tables were checked against their disassembly:
- 0x808656b8: 15 entries at 0x80866a04;
- 0x80865b0c: 14 entries at 0x80866a6c;
- 0x8088486c: 10 entries at 0x80885ab0.

Gate on the exact tree, all passing (75 s):
- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace` (695; new: `tables_guarded`, 7 cases)
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096
- `tools/progress.py --record` and `--check`

During development the existing predecessor-bypass tests caught two entry
holes in the first draft: an entry at the guard branch, and a slot entry
on a taken edge. Both are fixed.

ROMs, maps and catalogs stay local. Actions were not used. `native_complete`
stays false. Next: lower relocated overlays with run-time binding
(ADR-0172).
