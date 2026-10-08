# RAM mapping/degradation/failure policy boundaries

2026-10-08. Hypothesis: the identity-only RAM burst policy must not manufacture a
backing witness for remapped/degraded/failed accesses, even when returned bytes
match some backing bytes. The pinned RDRAM::Writable::translate selects enabled
chips through RI state/device IDs, while degrade can clear bits according to
current calibration and deterministic entropy. Failed mappings acknowledge RI
errors and return zero words; identity out-of-bounds reads return zeros without
a successful transaction. These paths are separate from normal direct reads.

Spike 017 uses direct component calls with declared chip/RI state, executing no
guest instructions. Bus address zero maps to backing chip one at 0x200000 and
stores through translation. Reads check reliable, zero and deterministic partial
degradation; disabled chip/inactive RI/out-of-bounds access returns zero. All
remain outside the identity-only witness policy. Three successful identity
transactions remain: a 32-byte read/store and 16-byte read. Host setup supplies
requestor arguments; they are no independent CPU/caller certificate.

A separately built baseline without the header callback matches instrumented
plain/traced/repeated returned words, GPR/HI/LO/PC/Count, RI error and complete RAM/
hidden-memory hashes. Repeated JSON is exact; degraded words have fixed goldens.
Count=0, RI error=1. RAM SHA-256:
`b34ba68aca7b98053ef23b552d335c428b1fb33b19972b1bfb2e4cbeaf0d515c`.
Hidden-memory SHA-256:
`68510b252b438d53c7be9eb09f1d519e8d0f3193d0f0a1d942852d282070cf6e`.
Both recompilers are disabled. The observer adds no guest read/translation/random
call or clock; it keeps unsupported results unclaimed rather than guessing their
backing from addresses/equality.

This validates the declared direct-component boundary cases, not hardware boot,
guest retirement, reset/restore, ordinary/ebus stores or general bus policy.
Unified transaction/fill/cache-operation/fetch/copy ordering and source/lifetime
handling remain separate work. No production image, generation or native
artifact is promoted.
