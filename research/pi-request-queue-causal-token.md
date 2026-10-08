# PI request identity must precede queue insertion

Status: **PARTIAL**

Worker lane: compose one accepted PI MMIO DMA request with the exact pinned ares
queue insertion/cancellation/dispatch path, and determine whether a queue-entry
identity is sufficient to witness the request through completion.

## Revisions

- Plaid base: `5a24b9ccf3064d96f2f0d50fd3df1e50ee6d4862`
  (`codex/executable-discovery` at claim time)
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Existing prerequisites: `research/pi-queue-completion-contract.md` / spike 031
  and `research/queue-insertion-identities.md` / spike 032.

Pinned source guard used by spike 033:

| file | Git blob |
| --- | --- |
| `ares/n64/n64.hpp` | `33a2a973d6026a8a014231f79a8ab9b98998b703` |
| `ares/n64/pi/io.cpp` | `2a41a8240e96ea3517bfb1fa67748829a900fb84` |
| `ares/n64/pi/dma.cpp` | `f2bd415495c6d84da779026b61fbe4c9f6ef7c88` |
| `ares/n64/cpu/cpu.cpp` | `41964d49c8983ae9a97b25625174cd4c4316c4a8` |
| `nall/nall/priority-queue.hpp` | `17eb754bccdfd075f8dac206d7c0aafd28d01e37` |

## Hypothesis

A request-scoped token attached at the accepted PI DMA scheduling point and
carried by the exact queue entry can uniquely witness
`request -> queue insertion -> dispatch -> dmaFinished`, including identical
request tuples after cancellation. Cancellation must retire the old identity,
and an interrupt-clear must not.

The adversarial question is whether every accepted PI request necessarily has a
successful queue insertion to carry such a token.

## Pinned source path

`PI::ioWrite` first rejects all non-status writes while either PI busy bit is
set. For an accepted read/write length write it then:

1. stores the length and sets `io.dmaBusy = 1`;
2. records `io.originPc`;
3. calls `cpu.queueInsert(Queue::PI_DMA_Read/Write, dmaDuration(...))`;
4. immediately calls `dmaRead()` / `dmaWrite()`.

`CPU::queueInsert` calls `queue.insert(event, clocks)` and returns silently when
that insertion fails. It does not report the failure to PI. The PI data-copy
call therefore still executes after a rejected event insertion.

The data movement is not deferred to the queue callback. `PI::dmaWrite()` reads
from the peripheral bus and writes RDRAM immediately; `PI::dmaRead()` reads
RDRAM and writes the peripheral bus immediately. `PI::dmaWrite()` also mutates
`io.dramAddress`, `io.pbusAddress`, and `io.writeLength`, so a provenance sensor
that wants the original request parameters must snapshot them before calling the
data-copy method.

Later, `CPU::synchronize()` steps the global queue. Both PI DMA event classes
call only `pi.dmaFinished()`, which clears busy and raises the PI interrupt.
Writing PI status bit 0 clears busy/error and calls `queue.remove()` for both PI
DMA event classes. Status bit 1 only clears the PI interrupt.

The pinned `nall::priority_queue<T[512]>` has capacity 512. `remove(event)` marks
matching heap entries invalid but does not decrease `size`; canceled entries are
physically drained only when their deadlines reach the heap root during
`step()`. This container fact was already established by spike 031; the new
question here is its consequence at the real PI request boundary.

## Experiment

`spikes/033-ares-pi-causal-token/probe.cpp` is a standalone behavioral extraction
of the exact queue operations plus the PI ordering above. It runs a baseline and
an instrumented model side by side. The token metadata is excluded from queue
ordering and all externally observable state comparisons.

Deterministic cases:

1. accepted request -> successful insertion -> same token completes;
2. second length write while busy is rejected before insertion and does not mint
   an accepted-request token;
3. request, status reset, identical restart at the same absolute deadline:
   canceled and live entries have the same event/deadline tuple but distinct
   tokens, and only the new token completes;
4. PI interrupt clear preserves the active request/token;
5. 512 `request -> status reset` pairs without advancing queue time fill the
   heap with canceled tombstones. Request 513 is accepted by PI and executes the
   immediate DMA method, but its queue insertion fails, so there is no queue
   entry that can carry a completion identity;
6. 64 deterministic random seeds x 20,000 operations compare baseline and tagged
   models after every request/reset/interrupt-clear/time-step operation.

Compared neutrality fields are PI busy/error/interrupt state, immediate DMA
count, completion count/order, queue size, queue clock, and next-event timing.

