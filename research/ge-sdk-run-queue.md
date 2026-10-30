# Source-bound SDK runnable queues and call-slot arguments

ADR-0306 completes the publication side needed before a checked native guest
exception handoff. ADR-0305 published waiters and saved callee context, but
native runnable threads still had no authoritative guest run-queue chain.
The source identifier also omitted scalar addresses completed in a direct
JAL delay slot, including the dispatcher's queue argument.

Scalar binding recovery now accepts an ADDIU/ORI into a0-a3 in the final slot
of a direct JAL when the preceding LUI value survives. JAL cannot use ra as
the base. The pair must be in the declared function extent, have no intervening
clobber/diversion, and admit no alternate entry into its interior. JALR,
branch slots, a LUI in a transfer slot and a low instruction after return are
not covered. All matching signature variants must still agree. There is no
runtime instruction decoder or special game address.

64 Rust positive combinations plus control/clobber/entry/extent negatives
cover the dataflow. runtime/test_argument_delay.py independently delivers 32
synthetic call arguments on pinned ares
9408cb43d4948fc3ea6e152a307a34348df3fe04: a0-a3, ADDIU/ORI and four signed-low
boundaries. The recovered binding equals the executed callee GPR and store;
exit PC and all 64 observed RAM words agree. This is a binding proof at the
call boundary, not permission to retain caller-saved values after the call.

A typed RunQueue binding follows the existing matching SDK ABI, full source
extent, direct-RDRAM, source guard and native pin rules. Original declaration
restoration keeps its exact declaration hash. Fresh identification/discovery
is used for game validation; new metadata is not attached to an old declaration.
The lowerer registers this interface before calling the verified public ABI.

With a verified tail and run-queue head, host-owned runnable threads publish
signed-priority/FIFO links, queue pointers and RUNNABLE state. Start, handoff,
yield, wakeup, changed priority, stop and destruction update membership.
Unchanged priority retains sequence. Existing preemption policy is preserved.
A handoff removes the selected thread before publishing RUNNING state. No
arbitrary guest list edit is imported into the host scheduler.

Queue publication preflights both waiting and runnable lists before writing
either list. Failed later-node checks cannot publish an earlier head. Late
registration supports either binding order and checks head/node/running-state
ranges before committing a new binding. Physical aliases are accepted;
conflicting heads and overlap with the tail refuse. These checks cover queue
publication; a terminal refusal is not a rollback of the whole preceding SDK
call or host scheduler transition.

runtime/test_run_queue.py exercises actual host threads and constructed failure
states, including priority/FIFO, same-priority ordering, two-list wake refusal,
late registration, source corruption, alias/conflict and protected nodes. Six
mutations are detected. The retained waiter/context suite detects all seven
mutations and retains its complete-buffer pinned-ares comparisons. Boundary
tests check the exact last valid event-table/tail/head placement and overflow
in both direct RAM aliases.

Fresh GoldenEye discovery retains 49,381 blocks, zero static blockers and six
residual sites. Six SDK source identities now declare the runnable head. The
visible silent stop remains VI1/fault12/PC80810a7c: the lowered dispatcher
selects the pager, but foreign ERET remains refused. The current VI backing
contains initialization noise, with no Rare/Nintendo logo or title verified.
The next step must authenticate the lowered restore entry and hand off to the
owned suspended host receive, preserving exception scope, context generation,
retirement and native frames. The public ABI EPC does not authorize skipping
that receive. TLB mappings must be produced by the pager, never injected.

Ignored stop JSON, RDRAM and framebuffer PNG:
target/receipts/tlb-exception-controls/ge0306-ge-final/.
Exact-tree six-command gate, fresh control receipts and input hashes:
target/receipts/sdk-run-queue-exact/.
The landing requires six quiet 30-second controls plus prescribed MP2 and
OoT save-load runs, all silent and visible. No RT64 bridge or patches changed.
