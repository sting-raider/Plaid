# Walk-local callee effect reuse (ADR-0216)

Base: `171a6f578c761c8b2ccd1f99d8d9077e21b52998`.
Branch: `experiment/pm-closure-0216`; primary-integrator review only.

## Hypothesis and initial classification

An immutable backward table walk can reuse a successful callee no-write query
for the same architectural target and required GPR. Its map, image and caller
slot are fixed for the lifetime of that walk. Repeated queries need not reread
the same callee or consume its source-read budget again. All source words,
binding identities and return witnesses must still join the final certificate.
No cache may survive into another walk or certificate verification.

Fresh ROM-derived discovery/solve reproduces scoped OPEN/9, 56,851 blocks and
162 loads. The load declarations and identification are the retained ROM-only
ADR-0206 inputs, including the later inferred TLB sources; no symbols or decomp
metadata are supplied. Initial discovery/solve: 25.725/10.945 seconds after
bootstrapping the worktree reference links. A traced repeat: 27.327/15.846 s.

| Sites (diagnostic addresses only) | Count | First missing proof |
| --- | ---: | --- |
| `80a0893c`, `80a089b8`, `80a08aa8` | 3 | Base-register initialization on independent address-taken entries (`80a08960`, `80a089dc`, `80a08ad4`); they are genuine unknown-state barriers under the current scope. |
| `80ac21d4`, `80ae427c` | 2 | Repeated mapped-callee queries exhaust the shared read budget: only 119/191 reads remain at the first failed query. |
| `8003c488`, `8082cf20` | 2 | Callee register effects, with 4061/4062 reads still available; save/restore needs its own memory proof. |
| `80b2c178`, `80b2c344` | 2 | Captured table pointers loaded from stack cells; pointer/index equality and intervening aliasing writes are unproven. |

Ignored receipts/scripts: `target/paper-mario/0216/probe.py`, `diagnose.py`,
`traced/discover.log`, `traced/solve.json`, `site-disassembly.txt`. Diagnostic
instrumentation is restored after building and is not production code. The
external-entry group was considered first because it has the most sites;
removing its barriers would be unsound. The next largest actionable group is
the two resource-limited proofs. Unproven paths remain refused.

## Rule and verification

Each backward walk owns a cache keyed by architectural target and required GPR.
Its immutable map, image and caller slot supply the rest of the query identity.
Only successful bounded no-write proofs enter it. A miss consumes the existing
shared 4,096-read budget; a hit performs no new source traversal. Every hit still
contributes the effect's exact instruction/cell words, linked/placed/source
bindings and actual return witnesses to the enclosing certificate. Caches never
cross walks, discovery rounds or producer verification. The verifier builds a
fresh walk and rechecks the current bytes, declarations and indirect evidence.
The resource limit now measures performed work instead of charging for a
successful source traversal repeatedly. No budget constant is increased.

The rule names no game, address, symbol, table extent or ABI. It does not skip
guest instructions, infer save/restore, grant a new binding, or change runtime
generations, frame pins, source-cell protection or native dispatch guards.

The authored repeated-call positive fails before the change and passes after it.
Three Rust tests retain changed-byte rechecks, caller/callee clobbers, distinct
targets and shared-return entries. Four mutations are killed by semantic test
failures (exit 101): disable reuse, omit source words, ignore the register key,
ignore the target key. The last mutant initially survived because the independent
return-witness gate rejected its fixture anyway; a clobbering prefix sharing the
same return exposes the actual unsafe reuse. Restored focused suites pass.

An authored native loop makes sixteen calls through long guest leaf/nested
bodies, writes RAM and saves/restores RA. Its complete captured CPU/PC/FPU/RAM
state equals pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
The existing BREAK, protected-table-write and invalid-scale/stride controls
remain in that suite. The pinned ISC JAL/JR/LW/SW/ADDU source was inspected;
no upstream code is copied or linked into native mode.

Fresh candidate discovery/solve is scoped OPEN/7, still 56,851 blocks and 162
loads. Both resource-limited sites close: five/six table entries, three distinct
targets each. There are no new blockers. Discovery/solve took 28.866/12.203 s;
the earlier 25.725/10.945 s untraced and 27.327/15.846 s traced baseline runs
are operational measurements with concurrent work, not a controlled speed claim.
No Paper Mario native artifact or VI/fault/PCM run is accepted while OPEN.

Ignored final receipts are under `target/paper-mario/0216/`: `classification.json`,
`mutations.json`, `mutation-restored.log`, `candidate/`, control comparisons and
`gate/result.json`. Final exact-tree gate results belong in that machine-readable
receipt. No progress milestone or README change is made.
