# MI interrupt-mask access from lowered guest code

ADR-0303 follows the source-bound current-thread publication in ADR-0302.
GoldenEye's general exception handler reads MI_INTR_MASK at a430000c, PC
808102bc. Before this change, the runtime's uncached I/O callback refuses that
register (VI0/fault1 in the ADR-0302 final run).

The pinned ares reference, 9408cb43d4948fc3ea6e152a307a34348df3fe04,
ares/n64/mi/io.cpp, reads six mask bits and applies six clear/set command pairs.
Set wins when both commands are present. The register mirrors every sixteen
bytes throughout the MI region. This is a project-owned implementation of the
register behavior, not copied upstream code; the reference is ISC licensed.

The runtime shares the value with its existing SDK mask/context operations.
Knowledge is tracked independently of CP0 Status: a source-verified SDK context
restore or complete mask update establishes all six bits, while a raw command
establishes only its touched bits. Reads refuse until all six are established.
Writes schedule reevaluation through the existing event model. This does not
add raw MI interrupt-line state or change the existing Cause event abstraction.
Other MI registers and unsupported access widths retain their refusals.

The retained synthetic contract compares 1024 mask/command/mirror combinations
against actual MIPS loads/stores on pinned ares. Native accesses use the normal
lowered memory helpers and runtime I/O callback. Unknown/partial knowledge,
full initialization by raw commands, SDK restore, unsupported widths and
preservation of CP0 Status/pending events are checked separately. Four mutations
remove setting, reverse simultaneous-command priority, bypass knowledge and
restrict mirroring; each is killed. Synthetic output and reference metadata are
retained under ignored target/runtime-test/mi-differential.json.

The native diagnostic advances GoldenEye to VI1/fault12/PC80810950, in the guest
dispatcher's Status restoration. Its source-bound current-thread publication
remains active. Natural reference tracing already establishes that this path
wakes the pager through a fault-event queue before dispatch. The host SDK event
registration and queue/thread scheduling state are still invisible to that
guest path; see ge-native-fault-event-bridge.md. No logo/title or initialized
framebuffer is claimed. No mapping or guest context is preloaded.

Exact-tree gate, silent controls, stop JSON, RAM readbacks and PNGs are retained
under ignored target/receipts/mi-mask-exact/ and
target/receipts/tlb-exception-controls/ge0303-* in the implementation checkout.
