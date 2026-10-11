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

### Validation-takeover worker

A validation-takeover worker finishes useful candidate work prepared by another session that lacked the execution environment for the final gate. It does not trust the prepared branch as canonical-ready. It independently reconciles the semantic diff onto current `main`, runs all required local validation, and becomes responsible for the final CAS and closeout.

## 3. Capability preflight comes first

**Before a direct-integration worker claims a lane, reads a large amount of branch archaeology, or begins implementation, it must verify that this session can actually perform the mandatory local gate.**

Minimum preflight:

```bash
git rev-parse --show-toplevel
git status --short
cargo --version
rustc --version
rustfmt --version
python --version
```

The local checkout must be writable and contain the Plaid workspace. The worker must also be able to fetch/refetch canonical `main` locally or otherwise materialize the exact current tree it will test.

For a cluster that depends on pinned emulator/reference semantics, verify the necessary pinned revision is locally present or locally fetchable before committing to that cluster.

### If generic capabilities are missing

Do **not** post a direct-integration claim. Do **not** spend the session implementing a candidate that cannot be validated.

Return promptly with:

```text
CAPABILITY-SKIP
worker: <id>
missing: <checkout/toolchain/reference capability>
reason: direct integration requires local validation of the exact candidate tree
```

The lane remains free for a capable worker.

A capability skip is not a project blocker and should consume almost no project work.

### If a task-specific capability is missing

Prefer another high-value cluster that can be fully validated in the current environment. Do not select a reference-dependent lane and discover at the end that the reference cannot run.

## 4. Canonical state and read order

Repository: `sting-raider/Plaid`

Canonical branch: `main`

After capability preflight succeeds, read in this order:

1. `AGENTS.md`
2. `ORCHESTRATION.md`
3. `docs/STATUS.md`
4. `docs/NEXT.md`
5. `docs/DECISIONS.md`
6. `SWARM_BACKLOG.md`
7. `research/integration-harvest-20261011.md` when present/relevant
8. recent commits on `main`
9. GitHub issue #4 claims/closeouts/handoffs
10. relevant `research/*`, `integration-prep/*`, `direct-integration/*`, `research/`, `spikes/`, `experiments/`, and `instruments/`
11. the exact pinned reference revision from `refs.lock.toml` when reference semantics matter

Current `main` and canonical documentation are authoritative. Old summaries, old prompts, research branch labels, and historical CI are not authority by themselves.

## 5. Shared coordination ledger

Live coordination ledger: `https://github.com/sting-raider/Plaid/issues/4`

Every parallel worker must inspect it before substantive work.

Research claim:

```text
CLAIM
worker: <short chat/session identifier>
started_utc: <timestamp>
lane: <bounded research slice>
hypothesis: <specific proposition to prove/disprove>
touching: <Plaid paths / upstream repos / experiments likely to change>
expected_output: <research note / spike / patch / tests / measurements>
```

Direct-integration claim:

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

## 6. Exact-head CAS protocol

The canonical-write protocol is deliberately mechanical:

1. **Fetch current `main`.** Record exact SHA `A`.
2. **Reconcile onto `A`.** The proposed canonical commit must be based on `A`, not on an older branch head.
3. **Validate that exact tree locally.** Run focused tests plus all applicable canonical gates.
4. **Refetch `main` immediately before writing.**
5. If current `main != A`, stop. Reconcile onto the new head and rerun the required validation. Do not reuse the old green result as the canonical gate.
6. If current `main == A`, create a clean commit whose parent is exactly `A`.
7. Atomically update `main` using `expected_sha=A`, with force disabled.
8. If the CAS is rejected, another worker won. This is expected. Fetch the new head, reconcile, retest, and retry.
9. Never force-push `main`, overwrite another worker's canonical commit, or disable the expected-head check.

Required invariant:

> A commit may land on `main` only when its parent is exactly the canonical `main` SHA against which its final integration validation was performed.

Two patches can each be green against `A` but interact when combined. If worker 1 moves `main` from `A` to `B`, worker 2's `A + patch2` result does not validate `B + patch2`. Worker 2 must reconcile and retest.

## 7. Local validation policy

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
- independent correctness stress tests where provenance or closure is affected.

Historical CI may be cited as supporting evidence, but it does not replace current validation of the exact candidate tree.

If a worker cannot run a required gate, it must not claim the integration is fully green and must not land it solely on old CI.

## 8. Validation handoff instead of environment BLOCKED

A worker should normally catch missing capabilities during preflight. If useful candidate work already exists before a missing capability becomes known, preserve it with a handoff rather than throwing it away.

