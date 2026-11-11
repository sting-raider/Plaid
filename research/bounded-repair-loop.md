# Bounded native repair loop (step 2b, ADR-0315)

Base: `ceba27e0fcfa367ccab67c104e931b64ef74625d` (step 2a).
Claim: issue #4, worker `bounded-repair-loop-step2b`.

Hypothesis: a bounded orchestration loop can consume its own native fault
observations through the existing admission interface without weakening native
dispatch or promoting observed coverage into executable completeness.

`scripts/native.py` now permits four total build/validation rounds. Each new
fault-3/15 record becomes the next deterministic generation, with the first
round's refined loads retained. Success requires exit zero and a valid fault-zero
stop; other faults, missing stops/captures, repeated payload hashes and the cap
reject acceptance. A capture's fault/site/target/VI must match its stop. Each
round prints its number, fault, PC, optional hash and reason. No output-directory
scan, automatic `--deep`, runtime guest execution or frontend work is introduced.

The four-round bound includes the initial build, so at most three new records
are admitted automatically. The final failing capture is still retained. Explicit
`--repair-record` inputs precede new generations and seed duplicate detection.
`--deep` uses the same loop with the full analysis-time replay budget, regardless
of an inherited short-budget environment variable.

Deterministic evidence (synthetic bytes only):

- Policy: two-round convergence, multiple ordered admissions, equal-payload
  no-progress stopping despite differing stop metadata, four unique faults at
  the cap, cap one, explicit input duplicates, missing capture, faults 4/11/17,
  missing/malformed stop, Boolean fault and nonzero process exit refusal.
- CLI: default short budget survives both rounds; explicit deep removes the
  inherited short budget; refined baseline loads and admitted records survive.
- Native integration: actual CLI discovery, solve, lowering, host compilation,
  execution, runtime capture, SHA-256 conversion, admission and rebuild; fault
  sequence `3 -> 0`. Complete GPR/HI/LO/PC and unchanged RAM are asserted, except
  for the intended final v0 value. Both manifests remain incomplete.
- Mutation: reversing the repeated-hash condition was rejected by the focused
  contract in 0.656 s; the source was restored before the landing gate.
- ADR-0314's retained runtime contracts continue checking whole-window and late
  content mismatches, alias/generation/write refusals and unresolved direct edges.

The exact-tree gate consists of `cargo fmt --all -- --check`,
`cargo clippy --locked --workspace --all-targets -- -D warnings`,
`cargo test --locked --workspace`, `python scripts/test_cli.py` and
`python runtime/test_runtime.py`, with `SDL_AUDIODRIVER=dummy`. Per-command outcomes
and wall-clock times are recorded in the landing commit message and ignored
`target/receipts/bounded-repair-loop/` output so this documentation can itself
belong to the exact tree that was validated. The available installed Rust tools
were added to the command PATH; the existing pinned reference checkout is linked
read-only in use through the ignored `.refs` junction. No upstream code is copied.

Paper Mario cold loop versus current deep build: **not run**. Resident Evil 2
end-to-end stop sequence: **not run**. No ROM folder or ROM paths were configured,
and the ROMs were unavailable locally. The user explicitly requested no disk
search and skipped both measurements. No game timings, game stop sequences,
gameplay progress, native-complete claim or performance improvement is inferred
from synthetic convergence. Broad observed windows may contain mutable data
and still stop conservatively with fault 17; their size/guards are unchanged.
