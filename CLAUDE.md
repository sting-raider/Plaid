# CLAUDE.md

**Read [`AGENTS.md`](AGENTS.md) first and follow it.** It is the single source of truth
for every agent working on Plaid (Claude, Codex, or anything else). This file only adds
a short orientation; where they disagree, `AGENTS.md` wins.

- Contributing from outside this machine/team (fork, PR, no push access)?
  Read [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md).
- Parallel / direct-integration workers: also read [`ORCHESTRATION.md`](ORCHESTRATION.md).

## Orientation in five minutes

1. What Plaid is and how far each game gets: `README.md`, `docs/REPORT.md`, then `docs/STATUS.md`.
2. What to do next: the newest section at the top of `docs/NEXT.md`.
3. Why things are the way they are: `docs/DECISIONS.md` (ADRs, newest at the bottom;
   grep for `ADR-NNNN`).
4. Build and CLI details: `docs/DEVELOPMENT.md`. Code map: `docs/ARCHITECTURE.md`.
5. Check your setup and run the gate: `python scripts/gate.py --doctor`, then
   `python scripts/gate.py` (add `--roms <dir>` for the game controls).

## Things that bite

- Never commit ROMs, saves, captures or other game data (`.gitignore` covers the usual
  extensions; check `git status` anyway).
- Native game runs: set `SDL_AUDIODRIVER=dummy` and keep the window visible.
  `scripts/gate.py` does both.
- Everything runs natively on Windows and Linux; no supported path needs WSL (ADR-0295).
- In git worktrees, `.refs`, `target/rt64-shim/Release` and `target/native-slice/oracle`
  may be junctions into the main checkout. Never delete them recursively and never
  `git worktree remove --force` a worktree that has them.
- Land with a plain fast-forward push after a full gate on the exact tree; never
  `--force` or `--force-with-lease` (see `AGENTS.md`, "exact-head CAS").
- Do not edit `docs/REPORT.md`'s progress tables; the maintainer updates them after landings.
- No game-specific hacks: a fix must be a general capability with a deterministic test.