Post:

```text
VALIDATION-HANDOFF
worker: <id>
cluster: <topic>
candidate_branch: <branch>
candidate_head: <sha>
prepared_base_main: <sha>
changed_paths: <paths>
reproduced_evidence: <what was already established>
remaining_validation: <exact commands/checks still required>
missing_capability: <why this session cannot run them>
notes: <known limitations / semantic cautions>
```

The result is `PREPARED_FOR_VALIDATION`, not `BLOCKED`, unless there is also a genuine technical blocker.

An execution-capable worker may take it with:

```text
VALIDATION-TAKEOVER
worker: <id>
source_handoff: <comment/worker>
candidate_branch: <branch>
candidate_head: <sha>
```

The takeover worker must:

1. inspect the handoff and original evidence;
2. fetch current `main`;
3. transplant/reconcile the useful semantic change onto current `main` rather than blindly trusting stale branch state;
4. run the complete local gate on the exact resulting tree;
5. use normal exact-head CAS;
6. post the final `MAIN-INTEGRATION CLOSEOUT`.

Do not weaken validation requirements merely to avoid a handoff.

`BLOCKED` should mean a real semantic/technical integration blocker: unresolved evidence, failing tests, conflicting invariants, unavailable required source data with no safe alternative, etc. A chat runtime simply lacking `cargo` is a capability mismatch, not a Plaid blocker.

## 9. Isolation and conflict rules

Parallel work is aggressive; canonical state remains conservative.

- Never force-push or rewrite `main` history.
- Prefer `research/<topic>-<shortid>`, `integration-prep/<topic>-<id>`, or `direct-integration/<topic>-<id>` branches for non-canonical work.
- Do not mechanically merge research branches wholesale.
- Keep temporary reference instrumentation, generated fixtures, and worker-only workflows out of canonical production unless they genuinely belong there.
- Keep reference modifications separated from project-owned production code and preserve license boundaries.
- No ROMs, firmware, copyrighted game assets, redistributed copyrighted traces, secrets, or credentials in git.

Integration-sensitive paths include `crates/plaid-core/src/program.rs`, `fetch.rs`, `solver.rs`, `merge.rs`, `lib.rs`, canonical docs/progress files, README, and reference instrumentation patches.

Multiple workers may study the same file, but they should not duplicate the same semantic integration cluster.

## 10. Work selection

Choose work in this order:

1. verify capability preflight;
2. inspect what current `main` already consumes;
3. recover useful validation handoffs or expired integration work;
4. take a high-value unclaimed blocker or validated research cluster from `docs/NEXT.md` / integration-harvest notes;
5. prefer production consumers of already-validated evidence over opening another ordinary research lane during an integration-harvest phase;
6. run a narrowly bounded experiment only when needed to resolve a concrete integration ambiguity;
7. stop rather than invent work when no high-confidence candidate remains.

Do not infer that a research branch needs integration merely because it exists. Classify it as already integrated, superseded, regression-only, research-only, partial, prepared-for-validation, blocked, or genuinely useful.

## 11. Experimental and proof contract

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

For provenance/closure work, correctness stress cases should include relevant variants of equal-value different-generation evidence, stale cache state, aliases/TLB changes, missing/reordered events, reused event identities, conflicting backing, partial/failed writes, reset/save/restore boundaries, and synthetically altered/deleted provenance.

UNKNOWN stays UNKNOWN.

## 12. Durable outputs and documentation

Useful durable evidence includes research notes, integration receipts, deterministic fixtures/harnesses, isolated branch commits, benchmark/trace summaries, precise negative results, and validation handoffs.

Do not dump gigantic generated traces into git. Record hashes, commands, summaries, schemas, and ignored artifact locations instead.

Update `docs/STATUS.md`, `docs/NEXT.md`, and `docs/DECISIONS.md` only when canonical state genuinely changes. Update `docs/progress.json` only when an auditable milestone changes state, then regenerate/check the progress outputs.

## 13. Closeout

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

There is no `MAIN-WRITE LEASE` or `MAIN-WRITE RELEASE` in the CAS workflow. Old lease comments are historical artifacts only.

## 14. Returning primary integrator handoff

When the primary integrator resumes after a direct-integration period, it should fetch latest `main`, inspect recent integration closeouts/receipts/handoffs, verify canonical docs, reconcile remaining prepared candidates, rerun broad validation before major architecture work, and resume primary ownership unless the user explicitly keeps direct-integration mode enabled.

Research branches are disposable. Evidence and canonical receipts are not.

## 15. North star

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
