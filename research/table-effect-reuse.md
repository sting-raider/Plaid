# Walk-local callee effect reuse (ADR-0216, partial)

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

No Paper Mario native artifact or run is accepted. This is a progress checkpoint;
implementation, mutation checks, controls and the final gate remain pending.
