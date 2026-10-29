# Native SDK waiter and yield-context publication

ADR-0305 follows the source-bound event/tail interfaces in ADR-0304. A host
thread blocked in a queue previously had no guest waiter node. The lowered
fault sender therefore enqueued a message but could not wake the pager.

When the source-bound SDK tail is known, native blocking, wakeup, blocked
priority changes, stop and destruction publish the corresponding guest wait
list. Receive and full-send lists remain separate. Nodes are ordered by signed
priority and enqueue sequence; a changed priority reenqueues behind equal
priorities, while an unchanged priority preserves the existing sequence.
RUNNABLE/STOPPED/RUNNING state halfwords follow the host handoffs. The existing host scheduler remains the owner of its continuations.
This step does not import arbitrary guest list edits into that scheduler.

All head/node destination ranges are checked before the first guest byte or
source witness changes. The lowerer's existing write permission check is
separated from witness revocation so multi-range SDK writes can preflight.
Actual stores still use the same protected runtime writer. An invalid later
node cannot leave the head changed. Host scheduler state on a terminal refusal
is not a recoverable transaction.

For a thread with the existing verified FR0 SDK Status profile, a bound tail
also enables publication of s0-s7, gp/sp/s8/ra and EPC. A thread using FP saves
FCSR (including FCC) and the six even FP pairs f20-f30. Caller-saved GPR slots,
HI/LO and f0-f18 remain untouched. Context stores are preflighted before any
saved Status/MI word changes. FR1, FP without CU1 and protected destinations
refuse. Legacy unprofiled threads retain their prior context scope.

The saved return PC and SP describe the native public ABI continuation, not
libultra's private stack frame inside osRecvMesg. Consequently these bytes do
not authorize jumping directly to that PC or skipping a pending host receive.
A foreign guest ERET still refuses. A future bridge must resume the exact
owned host continuation and preserve its exception/context generation and
native frame guards. Safepoint handoffs are likewise not proven guest SDK
continuations merely because these fields are present.

The store layout was established by compiler-time inspection of user-supplied
SDK source bytes and tested using independent synthetic architectural SD/SW,
SDC1 and CFC1 programs on pinned ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. Entire synthetic TCB buffers, including
untouched bytes, agree for FP and non-FP cases. Existing Status/MI algebra
retains its separate 256-case reference coverage. No SDK body, ROM byte or
copyrighted trace is committed. N64ModernRuntime's GPL header was inspected
for context, but its host-extended structure was unsuitable; no code was reused.

runtime/test_kernel_waiters.py also exercises real host blocking/wakeup,
priority/FIFO, equal-priority reenqueuing, both queue sides, stop/destruction,
later-node atomic refusal and FR/CU1/pinned-context refusal. Seven mutations
remove or corrupt ordering, removal, preflight, EPC, FCC, same-priority no-op
and runnable state; each is detected.

Fresh GoldenEye advances from VI1/fault12/PC80810950 to
VI1/fault12/PC80810a7c, the checked foreign ERET. RDRAM now names pager80060c90
as the guest running thread; the fault queue was popped to sentinel80027720,
and its saved Status/EPC are ff02/70004fd0. These are diagnostic observations,
not production constants. The host pager remains blocked until the checked
handoff bridge exists. The framebuffer readback contains no logo/title.

Ignored stop JSON, RDRAM and PNG:
target/receipts/tlb-exception-controls/ge0305-ge-final/.
Exact-tree gate, fresh controls and artifact hashes:
target/receipts/sdk-waiters-exact/. Landing requires the full six-command gate,
six quiet 30-second controls, prescribed MP2 and OoT save-load controls and an
exact-parent plain fast-forward push. No RT64 bridge or patch changes.
