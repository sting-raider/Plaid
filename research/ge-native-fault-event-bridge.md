# Guest fault-event scheduling frontier

Research continuation of ADR-0300 and the prepared SDK current-thread binding.
No implementation or integration of a scheduler bridge is claimed here.

The current-thread binding advances the native stop from VI 1/fault 1/PC
808101e4 to VI 1/fault 1/PC 808102bc. That instruction reads MI_INTR_MASK at
a430000c. An ignored diagnostic implements that read from the existing SDK mask
state, then reaches fault 12 at 80810950 (VI 0 or 1 depending on host timing).
The diagnostic is not a production capability or acceptance receipt.

An extended natural trace on pinned ares
9408cb43d4948fc3ea6e152a307a34348df3fe04 confirms the next path:

- 23665386, PC 700101e4: current guest thread is 8005d640.
- 23665471, PC 70010384: Cause.ExcCode is 2; the ordinary fault path is taken.
- 23665488, PC 700106d8: the internal event sender has loaded queue 80063640
  from event-table cell 80066a70 for event offset 0x60 (fault event 12).
- 23665515, PC 70010754: it finds waiting guest thread 80060c90.
- 23665549, PC 70010910: the dispatcher pops that thread.
- 23665565, PC 70010950: it restores that thread's saved Status ff02.
- 23818945: the original engine fetch 7f000bd0 eventually succeeds after paging.

The native diagnostic follows the same lowered fault branch with Cause=8, but
the guest event-table lookup returns zero. The existing host runtime keeps
osSetEventMesg registrations and queue waiters in host structures. Its guest
kernel therefore cannot see the registration, wake the pager, or dispatch a
valid saved context. The native host thread with ID 5 is blocked on queue
80063640. This is an SDK interoperability gap rather than a different TLB
exception classification.

The retained reference's raw RDRAM globals can be stale while its D-cache holds
newer queue/event state. The addresses above come from executed GPR values;
raw RDRAM snapshots alone do not establish the guest CPU's queue contents.

Ignored evidence is under target/reference-handler/ (natural ares) and
target/receipts/ge-handler-trace/ (native block trace), in the prepared kernel
worktree. Native milestones retain stop JSON, RAM and PNG under
target/receipts/tlb-exception-controls/ge-kernel-first/ and ge-kernel-mi-trial/.

Next work must establish general, source-verified SDK event/dispatch interfaces
and a checked suspension/resumption of the native exception scope while the
pager thread runs. Handler state cannot remain globally active on another host
thread. Source identities, saved CPU state, context ownership/retirement,
Status/EPC transitions and final mapping guards need synthetic differential
tests and mutations. Neither an observed final page mapping nor a game-specific
queue address may substitute for executing the paging path.
