# Unified ares cache/backing/fetch chronology

2026-10-08. Result: **PARTIAL**.

The current ares research hooks are strong enough to establish synchronous order
for the controlled cached paths but not to build a complete backing-to-fetch
history. At pin `9408cb43d4948fc3ea6e152a307a34348df3fe04`, a cached miss performs the
identity-RDRAM burst before the generated completed-fill callback, and the CPU
instruction tracer runs after `CPU::fetch` returns. A CACHE `fill` similarly
finishes its backing burst/fill before the completed-operation callback. A CACHE
hit writeback finishes the identity-RDRAM burst store (including hidden-RAM
update) before completed-operation observation.

A portable trace should still preserve one capture-wide monotonic event sequence.
The current artifacts serialize fetches, fills, CACHE operations and RDRAM bursts
as separate arrays. The executable spike `spikes/018-ares-cache-order/run.py`
shows that, absent cross-family order, a single RAM-read/fill/fetch triple admits
six total interleavings and a RAM-write/CACHE-op pair admits two. Repeated equal
payload/address fills provide no identity escape hatch. The pinned source reduces
these to one causal order, but requiring a future verifier to reconstruct raw
chronology from reference-specific source semantics is avoidable and brittle.

More importantly, a shared ordinal is insufficient by itself. Spike 015 ends with
an uncached instruction fetch from `0xffffffffa0004000`. The pinned `CPU::fetch`
uses `busRead<Word>` for that path, eventually reaching the ordinary identity
`RDRAM::Writable::read<Word>`. Spike 016's actual-RAM sensor instruments only
`readBurst` and `writeBurst`; therefore the uncached fetch has no actual RAM
transaction observation to join. Current state equality and the returned word are
useful behavior checks, not byte-origin provenance.

Local deterministic model result SHA-256:
`5246474a8eda3d950d3d5212740c0676213d97457700e66e049b2be142fd4940`.
Model source SHA-256:
`a1164d2e7a4adf1ce9f79d0f5c0d4936c5a8658719a6da168e81ccfc28f61862`.
The source guard SHA-256 is
`512a642d01ac1c7d455170f21c6e98515116ee66685a335ede0ed09ec6bb09f4`.

The worker environment could not clone/build the full pinned reference because no
`.refs/ares` checkout was mounted and direct GitHub DNS was unavailable. The new
source guard was syntax-checked but not executed against a local pin here. Full
reference neutrality remains supported only by the already committed spike-015/
016 plain/traced/repeated checks; no new neutrality claim is made for a unified
sensor implementation.

Recommendation: **INVESTIGATE**. Add a capture-wide monotonic ordinal and an
actual successful identity-RDRAM ordinary read/write witness, then rerun the
existing cache outcome/burst/boundary fixtures before any ProgramMap lifetime
join. Keep translated/degraded accesses, resets/restores, CPU/PI copies, general
stores and other requestors outside the certificate until separately covered.
