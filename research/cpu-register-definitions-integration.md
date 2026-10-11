# Captured CPU register-definition integration

Hypothesis: the validated full GPR/ordinal/control capture can distinguish a live
load definition from an unrelated equal-valued read, without guessing the producer
from payload. Preserve the original adjacent protocol; add a separate bounded
captured-definition protocol for the same supported instruction/storage domain.

The source contract comes from retained 044/045 captures and the 047 decoy-register
composition finding. No new research lane/reference build. Each decoded load is a
new definition even when GPR values stay equal. ORI cuts an earlier definition
even when its resulting value is equal. Failed reads, phase boundaries and
unsupported transforms supply no positive witness. NOP and other-register loads
can preserve a definition only across fully checked captured GPR/control steps.
Retain at most one in-place XORI and its actual instruction identity.

This is compiler-time observed def-use, not an execution-attempt/sensor census,
ultimate storage ancestry, executable lifetime or native proof. Existing source
and report binding remain mandatory; all completeness flags stay false. No
ProgramMap/solver certificate promotion or protocol waiver is added.

Implemented separate `plaid-cpu-word-definitions-v0` inspect/verify APIs and CLI
commands. Both protocols share strict source/GPR/control/effect validation;
adjacent inspect/verify reject the definition protocol and vice versa. Captured
register definitions carry their original load/read identity through other-
register reads, NOP and at most one in-place XORI. Same-value reloads select the
new actual read, not the oldest equal tuple. ORI and failed-load cuts remain
conservative even when values match. Unsupported instruction/domain paths reject.

Saved authenticated copy capture yields four witnesses: prior adjacent phases
1/2 plus phase 3's t0 source read 14 at 0x1000 (equal decoy t1 read is 17 at
0x1100), and phase 5's source read 31 through a captured NOP. The original
adjacent protocol still yields only its two witnesses. The XORI capture retains
all four prior exact transforms. New wire hashes are
`5ac9116743cfb0a4eebd0375bc76e97d04fe14c3e8f40e3af1277c1735c1d382` and
`8bf5ad3a30d4b413af5319a691feac01c6a1725246edb1f65e836436078e091d`.
No reference rebuilt. The 047 finding motivates register-based identity; its
SP/RSP address and mutation stream is not consumed by this RDRAM protocol.

Ten focused Rust tests, CLI cross-protocol/source/report/input gates, fmt check
and strict locked workspace/all-target Clippy pass. The preceding byte-expression
commit's complete canonical checks pass at exact
`7009c308b2d1bf4370b2a8097e8df4a3dbd7e0e8` (Actions 38147761501).
Canonical CI runs the full workspace for this implementation; no repeated local
reference build or unrelated corpus replay. General capture/producer census,
storage ancestry, executable lifetime and whole-ROM/native closure remain OPEN.
