# Primary integration: return closure and function-level lowering

Base: 0f83077. Milestone: 1 (completes the native slice) and step 1 of the
NEXT.md plan. Worker: Claude co-integrator, user-authorized on main.

New `crates/plaid-core/src/returns.rs` (ADR-0127) partitions a map into
functions (call targets) and bodies (blocks reachable without entering a
call). A `jr $ra` site gets a `plaid-return-closure/v0` certificate listing
the functions containing it and the continuations of every `$ra`-linking call
into them; the solver recomputes it from the map and bytes and accepts it only
under `DeclaredStaticImagesGuardedRam`, with an explicit call/return
assumption. Sites reachable from a host-entered entry get no certificate.
Whole-ROM and `DeclaredStaticImages` scopes keep returns OPEN.

`crates/plaid-lower` now emits one C function per guest function. Calls are C
calls that pass the expected return address; every certified `jr $ra` checks
`$ra` against it and aborts with fault 5 on mismatch. `jalr` lowers to a
switch of calls over its proven targets.

Spike096 on pinned ISC ares 9408cb43 (recompiler disabled): alu, muldiv,
loops, memory, transfers and the new `calls` program (recursive factorial,
non-leaf calls, a `jalr` pointer call, a tail call, stack frames in the
compared RAM window) match exactly on PC, all GPRs, HI, LO and the 256-byte
RAM window. `self_modifying` faults 2, `cache_alias` faults 4 and the new
`bad_return` faults 5 natively.

OoT US 1.2 conditional window (local ROM, not committed): 43 of 45 indirect
sites carry return certificates, 1 a local-constant proof, 1 none. The
whole-ROM solve still reports 62 blockers, as intended for that scope.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests (new return-closure lowering tests included),
`scripts/test_cli.py`, spike096 differential run, `tools/progress.py --check`:
all PASS. No Actions. `native_complete` stays false everywhere.
