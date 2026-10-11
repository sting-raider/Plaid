# Primary actual CPU / SP producer reconciliation

Hypothesis: actual decoder-boundary instruction/GPR/FPR context can explain a
completed CPU SP Word effect without same-PC/value matching or manually supplied
operand metadata. Physical bank/offset and guest-byte replay remain independent
requirements; an unscoped write cannot inherit an instruction source.

Reviewed all fixture/verifier files and the closeout for
`research/cpu-sp-producer-context-gpt56sol` at
`736f1406a729be51422f247260f47ef5412593e8`. Authenticated Actions `37915925049`
artifact SHA-256 `f41331e4cbf7590c8b598c2385e573da49296f963da8fd0b5635f6bc83b7d725`
and reproduced six attributed controls. Three additional forged histories still
passed its verifier: changing encoded SWC1 source selector without operand
metadata agreement, labeling a DMEM address as IMEM, and setting offset 4096.
The branch also supplies context from the caller and compares only sensor-
disabled/enabled/repeated selected facts. Reject that verifier as written.

The primary fixture retains its seven CPU cases and direct out-of-context decoy,
but uses the guarded actual CPU decoder callback from spike-044 and actual
completed SP Word callback from spike-039. All 32 GPR/FPR bits and FR/CU1 state
are captured at actual instruction begin/end. The verifier derives register
selection/effective address from the captured word, validates exact physical
bank and offset, requires one completed effect for each supported successful
store and none for denied SWC1, and replays guest-visible bytes.

The first primary reference run correctly failed the initial snapshot gate.
The fixture copied `imem.data` as though it were guest byte order. At this pin,
generic `Memory::Writable` uses host-order storage with byte-index XOR on little-
endian hosts; RSP's specialized DMEM storage has a different implementation.
The IMEM host snapshot was `a3 a2 a1 a0 ...`, while guest initialization was
`a0 a1 a2 a3 ...`. Corrected capture through `imem.read<Byte>` and retained an
independent host-order forgery regression. The gate was not relaxed.

Fresh corrected reproduction at unchanged ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04` passes eight original/disabled/enabled/
repeated checkpoints, including all captured FPR bits and prior reported CPU/
RSP/memory/clock/exception state. Twenty-one records retain six attributed
effects, one unattributed effect and one denied-CU1 fault without a sink.
Sixteen measured forged histories fail; eight independent synthetic regressions
pass. Schema-0 result SHA-256:
`2cadac7ab077a2575d19360743161976789a72fd3a00173fda0f891f14792864`.
Full locked core, fmt and strict workspace Clippy pass.

SB +1 observes this pin's widened full Word `0x77880000`, not a nominal isolated
byte. FR-sensitive SWC1 source selection preserves paired-even high vs named
low halves. Same-value SWs have distinct actual decoded contexts; the direct
same-value CPU write stays unattributed. These facts do not establish N64-wide
hardware truth or ultimate source ancestry. No complete attempt/writer census,
reentrant/asynchronous semantics, all store families, executable lifetime or
production/native producer certificate is claimed. The reported checkpoint is
not every emulator state bit. The bounded branch fixture/verifier is superseded;
broader obligations remain open.

Only project-owned ISC fixture/observer code is retained. Guarded generated ares
shadows and full core ISC / SLJIT BSD notices remain ignored; no upstream
implementation, ROM or firmware data enters production or Git.
