# PI request, queue identity and dispatch composition

Result: **VALIDATED** for the bounded pinned-ares PI DMA-write request -> queue-token -> CPU-dispatch composition described below, 2026-10-09. This is **not** a hardware-timing result and **not** a proof that the later queue event is when bytes are transferred.

## Hypothesis

A guest PI DMA request can be joined to a later PI completion handler only if one request is bound to one **successful** queue insertion token, that token survives heap movement without cancellation or chronology loss, the token is the valid queue removal consumed by the CPU dispatch callback for the same PI event class, and `PI::dmaFinished()` occurs under that dispatch context. Event value, deadline, current PI status, or the fact that bytes were already copied are insufficient identities.

## Pinned source map

Exact upstream revision: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.

- `nall/nall/priority-queue.hpp` blob `17eb754bccdfd075f8dac206d7c0aafd28d01e37`: fixed capacity is 512; insertion failure returns `false`; cancellation marks matching heap entries invalid; callbacks occur only for valid removals; serialization preserves queue clock/size/entries/validity.
- `ares/n64/cpu/cpu.cpp` blob `41964d49c8983ae9a97b25625174cd4c4316c4a8`: `CPU::queueInsert` silently returns if `queue.insert` fails. `CPU::synchronize` distinguishes `PI_DMA_Read` and `PI_DMA_Write`, but both invoke `pi.dmaFinished()`.
- `ares/n64/pi/io.cpp` blob `2a41a8240e96ea3517bfb1fa67748829a900fb84`: PI DMA-length writes set busy state, call `cpu.queueInsert(...)`, and then execute `dmaRead()` / `dmaWrite()` immediately. PI status reset clears busy/error and cancels both PI event classes.
- `ares/n64/pi/dma.cpp` blob `f2bd415495c6d84da779026b61fbe4c9f6ef7c88`: the byte-copy loop is inside `dmaRead()` / `dmaWrite()`. `dmaFinished()` later clears busy, sets interrupt and raises the PI IRQ; the common handler itself carries no read/write request identity.

The exact-pin source guard checks 13 contracts covering queue capacity/cancellation/serialization/callback validity, PI request ordering/reset behavior, CPU PI dispatch and common completion behavior.

## Recovered work and coordination provenance

Issue #4 had a near-simultaneous claim race. The earliest live lease for this semantic slice is `gpt56sol-pi-queue-dispatch-20261009` at 2026-10-08T21:10:00Z. Later overlapping workers correctly stopped/closed once the race became visible.

Useful work from the expired/raced branch was preserved rather than rewritten. The source-guard/model files and an actual-reference fixture existed in the raced history; cleanup from a duplicate worker removed parts of the actual fixture. This worker recovered the useful fixture from commit ancestry, repaired only the build harness, executed it at the exact pin, and records that provenance here rather than pretending authorship sprang fully formed from the current session.

## Source-guarded executable model

Command:

```sh
python3 spikes/033-ares-pi-queue-dispatch/run.py
```

Exact-pin CI result from Actions run `37846985240`, job `113550181178`:

- all 13 source contracts passed;
- 2,000 deterministic fuzz histories x 80 actions each;
- 3,672 modeled completions met the full request/token/dispatch contract;
- 2,327 modeled real PI completions were deliberately left unknown after identity loss;
- 17,965 PI copy effects occurred;
- five forged joins were rejected;
- canonical model report SHA-256: `ebab07300e683fa8d555f0fc4228fe3627b04bd261778373594be76cb3be0b27`;
- model result SHA-256: `d2934edd6252f069a25eb4e57fd71ee3e1d2724a027f461685c50dea64d99d26`.

This model was retained as an adversarial contract, but the conclusion below depends on the real pinned-core experiment, not on the model agreeing with itself.

## Actual pinned-core experiment

Command:

```sh
python3 spikes/033-ares-pi-queue-dispatch/actual.py
```

The harness uses the project headless ares builder and the already-validated external queue-identity sensor from spike 032. It builds and runs:

1. an uninstrumented baseline;
2. the callback-capable build with observers disabled;
3. the callback-capable build with observers enabled;
4. a repeated enabled run.

