# Explicit scalar RSP actors feed executable backing

Raw v10 connects exact executed-code and rooted scalar operand facts to direct
SB/SH/SW method scopes, their completed DMEM byte effects and shared SP writers.
The existing store-lane verifier is reused. Method/instruction/read/root/effect
identities remain separate; ownership is not inferred from timing or equal bits.
Scope zero means an external/opaque mutation and always cuts ancestry. Even an
equal external write inside a method interval cannot borrow that method's writer.

`test_consumer.py` exercises ORI -> scoped SW -> DMEM -> CPU executable backing,
fresh writer/register-definition identity, exact lane/value/method/owner checks,
missing/reused/incomplete scopes, unowned equal effects and legacy rejection.
Both consumers and independent graph/digest replay agree. PI attribution remains
zero for computed stores: observed writer compatibility is not ultimate ROM origin.
`test_prepare.py` checks only the three real store method anchors and unchanged
optional Word reads. `run.py --verify-existing` rechecks the complete actual pin
controls, including all full machine/backing states and unchanged repeat output.

The reference graph has 360 records/40 checkpoints, 14 opaque operand roots,
42 performed instructions, 20 scalar definitions and two actual scoped SW calls/
eight completed byte effects. The portable original synthetic observations also
replay through the shared Rust kernel; code-byte origins in that projection are
unknown. Complete reference captures, binaries, source stamps and receipts remain
ignored and separately authenticated. No game assets or upstream code are imported.

Spike057 `--history storage-sp-stores` selects the optional raw boot recipe. The
initial operand-root adapter still rejects later undeclared task/PC/GPR reentry.
General/vector producers, task/control/reset, DMA/RAM/computed-origin composition,
writer/backend census, hardware, lifetimes and whole-ROM/native remain OPEN.
All broad certification flags stay false; no native lowering or runtime fallback.
