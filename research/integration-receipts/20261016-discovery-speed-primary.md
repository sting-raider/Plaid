# Primary integration: discovery labels returns once and resumes rounds (ADR-0178)

Base: a1c2854. Milestone 5 tooling, rule 8. Worker: Claude co-integrator, user-authorized on main.

Composing OoT's 469 catalog overlays at their link addresses made discovery
take 459 s. A profile showed three costs:
- return certificates were labelled after every address-taken round;
- each round restarted the indirect fixed point;
- each return certificate scanned every block and call edge.

All three are fixed without changing results.

| Run (release, local inputs) | Before | After | Output |
|---|---|---|---|
| SM64 discover | 30.7 s | 6.7 s | byte-identical |
| OoT fixed discover | 8.5 s | 3.3 s | byte-identical |
| OoT + 50 overlays discover | 70.6 s | 27.3 s* | byte-identical |
| OoT + 469 overlays discover | 459 s | 44 s | byte-identical |
| OoT + 469 overlays solve | 19.3 s | 4.5 s | byte-identical |
| SM64 solve | 2.1 s | 1.2 s | byte-identical |

\* Measured while another discovery was running.

Measurement: with every overlay composed, OoT has 138,829 blocks and
`solve --address-taken` reports 29 blockers: 28 unresolved indirect sites
and one decoded runtime function. Overlay execution is ADR-0172's next
stage.

Gate on the exact tree, all passing (156 s):

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace` (688)
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096
- `tools/progress.py --record` and `--check`

ROMs, load files, maps and catalogs stay local. Actions were not used.
`native_complete` stays false.
