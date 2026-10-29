# Guest SDK current-thread state

ADR-0302 follows ADRs 0300/0301. Exact-tree validation receipts are retained
under ignored target/receipts/sdk-running-exact/.

The native guest general exception handler reaches PC 808101e4 with k0=0.
Its preceding load obtains the SDK current-thread pointer from guest RAM. The
host scheduler maintains that pointer only in host structures. Existing
signature identification already supplies the symbolic `__osRunningThread`
binding consistently across the SDK functions; declaration ingestion discards
it. Publishing an observed game address directly would conceal this general
interface gap.

The candidate carries per-source current-thread bindings into the ProgramMap.
Bindings require a supported SDK ABI, a declared source extent and aligned
direct-mapped RDRAM. Conflicting map merges refuse. A fixed host boundary checks
and pins its complete source before registering the cell; mapped boundaries
retain their existing complete source/mapping guards and pins. Registration
refuses conflicting physical cells. Host scheduler handoffs publish the current
guest thread, including preemption, blocking, wakeup and stop/resume. No guest
context or page mapping is preloaded.

The first synthetic native test observes boot, first start, preemption, blocked
receive, wakeup and stop handoffs directly from guest code. Core tests cover
roundtrip, legacy omission, malformed bindings and merge conflicts. Single/multipart handoffs agree; removing publication fails the guest log, and
source corruption refuses before registration. GoldenEye advances to VI 1,
fault 1, PC 808102bc, a raw MI interrupt-mask read. The published thread
8005d640 matches the retained pinned-ares trace at the same handler point.
The six-command gate passes on the candidate. Canonical acceptance, control
runs and integration are recorded in the exact-tree landing receipt.

The bind-runtime-globals command restores this optional metadata from the
exact original declaration evidence, without repeating executable discovery.
ROM identity, declaration hash, per-entry source identity, ABI, extent and
existing-binding consistency are checked. CLI tests reject stale/foreign
declarations and missing or altered entries. This is motivated by repeated
control discovery exceeding several minutes; it does not import new targets
or waive source replay, solving or native source guards.
