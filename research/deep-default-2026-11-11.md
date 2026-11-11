# Restore the default full-budget native build

Claim: worker t3-59c97f9f, base `4e9ddde58558b072275e65db85c6cfbf4baed2d9`.
Hypothesis: the launcher command must choose the full observation budget and
a single validation, because the shorter repair loop fails Paper Mario's
second solve while a deep build completes. Preserve bounded repair as opt-in.

Baseline: `research/repair-loop-measurements-2026-11-11.md` reports a cold
Paper Mario short-budget repair failure in 422.465 s and a successful full
budget run in 655.551 s, both including 60-second validation and a prepared
toolchain; these are different outcomes and not an equivalent speed comparison.

First local attempt: 595.673 s, exit 1 at RT64 link, no game run. The
initial work-directory bridge DLL was stale and missed `plaid_gfx_connected`,
`plaid_gfx_input_player` and `plaid_gfx_window_options`. The retry uses the
engine RT64 bridge from a checkout at the same base, whose bridge source blob
`e416c3de8096367df6fcb3ea1d168ee12a335e7d` matches this tree; the replacement
DLL SHA-256 is `d76141b5c2c05549dda1df3c56408d72a98adfdf781bdcd6a44423d1c924d2d9`.
It exports all three symbols. The retry reuses the first attempt's analysis and
object caches; the two wall times must not be compared as equivalent cold runs.
The CLI synthetic suite passed in 94.069 s with overlapping game analysis.

Retry result: exact checkout command `python -B -u scripts/native.py <Paper
Mario ROM> --rt64 --seconds 30`, fresh `PLAID_WORK_DIR` initially and retained
caches for the retry, `SDL_AUDIODRIVER=dummy`, `PLAID_PIF_ROM` unset, visible
window. Exit 0, 83.019 s wall (31.126 s validation), time-limit stop at VI 1798,
fault 0, PC 00000000. The residual solve closed with 10 residual sites; the
manifest remains `native_complete: false`. Initial failed plus retry elapsed
678.692 s including initial release build, stale DLL failure and shared CLI
validation; this is not a controlled comparison with the historical 655.551 s
prepared-toolchain, 60 s deep measurement. The prior short-budget default failed
in 422.465 s; the new default completed, so it is not a same-outcome speedup.
