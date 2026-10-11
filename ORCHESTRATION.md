# Plaid Parallel Research and Integration Orchestration

This file governs parallel Plaid workers. It complements `AGENTS.md`; it does not replace Plaid's architectural invariants.

## 1. Integration modes

Plaid has two explicit modes.

### Normal mode

One continuing primary implementation/integration session owns canonical integration. Parallel workers research, prototype, validate, and prepare integration candidates in isolated branches/worktrees. The primary integrator decides what lands on `main`.

### User-authorized direct-integration mode

When the user explicitly authorizes direct integration, multiple workers may prepare and validate production changes in parallel and may attempt to land them directly on `main`.

Canonical writes in this mode are serialized by **exact-head compare-and-swap (CAS)**. There is no main-write lease.

A worker may only land a commit whose parent is the exact `main` SHA against which that worker's final validation was run. If `main` moves before the update, the validation is stale for canonical integration even if the worker's own patch did not change.

## 2. Roles

### Primary integrator

The primary integrator owns canonical reconciliation in normal mode and resumes ownership when a temporary direct-integration period ends. It reviews evidence, resolves overlapping designs, reruns important tests, and keeps `docs/STATUS.md`, `docs/NEXT.md`, and `docs/DECISIONS.md` coherent.

### Research worker

A research worker owns one bounded hypothesis or experimental slice. It may clone/fetch Plaid and pinned references, create isolated branches/worktrees, patch legal reference code for experiments, compile/run software, instrument, fuzz, benchmark, trace, disassemble, differential-test, and produce candidate patches or durable evidence.

A research worker does not write `main` unless the user explicitly enables direct-integration mode for that worker/session.

### Direct-integration worker

A direct-integration worker starts from completed research or an already-validated invariant and turns one bounded cluster into production code/tests/docs. It must reproduce the important result against current `main`, validate the exact candidate tree locally, and use exact-head CAS for the canonical update.

## 3. Canonical state and read order

Repository: `sting-raider/Plaid`

Canonical branch: `main`

Before selecting work, read in this order:

1. `AGENTS.md`
2. `ORCHESTRATION.md`
3. `docs/STATUS.md`
4. `docs/NEXT.md`
5. `docs/DECISIONS.md`
6. `SWARM_BACKLOG.md`
7. `research/integration-harvest-20261011.md` when present/relevant
8. relevant `research/`, `spikes/`, `experiments/`, and `instruments/`
9. recent commits on `main`
10. GitHub issue #4 claims/closeouts
11. relevant `research/*`, `integration-prep/*`, and `direct-integration/*` branches
12. the exact pinned reference revision from `refs.lock.toml` when reference semantics matter

Current `main` and canonical documentation are authoritative. Old summaries, old prompts, research branch labels, and historical CI are not authority by themselves.

## 4. Shared coordination ledger

Live coordination ledger: `https://github.com/sting-raider/Plaid/issues/4`

Every parallel worker must inspect it before substantive work.

Research claim template:

```text
CLAIM
worker: <short chat/session identifier>
started_utc: <timestamp>
lane: <bounded research slice>
hypothesis: <specific proposition to prove/disprove>
touching: <Plaid paths / upstream repos / experiments likely to change>
expected_output: <research note / spike / patch / tests / measurements>
```

Direct-integration claim template:

```text
DIRECT-INTEGRATION CLAIM
worker: <id>
base_main: <sha>
cluster: <bounded integration topic>
source_research: <branches/commits/closeouts>
touching: <expected production paths>
```

Claims coordinate semantic ownership and prevent duplicated work. They **do not lock or reserve `main`**.

A claim becomes recoverable after roughly **35 minutes without meaningful durable progress**. Meaningful progress includes a commit, substantive evidence update, reproducible test result, research note/spike update, or useful patch/harness/checkpoint. `still working` is not meaningful progress.

When recovering an expired claim, inspect and preserve useful prior work before starting over.

## 5. Exact-head CAS protocol for direct integration

The canonical-write protocol is deliberately mechanical:

1. **Fetch current `main`.** Record exact SHA `A`.
2. **Reconcile onto `A`.** The proposed canonical commit must be based on `A`, not on an older branch head.
3. **Validate that exact tree locally.** Run focused tests plus all applicable canonical gates.
4. **Refetch `main` immediately before writing.**
5. If current `main != A`, stop. Reconcile onto the new head and rerun the required validation. Do not reuse the old green result as the canonical gate.
6. If current `main == A`, create a clean commit whose parent is exactly `A`.
7. Atomically update `main` using `expected_sha=A` / force-with-lease-style compare-and-swap semantics, with force disabled for normal fast-forward integration.
8. If the CAS is rejected, another worker won. This is expected, not an error. Fetch the new head, reconcile, retest, and retry.
9. Never force-push `main`, never overwrite another worker's canonical commit, and never disable the expected-head check.

The required invariant is:

> A commit may land on `main` only when its parent is exactly the canonical `main` SHA against which its final integration validation was performed.

This allows parallel preparation and parallel validation while still serializing successful canonical state transitions.

### Why stale validation is not enough

Two patches can each be green against `A` but interact when combined. If worker 1 moves `main` from `A` to `B`, worker 2's `A + patch2` result does not validate `B + patch2`. Worker 2 must reconcile and retest.

## 6. Local validation policy

GitHub Actions is manual-only. Do not create PRs, workflow files, or `workflow_dispatch` runs merely to obtain validation for ordinary direct integration.

Production Rust changes should run locally at minimum:

```bash
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
```

Also run:

