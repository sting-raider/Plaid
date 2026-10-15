# Primary integration: function-pointer calls through memory stay open

Base: 48f9427. Milestone: 5 (OoT). Worker: Claude side session started by
the co-integrator, user-authorized on main, running autonomously.

ADR-0142 records a negative result, with the details in
`research/function-pointer-points-to.md`:
- All 21 OoT function-pointer `jalr` sites take their target from memory.
- A sound field-store census would need whole-program store points-to.
- A runtime-checked guess cannot count as closure.
- Store-guarded fixed-address cells, the only sound extension measured,
  would close 1 of 22 sites.

No production code, tests or lowering changed, so spike096 and the Rust
gate are unaffected. Local OoT reproduction on this base: 59 identified
functions; 7684 blocks, 698 indirect sites and 29 guarded blockers,
unchanged. The ROM, loads declaration and maps stay under ignored `target/`.

Local checks on the exact tree: `tools/progress.py --check`. No Actions.
`native_complete` stays false.