Commands executed in this worker environment:

```text
g++ -std=c++20 -O2 -Wall -Wextra -pedantic probe.cpp -o probe
./probe

g++ -std=c++20 -O1 -g -fsanitize=address,undefined \
  -fno-omit-frame-pointer -Wall -Wextra -pedantic probe.cpp -o probe-sanitize
ASAN_OPTIONS=detect_leaks=1 ./probe-sanitize
```

Both builds produced byte-identical stdout:

```text
PASS straight_completion token=1
PASS busy_reject_no_token records=1
PASS equal_tuple_cancel_restart old=1 new=2 completions=1
PASS interrupt_clear_preserves_request token=1
PASS queue_full_dma_without_event queue_size=512 immediate_dmas=513 rejected_token=513
PASS differential_fuzz seeds=64 ops_per_seed=20000 total_ops=1280000
RESULT PARTIAL: queue-entry token is sufficient for successful insertions but not universal; request identity must predate queue insertion and record insertion failure.
```

Output SHA-256:
`8f49c659443569004ccc17e377988cdac70d17cb33df669f37ac69667c0f0424`.
Probe source SHA-256:
`a23bbf02dbbb5f03637e77cb4a4e2b1bf9c92c6d122a4d9149f6eac636bd422c`.

The committed runner additionally checks the five exact upstream Git blob IDs,
requires a clean `.refs/ares` at the pinned revision, repeats the optimized run,
and builds/runs ASan+UBSan. The worker could not execute that wrapper against a
local `.refs/ares` checkout because this environment's direct GitHub DNS path
failed; the probe itself was compiled and run locally as above, while the exact
upstream files were inspected through the GitHub connector.

## Result

**PARTIAL.** A successful queue insertion identity is sufficient to disambiguate
identical event/deadline tuples and to join a successfully queued request to the
specific dispatch candidate, provided cancellation and dispatch retain that
identity. It is **not** sufficient as the root identity for PI data movement.

An accepted PI request can execute data movement without any queue entry at all
when insertion fails. Therefore the causal root must be minted at the accepted
PI request boundary, before `CPU::queueInsert` and before the immediate data-copy
method.

A useful trace contract is:

```text
PI_REQUEST_ACCEPTED {
  request_id,
  direction,
  original_dram_address,
  original_pbus_address,
  original_length,
  origin_pc,
  computed_duration
}

PI_QUEUE_RESULT {
  request_id,
  outcome = inserted(queue_insertion_id) | rejected_full
}

PI_BYTE_EFFECT / PI_TRANSACTION {
  request_id,
  ...actual backing read/write witness...
}

PI_REQUEST_CANCELLED {
  request_id,
  queue_insertion_id?     // present only when insertion succeeded
}

PI_REQUEST_COMPLETED {
  request_id,
  queue_insertion_id      // only a valid dispatched queued request can complete
}
```

Busy-rejected length writes may be logged as rejected attempts, but they must not
be confused with accepted request generations because they perform no PI DMA.
Interrupt clear is not cancellation. Status reset is cancellation of the current
accepted request even if that request had `rejected_full` and therefore has no
queue identity.

For a successfully inserted request, compose the already-prototyped spike-032
queue insertion identity with `request_id`; do not fall back to `(event,
deadline)`, current PI registers, or a global "last PI request" slot. The latter
are ambiguous after cancel/restart, and `dmaWrite()` mutates the live PI register
state after the request snapshot point.

## What this does not prove

- This did not compile or run the full ares CPU/PI subsystem. It is a
  source-guarded executable behavioral extraction, so full-emulator
  instrumentation neutrality remains unproven.
- It does not establish N64 hardware behavior for queue saturation; the 512-entry
  queue is an ares implementation detail. The point is instrumentation
  completeness relative to the pinned oracle and Plaid's trace evidence.
- It does not prove actual backing-byte provenance. The request ID should label
  future RDRAM/PBUS transaction witnesses; address/direction alone is still not
  byte origin.
- It does not solve save-state identity across serialization. Spike 032 already
  marks unsupported restored queue identities unknown.
- It does not prove closed-world executable discovery or PI timing correctness.

## Integration recommendation

**PRIMARY-INTEGRATOR-REVIEW.** Adopt the semantic contract, not this standalone
model. The next production/reference instrumentation step should mint PI request
IDs at the accepted MMIO length write, snapshot immutable request parameters,
compose them with spike-032 successful insertion IDs, label the immediate
RDRAM/PBUS effects with the request ID, explicitly record insertion rejection,
and close the request on reset or identified dispatch/completion.
