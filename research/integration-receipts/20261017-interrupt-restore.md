# IE restore prerequisite (ADR-0193)

Base main: `37399f325328f63aed3c38e48df6b9ba86fd6e77`.

`__osRestoreInt(0)` must preserve an already-enabled IE bit. The runtime
assigned the argument instead and disabled interrupts. Restore now ORs the
valid saved IE bit into the current Boolean; the existing enabled-state
delivery/preemption path remains in use. This fixes the IE operation only.
It does not add a full CP0 Status model or admit `__osGetSR`.

The new retained synthetic program contains independently assembled reference
MFC0/bit operations/MTC0 routines. Native lowering replaces those declared
function boundaries with the host runtime; the pinned ares interpreter alone
executes the reference instructions. There is no game input, SDK code copy or
runtime instruction decoder. The oracle revision and exact hashes of both
the native-slice driver and its common fixture are checked.

The test aligns initial IE with RestoreInt(1), then checks enabled-zero,
disabled-zero, nested saved values and repeated enable. Before the fix, its
eight IE observations were `[1,0,0,0,1,0,1,0]`, while ares produced
`[1,0,0,1,1,0,1,0]`. The entire 256-byte retained RAM slice otherwise agreed.
The passing test compares that complete slice, including saved callee GPR
canaries, SP/GP/FP and HI/LO. Native normal exit/fault 0 and the oracle's exact
exit PC/no-exception outcome are required. Restore's unspecified void return
and caller-clobbered temporaries are not compared as ABI-preserved outputs.

A deterministic C fixture injects SP event arrival into the existing host
runtime. RestoreInt(0) in an enabled context must deliver its queued message;
in a disabled context the message must remain pending until RestoreInt(1).
It checks queue counts/message writes and fault 0 without host timing or a
game window. This tests the runtime's IE gate, not full hardware interrupt,
mask, acknowledgment or exception equivalence.

The red focused invocation took 6.04 s and the green repeat 4.51 s on this
machine, including native compilation/WSL startup. This is a correctness
measurement, not an optimization claim. The full pre-change runtime suite's
last accepted time was 161.904 s; the final integration gate and added-test
cost are recorded in ignored `target/interrupt-restore/` evidence and issue #4.
The first complete post-fix suite passed in 216.385 s. It ran before the
additional deterministic C event fixture was added; that fixture separately
passed with the differential. The final committed-tree suite repeats both.
These whole-suite runs were not a controlled performance comparison.

Acceptance includes the focused differential and the complete existing
runtime suite, retaining scheduling/event, audio, RCP, overlay/slot and native
RSP contracts. No new interrupt timing, pending-device or thread Status
equivalence claim is made. Full mask bindings, saved/live Status, idle policy,
PRENMI, CU1/FR and event bypasses remain in `research/status-interrupt-model.md`.
BK stays scoped OPEN/1; no native game/audio run is attributed to this fix.
