# Closed-world diagnostics v0

2026-10-08. Hypothesis: explicit missing-target and coverage obligations can reject
incomplete maps, while a finite synthetic CFG can close under recorded assumptions.

35 Rust tests pass. Solver tests include a CLOSED synthetic immutable loop, OPEN
whole-ROM status for that same loop, finite observations rejected as proofs, changed
prefix certificates rejected, missing decoded target blocks, deleted direct edges,
deleted JR sites, exceptions, executable writes, missing bytes, and empty maps.

The solver re-derives CFG facts from bytes and reports exact sites/evidence. Merged
unmapped-target diagnostics can be discharged only by a matching block identity;
the original unresolved fact remains in the report's discharged list.

Whole-ROM root/boot, exception/interrupt, DMA/overlay/relocation, executable-write,
RSP and R4300 execution-mode certificate verifiers are unimplemented and always
block whole-ROM closure. This is explicit missing implementation, not a compatibility
guess. A static declared scope excludes these effects and supports only a bounded
nontrapping integer/control subset. No emitted native artifact exists.
