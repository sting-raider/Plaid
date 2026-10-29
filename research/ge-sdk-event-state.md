# Source-bound SDK event and empty-queue state

ADR-0304 follows the MI mask interface in ADR-0303. The lowered guest fault
sender previously read a null event-queue pointer because osSetEventMesg kept
its registration only in the host runtime. Host-created message queues also
used null heads instead of the SDK's thread-tail sentinel.

Retain typed EventStateTable/ThreadTail bindings by exact CodeAddress. Only the
corresponding osSetEventMesg/osCreateMesgQueue ABI, a complete source extent and
an aligned bounded direct RDRAM address are accepted. Declaration restoration
still requires the exact original hash, evidence, entry, ABI and extent. Merge
conflicts refuse. Legacy maps omit the optional field and retain their scope.

The existing SDK source wrapper verifies and pins the full function before
registering either interface; mapped sources retain their mapping/content and
frame guards. The runtime refuses conflicting physical bindings and malformed
tail nodes. First event-table registration preflights the complete backfill
before publishing the binding. Event registrations write their guest pair
atomically. Host delivery reads the bound guest table, including guest updates
and a null queue disabling delivery. Queue creation publishes the source-bound
sentinel in both empty heads. It does not publish blocked-thread lists yet.

A synthetic SDK constructor and event-registration body run on pinned ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. Their ABI-visible memory results match
native host replacement. Further native contracts cover guest event writes,
disable, late binding, conflicting/malformed globals, atomic failure against a
pinned code range and corruption before the first source-bound registration.
Three mutations remove publication, substitute null heads and ignore guest
table writes; each fails. Core/CLI tests cover roundtrip, legacy omission,
extent/ABI/address checks, duplicate declarations, merge conflict and exact
original-evidence restoration/refusal. No SDK instruction body is added to git.

Fresh GoldenEye remains VI1/fault12/PC80810950. RDRAM readback now shows fault
event 12 naming queue80063640/message10, both queue heads naming sentinel
80027720, and validCount=1. These are diagnostic observations, not production
constants. Host thread5 remains blocked on that queue: its waiter node is not
in the guest queue, so the lowered sender cannot enqueue it for guest dispatch.
This narrows the remaining bridge to waiter/run-queue publication and checked
exception-scope suspension/resumption. No logo/title or framebuffer claim.

The ignored stop JSON, RAM and PNG are under
target/receipts/tlb-exception-controls/ge0304-ge-final/. Exact final-tree gate
and control receipts are retained under target/receipts/sdk-events-exact/.
