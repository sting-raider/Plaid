# Distance to no-assumption CLOSED: generated chart and ledger

Docs and tooling only: `docs/`, `README.md`, `tools/progress.py`. No crate,
runtime or solver change, so no compiler transformation needs a verifier.

**What it adds:**
- `docs/assumptions.json` (schema version 1): per-ROM whole-ROM blockers by
  class and the scoped results, the 15 assumptions the SM64 `--address-taken`
  result relies on (run-time check and fault code, state, what retires it),
  and the hand inputs outside the solver.
- `tools/progress.py` renders `docs/assumptions.svg` and the README block
  between `<!-- assumptions:begin -->` and `<!-- assumptions:end -->`.
  `--check` fails on drift in both. It also rejects a missing singleton
  class or an unknown assumption state.
- README: the status footnote now says what the VR4300 and RSP percentages
  do and do not mean (the unfilled VR4300 cells are COP0, TLB, `ERET`,
  `SYSCALL` and `CACHE`), and the About paragraph and OoT row match the
  current state (ADR-0176/0177/0178/0179).

**Data:** measured 2026-10-16 with `plaid solve <rom> <map> [scope]` on local
inputs and copied from the session brief, not re-measured here. Per-ROM class
counts sum to the measured totals (4,820 / 3,105 / 14,642), checked when the
file was written. Assumptions retired: 0/15. Indirect sites closed without
assumptions: SM64 1 of 4,385, OoT 2 of 2,562, OoT + overlays 6 of 13,310.
OoT's `--guarded-ram` assumption count was not given, so it is `null` and
omitted from the table.

Gate on the exact tree: see the closeout comment on issue #4. ROMs, maps and
game data stay local. Actions were not used. `native_complete` stays false.
