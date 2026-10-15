# Primary integration: runtime identification over declared loads

Base: 3e9ef7c. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main, running autonomously.

ADR-0141: `plaid identify ... --loads <loads.json>` scans the composite
image that `discover` builds. Ambiguous names stay undeclared.

`scripts/test_cli.py`: a load copying an identified body makes it
ambiguous.

OoT US 1.2 local measurement: 59 identified functions, up from 39. 7684
blocks, 29 guarded blockers, down from 31: 22 indirect sites and 7 calls
into the 64DD segment. No instruction-scope blocker remains.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, `tools/progress.py --record` and
`--check`. spike096 is unaffected, since no lowering or driver changed. No
Actions. `native_complete` stays false.
