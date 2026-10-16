# Primary integration: discovery places relocatable overlays at link addresses (ADR-0179)

Base: c114210. Milestone 5, ADR-0172 stage 2a. Worker: Claude co-integrator, user-authorized on main.

`plaid discover … --overlays` catalogs the overlay tables inside the image
as composed so far, then adds each executable overlay as a relocatable
declared load at its link address. Data-only overlays and colliding link
ranges are left out, and the loads carry catalog evidence.

| OoT 1.2 (local) | Fixed image | With `--overlays` |
|---|---|---|
| overlays placed | 0 | 468 of 469 |
| blocks | 29,511 | 138,829 |
| discover | 3.3 s | 43 s |
| `solve --address-taken` | closed, 0 blockers | open, 29 blockers |

The 29 blockers are 28 GCC jump-table shapes outside ADR-0140's recognizer
and one overlay function that matches a runtime signature.

The map equals the hand-written load-file experiment's block count, and
re-running gives the identical map. Lowering refuses the map until it is
CLOSED and overlays are bound at run time (ADR-0172).

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace` (688)
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096
- `tools/progress.py --record` and `--check`

The redundant closure clippy found was fixed, then clippy, fmt and the
workspace tests were re-run on the final tree.

ROMs, catalogs and maps stay local. Actions were not used. `native_complete`
stays false.
