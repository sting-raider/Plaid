# Primary integration: declared runtime functions (runtime boundary)

Base: 0eddfee. Milestones: 3 (closure under declared assumptions) and 4
(runtime link). Worker: Claude co-integrator, user-authorized on main.

ADR-0129 adopts N64Recomp's reimplemented-function model as an evidence-backed
discovery boundary. A `plaid-runtime-functions-v0` declaration names guest
entries the host runtime provides. Discovery records calls and tail jumps into
them without decoding them, the map stores them as `runtime_functions`, the
solver re-derives control flow with the same boundary and accepts them only
under `DeclaredStaticImagesGuardedRam` with a listed ABI assumption, and
`plaid-lower` calls `plaid_rt_<name>`. A runtime entry that guest control flow
also decodes is a blocker.

Spike096 on pinned ISC ares 9408cb43: the new `boundary` program calls and
tail-calls a declared `sum`. Ares runs the guest body; native code links
`runtime.c` and never decodes the body, whose `SYNC` is outside the scope.
Results (s1 = 404, s2 = 15) and all eight programs match exactly. The four
negatives fault 2, 4, 5 and 6.

OoT US 1.2 conditional window, local measurement only: declaring every called
function containing a system instruction (17 functions, chosen by a
heuristic rather than evidence) takes guarded-scope blockers from 82 to 1. The
remaining blocker is the boot function's own return to the host. This is not
closure: coverage falls from 293 to 190 blocks, and the first thread entry
`0x8000063c`, passed to `osCreateThread`, is undiscovered with or without the
boundary. Runtime callbacks into guest code are the next requirement.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests (new runtime-boundary tests included), `scripts/test_cli.py`,
spike096 differential run, `tools/progress.py --check`: all PASS. No Actions.
`native_complete` stays false everywhere.