- focused regressions for the changed subsystem;
- retained synthetic contract checks affected by the change;
- `python tools/progress.py --check` when progress data changes;
- exact pinned-reference checks from `refs.lock.toml` when semantics depend on a reference;
- independent/adversarial checks where provenance or closure is affected.

Historical CI may be cited as supporting evidence, but it does not replace current validation of the exact candidate tree.

If the worker cannot run a required gate, it must not claim the integration is fully green and must not land it solely on the strength of old CI.

## 7. Isolation and conflict rules

Parallel work is aggressive; canonical state remains conservative.

- Never force-push or rewrite `main` history.
- Prefer `research/<topic>-<shortid>`, `integration-prep/<topic>-<id>`, or `direct-integration/<topic>-<id>` branches for non-canonical work.
- Do not mechanically merge research branches wholesale.
- Keep temporary reference instrumentation, generated fixtures, and worker-only workflows out of canonical production unless they genuinely belong there.
- Keep reference modifications separated from project-owned production code and preserve license boundaries.
- No ROMs, firmware, copyrighted game assets, redistributed copyrighted traces, secrets, or credentials in git.

Integration-sensitive paths include:

- `crates/plaid-core/src/program.rs`
- `crates/plaid-core/src/fetch.rs`
- `crates/plaid-core/src/solver.rs`
- `crates/plaid-core/src/merge.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- `docs/progress.json`
- `README.md`
- `instruments/mupen/discovery.patch`

Multiple workers may study the same file, but they should not duplicate the same semantic integration cluster.

## 8. Work selection

Choose work in this order:

1. inspect what current `main` already consumes;
2. recover useful expired/blocked integration work;
3. take a high-value unclaimed blocker or validated research cluster from `docs/NEXT.md` / integration-harvest notes;
4. prefer production consumers of already-validated evidence over opening another ordinary research lane during an integration-harvest phase;
5. run a narrowly bounded experiment only when needed to resolve a concrete integration ambiguity;
6. stop rather than invent work when no high-confidence candidate remains.

Do not infer that a research branch needs integration merely because it exists. Classify it as already integrated, superseded, regression-only, research-only, partial, blocked, or genuinely useful.

## 9. Experimental and proof contract

Every experiment or correctness-sensitive integration needs a falsifiable claim and explicit limits.

Never upgrade:

- observation -> exhaustive proof;
- physical address -> byte origin;
- equal payload -> equal provenance/generation;
- cache tag -> resident-byte history;
- numeric target -> executable identity;
- compilation -> execution;
- repeated runs -> universal coverage;
- one reference implementation -> hardware truth;
- one game's behavior -> N64-wide invariant.

For provenance/closure work, adversarial cases should include relevant variants of equal-value different-generation evidence, stale cache state, aliases/TLB changes, missing/reordered events, reused event identities, conflicting backing, partial/failed writes, reset/save/restore boundaries, and synthetically altered/deleted provenance.

UNKNOWN stays UNKNOWN.

## 10. Durable outputs and documentation

A useful worker session should leave durable evidence such as:

- `research/<topic>.md`;
- `research/integration-receipts/<date>-<topic>-<worker>.md`;
- a deterministic fixture/harness;
- an isolated branch commit;
- benchmark/trace summary;
- a precise negative result.

Do not dump gigantic generated traces into git. Record hashes, commands, summaries, schemas, and ignored artifact locations instead.

Update `docs/STATUS.md`, `docs/NEXT.md`, and `docs/DECISIONS.md` only when canonical state genuinely changes. Update `docs/progress.json` only when an auditable milestone changes state, then regenerate/check the progress outputs.

## 11. Closeout

Research closeout:

```text
CLOSEOUT
result: <VALIDATED / REJECTED / PARTIAL / BLOCKED>
artifacts: <branch, commit(s), note, spike, test commands>
key_evidence: <concise concrete findings>
remaining_gap: <what is still unknown>
integration_recommendation: <ADOPT / REJECT / INVESTIGATE / PRIMARY-INTEGRATOR-REVIEW>
```

Direct integration closeout:

```text
MAIN-INTEGRATION CLOSEOUT
worker: <id>
result: <INTEGRATED / REJECTED / BLOCKED>
validated_base_main: <sha>
new_main: <sha or unchanged>
cluster: <topic>
production_commits: <sha(s)>
local_validation: <exact commands/results>
docs_updated: <paths>
superseded_research: <branches/commits>
remaining_gaps: <explicit>
codex_handoff: <what the returning primary integrator needs to know>
```

There is no `MAIN-WRITE LEASE` or `MAIN-WRITE RELEASE` in the CAS workflow. Old lease comments are historical coordination artifacts only.

## 12. Returning primary integrator handoff

When the primary integrator resumes after a direct-integration period, it should:

1. fetch latest `main`;
2. inspect recent `MAIN-INTEGRATION CLOSEOUT` records and integration receipts;
3. verify that canonical docs match the landed state;
4. reconcile any remaining prepared/blocked candidates;
5. rerun broad validation before major new architecture work;
6. resume serialized primary ownership unless the user explicitly keeps direct-integration mode enabled.

Research branches are disposable. Evidence and canonical receipts are not.

## 13. North star

Parallelism exists to shorten the path to:

```text
N64 ROM
  -> trustworthy executable-byte provenance
  -> complete ProgramMap
  -> closed-world proof for a declared scope
  -> MIPS-to-native AOT compilation
  -> verified native runtime
  -> no runtime MIPS interpreter/JIT in native-complete mode
```

The workers are not competing to write the most code. They are competing to eliminate uncertainty without corrupting canonical state.