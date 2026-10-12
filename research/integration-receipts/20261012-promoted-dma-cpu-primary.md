# Promoted DMA identity and complete progression reach CPU execution

Base:e180f0b666105960f3154044202c549c78a8e8b4. Claim:6125755215.

Reconcile PR29/research/rsp-imem-install-lifetime-gpt56sol's actual pending->current
promotion and completion-before-busy-clear/handoff hooks with the canonical
original-clock RSP definition/DMEM/reverse-DMA/CPU execution graph. Preserve the
sp-dma-lifecycle research's rejected immutable-pending and sampled-BUSY-edge
assumptions. Ares's mutable/FULL behavior disagrees with Mupen/Gopher and remains
implementation-specific, not a hardware policy.

Compile the exact prepared rsp_imem_install module locally against current
plaid-core. REPRO: length16/count0 declares24 bytes, but one8-byte DmaSink followed
by Complete is accepted as one completed request. Its nonempty-fragment grouping
is insufficient for the declared complete progression. The ignored reproduction
is target/imem-prep-repro, with output target/imem-prep-repro.log. Preserve this
counterexample in canonical tests; do not transplant the looser verifier.
Prepared branch head:db66c527a8761b5804fe5872e7b03d362671d9c1;
module Git blob:4616e944e8cee4ef797f8d11f73759c2005f412d.

Controlled v5 derives request identity from the actual raw promotion ordinal.
Require every completed DMEM reverse-DMA Word's request/lane/current descriptor
to match the exact length/count/skip/row/PBUS-wrap progression. Completion requires
all expected words and the exact final PBUS/DRAM endpoint. Initial/pending labels,
equal payloads, nearest transfers or sampled BUSY-low state cannot supply identity.
Keep individual Word/byte writers separate from the request; unknown writes retain
their cuts. Request identity connects to the existing backing read/fetch/decoder
graph without changing its raw clocks or claiming continuous executable lifetime.

Guest program and19 checkpoints are unchanged. Authenticate and re-execute the
retained spike061 baseline instead of rebuilding it; compile only the required
new lifecycle sensor. Optional callbacks add no object fields/guest reads or state
mutations. Preserve existing SP/RSP source shadows while adding lifecycle hooks;
repeated standalone/composed generation and stale-output guards pass.

Authenticated baseline enrollment (issue4/comment6125875532):
results.json SHA a9c6ef980c5cd11a0c1ba0ed9ae7a706e2c9ebf486293cad35c4bb847f9cb710;
binary SHA6f0a45544ec0b4b022a9b40c1a8f864ae10477454034f8a62d69aedb96e36307;
build manifest SHA8d35d6212e0227e79a4cc657de92b95bb93147664b0ad6e60db61f6a3972556f;
v4 source SHA0e6d95cb879272bbf123981d6c8fe91753ddcf8fe456abefdbe450c09714fc9b.
Reject any changed digest or baseline/control fact.

Baseline/disabled/enabled/repeat agree on all19 machine/timing/exception checkpoints,
CPU steps, reported state and full reported bank/RAM hashes; repeated source exact.
Independent COMPLETE136-event census, source/image/definition/parent/request replay
agrees: promotion54, separate writes55/56, completion57; six definitions, three
IMEM copies, eleven CPU fetch/decoder pairs and seventeen RSP fetched words.
DMAwrite55 keeps RSP stores33..36/context32/definition30; CPU fetch132/read133
retains its four writers and decoder135 executes the exported NOP. No full-machine
state or hardware consensus coverage is inferred.

Source SHA256:
476cb236bb855af8ea6f5d980d01fbab5dc398c9df62b27dfc79844a13a4b656.
Report SHA256:
344789d2e2c288c91f79e113a7c19ac4b1e4001b0b8aa3b4a4ad9e22ee8c9b4a.
All v0-v4 reports remain EXACT; prior v4:
bc71405ad5a1c0e69a8465b95d36864c6e627df8f80b59d36d02bd6b4bd347c8.

Focused20, actual/synthetic CLI, complete source/report verification, independent
graph/source replay, exact-pin guards and five old report checks PASS. Regression
coverage includes early/incomplete declared transfers, missing promotion/completion,
wrong ownership, missing/duplicate/reordered Word/read callbacks, endpoints, count/
skip/wrap, equal reloads, immediate completion/promotion, mixed/unknown byte parents
and report deletion/forgery. All proof flags remain false.
Full local fmt, strict locked workspace/all-target Clippy, locked workspace tests,
canonical CLI and diff gate PASS with two build jobs. No skipped checks, changed
reference baseline, repeated emulator build or weakened proof obligation.

PR29's lifecycle atoms are partially reconciled; its IMEM ingress/install layer and
loose grouping module are not wholesale merged. Broader producer/consumer coverage,
accepted pending requests, general FIFO policy, DMA ingress, reset/restore/cache/TLB,
mutation census, hardware consensus, continuous lifetime and whole-ROM/native stay
OPEN. No progress milestone, ROM/assets, branch-only workflows or upstream
implementation import. Generated artifacts stay ignored under
target/promoted-dma-cpu-consumption-primary and target/promoted-dma-integration-primary.
