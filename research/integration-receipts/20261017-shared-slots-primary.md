# Shared executable slot integration (ADR-0185)

Milestone: 5. Prepared base: `583f07c38fddf056f2bf58eefb198b0292d959c9`.
Recovered the interrupted Claude candidate and the subsequent Codex hardening.
Compiler changes are isolated from the graphics/runtime candidate in a separate
checkout; no game-derived files are tracked.

The public-CLI contract runs two synthetic files in one slot and matches the
entire pinned-ares state through 7 / 11 / 7. Tampered text and two identical
alternates fault. Slot mappings, inferred text bounds and content identity are
recomputed, including forged-metadata negatives. The native verifier cannot
omit executable bytes; a deliberate inverted comparison was caught by its test.

Local gate on this compiler tree: formatting, strict workspace/all-target
Clippy, workspace tests, CLI tests and runtime tests PASS. The gate took
250.33 seconds in the isolated checkout, including recompilation for its new
source path. Runtime tests include the slot differential and the existing
every-byte overlay-verifier negatives. Spike096 passed on the same compiler
changes before isolation; the slot oracle is ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04` with recompilers disabled.
Progress record, generation and check PASS.

Local F-Zero X measurement: 27,621 blocks, 1,974 indirect sites, CLOSED with
zero blockers and 14 assumptions in the address-taken scope. Guarded RAM without
address-taken has 44 blockers; whole-ROM without assumptions has 2,995.
Before: 11,398 blocks and 20 address-taken blockers (ADR-0184).
These are conditional closure results, not native-complete acceptance.

The separate runtime candidate supplies raw handle PI DMA, an empty-tile RT64
correction and a native graphics-RSP bridge. Its visible game results are not
used as the validation gate for this compiler-only commit.

Retained local logs: `target/session-resume/slots-{fmt,clippy,tests,cli,runtime}.log`.
No Actions. No interpreter/JIT fallback. No new copied upstream code.
