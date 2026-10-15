# Primary integration: guarded flag cells (negative result)

Base: 21265ef. Milestone: 5. Worker: Claude co-integrator, user-authorized
on main, running autonomously.

ADR-0147 records a prototyped and reverted mechanism: guarded flag cells
that prune branches. On OoT it would have cut 28 guarded blockers to 20,
but its writer census cannot see stores through pointers, so its value sets
are unsound for runtime state. Details are in
`research/guarded-flag-cells.md`.

No code changed. Docs-only landing: `tools/progress.py --check`. No
Actions. `native_complete` stays false.
