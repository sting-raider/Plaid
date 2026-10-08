# Actual accepted PI request and CPU callback scopes

Primary receipt, 2026-10-09. New worker PI research supports insertion identity,
explicit rejection/cancellation and keeping data movement separate from scheduled
status callbacks. The recovered actual write-only fixture reproduces locally with
its exact trace/result hashes. This follow-up additionally tests the read request
path and records explicit accepted-I/O and actual CPU dispatch scopes rather than
inferring them from the next common handler invocation.

`python spikes/035-ares-pi-queue-dispatch-context/run.py` passes at clean ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, WSL Ubuntu x64 G++ 15.2.
The optional shared builder retains original source operations, adds nullable
callbacks before/after the accepted PI length-write insertion/copy path, and
brackets the actual `CPU::synchronize` queue callback with an original local
scope. Object fields/layout stay unchanged. Queue identities remain external.
Generated upstream code/LICENSE, toy ROM and raw results stay ignored.

The five-case chronology has 2,222 records and five accepted requests:

- Write request 1 receives token 1, performs eight actual successful byte writes
  immediately, and later reaches the common status handler under that exact CPU
  dispatch scope.
- Write request 2/token 2 is canceled. A new read request 3/token 3 is dispatched
  under the read event class. The canceled write drains invalid with no callback.
- Two manually inserted write events/tokens 4 and 5 reach the CPU/status callback
  with request identity unbound. These are queue adversaries, not accepted PI I/O.
- After 512 canceled entries fill capacity, accepted write request 4 still performs
  eight actual successful byte writes despite insertion rejection. Draining those
  invalid entries produces no status callback; busy remains 1 at the checkpoint.
- Write request 5 performs eight byte writes and receives a queue token. Direct
  fixture invocation of `dmaFinished` has no CPU dispatch scope, so its request
  association remains unknown despite the busy/interrupt transition.

The four write requests produce 32 successful identity-RAM scalar effects. The
checker binds each effect to its actual attempt/return under the accepted call.
It does not claim canonical ROM origins here; that needs the separate PI half/
buffer witnesses. Six token/direction/request/type/byte forgeries fail. Valid
removals must be consumed by the immediate CPU dispatch after heap repair; a
stale removal context cannot name an unrelated later status call.

Original-source baseline, sensor-disabled and repeated enabled reported GPR/HI/LO/
PC/Count/exception, PI checkpoints, full RAM/hidden hashes and 6,152-byte queue size
agree. Final Count 643, exception 0, RAM SHA-256
`89d11d41813308236842b26e868c93434ff26513d09e1bdb8796a6e7daf5ecf5`,
hidden SHA-256
`bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8`.
Trace SHA-256:
`9d6f845713fe8a031d18475f4ecc76e0f8118a58b6ee6b4abdff4111e57a968a`.
Result SHA-256:
`36e508a15f180c881ccfede05a0f93a7f80ee358424bf1eb9a18bedb6c0a938b`.
New and prior PI/shared sensor generation/reuse tests also pass.

This executes actual PI I/O methods, queue and CPU synchronization components,
without CPU instruction execution of guest MMIO. It proves finite request-to-
status dispatch identity under this capture, not hardware timing or the time of
byte transfer. Arbitrary boot joins, reentrancy, capture gaps and restored sidecar
identity require additional contracts. Existing history v1 completion remains
uncertified, and no ProgramMap/solver/image/lifetime/native path changes.
