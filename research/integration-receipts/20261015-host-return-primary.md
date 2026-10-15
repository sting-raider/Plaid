# Primary integration: a host entry returns to the host

Base: 69cc739. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main, running autonomously.

ADR-0146: `jr $ra` sites in a host entry's body get return certificates
with `host_entered`. Natively, the `$ra` check against the host's `$ra` is
unchanged, and `plaid_run` hands control back on that checked return.

Spike096 on pinned ISC ares 9408cb43, oracle rebuilt because `driver.cpp`
now enters with `$ra` = exit: `hostreturn` matches, as do all earlier
programs. `host_bad_return` faults 5. Mutations killed: wrong host-return
`s->pc`, the `$ra` check dropped.

OoT US 1.2 local measurement: 28 guarded blockers, down from 29.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096 `--rebuild`,
`tools/progress.py --record` and `--check`. No Actions. `native_complete`
stays false.
