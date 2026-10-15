# Primary integration: discovery recall harness

Base: 7e39595. Milestone: 2 (scorer). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

ADR-0144: `plaid recall <map.json> <reference> [start end]` scores
discovered function entries against a GNU ld map (`.text` symbols) or a
splat `symbol_addrs` file (`type:func`), with a 0.99 recall target. The
reference is a local oracle and is never committed.

Tests: `recall` unit tests (section filtering, sign extension, aliases,
splat lines). `scripts/test_cli.py` checks a 2/3 recall with the missed
name, range restriction, and rejection of a reference with no code symbols.

No ROM was measured: SM64 is not available locally yet.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, `tools/progress.py --record` and
`--check`. spike096 is unaffected. No Actions. `native_complete` stays
false.
