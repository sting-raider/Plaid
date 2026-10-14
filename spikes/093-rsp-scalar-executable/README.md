# Exact executable reads feed rooted RSP scalar producers

Reuse the canonical ORI/ADDU expression and transition verifier. Raw v9 requires
complete before/after GPR snapshots and explicit opaque operand roots. Definitions
link to the exact performed begin/end/read identities in the existing SP/PI graph.
Equal redefinitions select fresh contexts; equal root snapshots still cut old
parents. Unsupported instructions cut held scalar candidates and remain opaque.
Register roots do not rewrite captured executable-byte parents.

`test_consumer.py` verifies both existing consumers and independent replay: ROM/
PI/RAM/IMEM code -> ORI -> ADDU, repeated definitions, root cuts, malformed roots/
snapshots, foreign register changes, forged/deleted reports and legacy rejection.
`verify.py` independently computes every root/transition/definition commitment.
`run.py` exercises actual pinned ORI/ADDU/read/root controls and full baseline/
disabled/enabled/repeat machine/backing checkpoints. Use `--verify-existing` to
reuse authenticated artifacts. The portable original synthetic regression under
`crates/plaid-core/tests/fixtures/` checks actual snapshots through the shared
Rust engine and records the parent source digest. Its executable byte origins
are explicitly unknown; it is not a substitute for the complete native capture.

`boot_driver.cpp` / `observer.hpp` select spike057 `--history storage-sp-operands`.
The initial boot adapter emits one opaque initial operand root. A later undeclared
PC/GPR reentry fails; guest task/control/reset roots remain to be composed.
Captures are finite, hardware consensus is unproven, and all mutation/lifetime/
whole-ROM/native completion flags remain false. No native lowering is added.