The enabled and disabled builds execute actual pinned `PI::ioWrite`, `PI::dmaWrite`, the actual 512-slot priority queue, `CPU::synchronize`, and actual `PI::dmaFinished`. Project-owned metadata is external to the reference queue object layout.

Actions run `37846985240`, job `113550181178` completed **SUCCESS** on Ubuntu 24.04. Baseline, observer-disabled and observer-enabled architectural fixture facts/state hashes were equal; the repeated enabled trace was byte-identical.

Actual trace SHA-256:

`a52ac2df67c03f4bbc68fe26c9a8ac09113212a9c6971af556d02d892d5d300c`

Actual result SHA-256:

`3b5b3850b35dd26ad728b5bac49eb1e8791f4b749d2aba11c09ee73ae4af9b6d`

Observed exact-reference summary:

- normal request id `1` received insertion token `1`; that same token reached one valid removal and the subsequent actual `dmaFinished()` callback;
- canceled request token `2` was invalidated and later drained invalid, with no completion callback;
- after filling all 512 queue slots, request id `3` still executed the immediate actual `dmaWrite` copy but received no queue token and produced no completion;
- two manually inserted `PI_DMA_Write` entries with the same event value and equal deadline received distinct tokens `515` and `516`; both reached the common completion callback with request identity deliberately unbound;
- a real request received token `517`, then queue serialization/reset/restore erased the external identity; the restored event still dispatched, but the completion remained token/request `0` and therefore uncertified;
- the actual run emitted 537 queue records and 100 PI records.

## Adversarial conclusions

### Full queue disproves copy-effect -> scheduled-completion

Ares copies the bytes synchronously after the failed `CPU::queueInsert`. Therefore observing the resulting RDRAM mutation cannot prove that a completion event exists. A future provenance system must record the byte-copy transaction separately from scheduled-dispatch identity.

### Cancellation must kill the exact token

Cancellation does not erase the heap slot. An invalid entry can later reach queue removal. Certification must require a **valid** removal carrying the same token, not merely a later occurrence of the same PI event class.

### Event class + deadline is not identity

Equal `PI_DMA_Write` events at the same deadline remain distinct queue entries. Matching by `(event, deadline)` or by latest PI request is unsound.

### Common `dmaFinished()` needs inherited context

Both PI event classes enter the same handler. Direction/request identity therefore has to be inherited from the exact valid dispatch context. The handler/status transition alone is insufficient.

### Serialization is a chronology boundary

The external queue token is intentionally discarded across serialization in this experiment. The restored real event may still execute, but provenance remains unknown until a separately validated snapshot/restore identity policy exists.

## Validated bounded contract

For this pinned-ares scope, the evidence supports the following chain:

`PI request id + PI event class -> successful queue insertion token -> uncanceled valid removal -> CPU dispatch(event, token) -> dmaFinished under that dispatch context`

The queue token proves **request-to-dispatch identity**. It does **not** prove that the byte transfer occurred at dispatch. In this ares implementation the copy occurred earlier, synchronously inside the PI register write path.

## Limits / remaining unknowns

This result is deliberately narrow:

- the full actual-reference request fixture exercises the `PI_DMA_Write` request path; the exact source guard covers both PI read/write dispatch classes, but a symmetric full-core `PI_DMA_Read` request fixture was not independently run;
- this is an emulator-instrumentation result at the pinned ares revision, not an N64 hardware timing oracle;
- it does not prove arbitrary boot-history joining, reentrancy, overlapping guest PI requests, or every frontend/reset lifecycle;
- save-state/restore identity is explicitly **not** certified;
- the queue token is a project-owned observation identity, not a guest-visible machine value;
- byte-origin provenance still requires the separate backing read/write transaction evidence and chronology work; this experiment only certifies the scheduling/dispatch identity chain;
- production ProgramMap/closure integration was intentionally not attempted on this research branch.

## Integration recommendation

**PRIMARY-INTEGRATOR-REVIEW**.

Adopt the fail-closed semantic contract and counterexamples. If integrating a production observer, preserve separate facts for (1) actual PI byte-copy transactions and (2) queue scheduling/dispatch identity, and never reinterpret `dmaFinished()` as the byte-transfer boundary. Reproduce Actions run `37846985240` or rerun both commands above before transplanting the instrumentation semantics.
