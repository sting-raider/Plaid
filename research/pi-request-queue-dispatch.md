# PI request, queue identity and dispatch composition

Result: **PARTIAL**, 2026-10-09. This is a bounded composition result for pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, not a hardware invariant or a full-core PI completion certificate.

## Hypothesis

A guest PI DMA request can be joined to a later PI completion only if one request is bound to one **successful** queue insertion token, that token survives cancellation and lifecycle boundaries, the token is the valid queue removal consumed by the CPU dispatch callback for the same PI event class, and `PI::dmaFinished()` occurs under that dispatch context. A latest-write/status heuristic must fail closed.

## Pinned source map

Exact pinned source inspected:

- `nall/nall/priority-queue.hpp` blob `17eb754bccdfd075f8dac206d7c0aafd28d01e37`: capacity failure returns `false`; cancellation only marks matching heap entries invalid; `step()` invokes the callback only when `remove()` returns a valid event; serialization preserves queue clock/size/entry validity.
- `ares/n64/cpu/cpu.cpp` blob `41964d49c8983ae9a97b25625174cd4c4316c4a8`: `CPU::queueInsert` silently returns when `queue.insert` fails. `CPU::synchronize` distinguishes `PI_DMA_Read` and `PI_DMA_Write` in the switch, but both dispatch to `pi.dmaFinished()`.
- `ares/n64/pi/io.cpp` blob `2a41a8240e96ea3517bfb1fa67748829a900fb84`: for both PI DMA registers, ares sets DMA busy and origin, calls `cpu.queueInsert(...)`, and then executes `dmaRead()`/`dmaWrite()` immediately. PI status reset clears busy/error and cancels both queue event classes.
- `ares/n64/pi/dma.cpp` blob `f2bd415495c6d84da779026b61fbe4c9f6ef7c88`: `dmaFinished()` itself has no direction identity; it clears busy, sets interrupt and raises PI IRQ. `PI_DMA_Write` is the PBUS-to-RDRAM data path and `PI_DMA_Read` is the RDRAM-to-PBUS path.

The existing `spikes/032-ares-queue-identity/` experiment already executed the exact pinned queue and validated distinct insertion/removal tokens through heap movement, cancellation and equal event/deadline pairs while preserving baseline state. This experiment deliberately composes that validated primitive instead of duplicating it.

## Executable contract experiment

`spikes/033-ares-pi-queue-dispatch/model.py` models the pinned queue operations and the minimum proposed request/dispatch observer. It independently replays the event ledger and rejects forged joins. `source_guard.py` binds the model assumptions to the exact pinned source. `run.py` requires `.refs/ares` at the exact pin and runs both.

Deterministic local model run:

- 2,000 fuzz histories × 80 actions each.
- 3,672 completions met the complete request/token/dispatch contract.
- 2,327 real modeled PI completions were deliberately left unknown after identity loss.
- 17,965 PI copy effects occurred.
- five independent ledger forgeries were rejected.
- canonical model report SHA-256: `ebab07300e683fa8d555f0fc4228fe3627b04bd261778373594be76cb3be0b27`.

Adversarial cases:

1. Successful read and write requests each certify only their own insertion token.
2. With all 512 queue slots occupied, the PI request still performs its immediate copy effect after silent insertion rejection, but has no scheduled completion identity and remains busy. This directly disproves `copy effect => scheduled completion`.
3. Canceling a write and then issuing another same-class request at the same delay certifies only the second token; the canceled token cannot be borrowed.
4. A serialization boundary intentionally discards external queue identity. The queued event can later dispatch and `dmaFinished()` can clear busy/raise interrupt, but completion provenance remains unknown.
5. Two equal-deadline low-level PI event insertions retain distinct tokens. This is a queue-composition adversary, not a claim that guest PI MMIO can legally create two concurrent busy requests.
6. Forged completion request ID, dispatch direction, completion token, request direction and dispatch token are all rejected by independent replay.

## Consequence

The bounded evidence says a sound future observer should carry:

`PI request id + PI event class -> successful queue token -> uncanceled valid removal -> CPU dispatch(event, token) -> dmaFinished under that dispatch context`.

The PI copy/write history remains a separate fact. It may be joined to the request, but it must not by itself certify that the scheduled completion exists. A dispatch after a serialization/restore boundary is unknown unless a separately validated restore policy reconstructs identity.

## Limits and next experiment

This worker could not clone the references in the local sandbox because outbound DNS to GitHub is unavailable. The exact files above were inspected through the GitHub connector, and the branch includes a source guard plus branch-only GitHub Actions workflow intended to execute the guard at the pin. The new composition model is executed locally; the full pinned CPU/PI implementation is **not** instrumented or executed by this spike. Therefore instrumentation neutrality, reentrancy, arbitrary save/restore semantics, full boot chronology joining, and hardware timing remain unproved.

Recommended next step: instrument the actual pinned CPU queue-dispatch boundary and PI request/dmaFinished boundaries while reusing the external queue-token sensor, then run the existing bounded boot fixture baseline/disabled/enabled/repeat. Promote completion only if that full-core run preserves the fail-closed cases above.

Integration recommendation: **INVESTIGATE**. Adopt the evidence contract and the full-queue/cancellation/serialization counterexamples, but do not yet promote boot PI status contexts to certified completion identities.
