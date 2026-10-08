# ares PI queue dispatch identity

Conclusion: **PARTIAL**

Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Related Plaid state: `research/pi-queue-completion-contract.md`,
`research/queue-insertion-identities.md`, and
`spikes/032-ares-queue-identity/` at integration base
`5a24b9ccf3064d96f2f0d50fd3df1e50ee6d4862`.

## Question

Can the layout-neutral monotonic insertion identity validated by spike 032 be
carried from one specific PI DMA scheduling request to the exact queue row that
CPU dispatches to `PI::dmaFinished()`, without identifying work by an ambiguous
`(when,event)` tuple or by transient heap location?

Hypothesis: a sidecar token that mirrors every heap move is sufficient for the
continuous-execution path. Tuple-only and slot/pointer identity are not. The
hypothesis was intentionally tested against duplicate rows, cancellation,
heap compaction/reuse, capacity failure, and serialization.

## Pinned source map

At the pinned ares revision:

1. `ares/n64/pi/io.cpp`
   - writes of `PI_READ_LENGTH` / `PI_WRITE_LENGTH` set `io.dmaBusy`, record
     `io.originPc`, synchronously call `cpu.queueInsert(Queue::PI_DMA_*,
     dmaDuration(...))`, then perform the DMA body;
   - a PI status reset calls `queue.remove(Queue::PI_DMA_Read)` and
     `queue.remove(Queue::PI_DMA_Write)`.
2. `ares/n64/cpu/cpu.cpp`
   - `CPU::queueInsert` synchronously calls `queue.insert(event, clocks)`;
   - `CPU::synchronize` calls `queue.step(clocks, callback)` and dispatches
     `PI_DMA_Read` / `PI_DMA_Write` callback events directly to
     `pi.dmaFinished()`.
3. `nall/nall/priority-queue.hpp`
   - the queue is a fixed binary min-heap;
   - insertion bubbles parent entries down before writing the new row;
   - root removal repairs the heap by copying child/last rows;
   - `remove(event)` does not physically delete rows: it marks every matching
     row invalid;
   - `step()` calls the CPU callback only when `remove()` returns a valid event;
   - serialization writes queue clock, size and every heap entry.
4. `ares/n64/n64.hpp`
   - the N64 queue is `priority_queue<u32[512]>`.
5. `ares/n64/system/serialization.cpp`
   - N64 system serialization executes `s(queue)` before `s(pi)`.
6. `ares/n64/pi/serialization.cpp`
   - PI state includes DMA busy/error/interrupt, DRAM/PBUS addresses, lengths,
     bus latch, origin PC and timing fields, but no Plaid queue/request identity.

## Exact continuous-execution join

Spike 032 already mirrors queue slot identity for all heap-copy operations and
mints a fresh token at the final insertion slot (`kind == 4`). This is enough to
build the missing bridge without changing ares queue entry layout or callback
signature:

- **Request -> token:** because `CPU::queueInsert` is synchronous, a PI observer
  can associate the request with the fresh `kind == 4` token produced during
  that call. A failed insert (`kind == 2`) must instead produce *no* token.
- **Token -> exact removal:** spike 032's `kind == 5` fires on heap slot 0 before
  root repair and therefore names the exact row being removed, including its
  validity.
- **Removal -> CPU dispatch:** `priority_queue::step` immediately invokes its
  callback after that `remove()` only when the removed row was valid. There is
  no intervening queue operation in this path. The CPU callback then switches
  on the same event and calls `pi.dmaFinished()` for both PI DMA event kinds.
- **Cancellation:** spike 032's `kind == 8` runs on the exact matching slot
  before `valid = false`. That token can be closed as canceled. When the
  tombstone later reaches root, `kind == 5` still observes it but `step()` does
  not issue a CPU callback.

A robust bridge should validate owner, event, validity and observer ordinal, not
just carry a mutable global token and hope no unrelated queue action happened.

## Adversarial experiment

`spikes/033-ares-pi-dispatch-identity/run.py` is a clean-room semantic model of
the pinned priority queue. It runs an uninstrumented baseline and a sidecar
variant in lockstep.

Deterministic cases:

- **duplicate tuple:** two `PI_DMA_Write` entries at the same absolute clock
  have the same tuple but distinct tokens `1` and `2`; exact removal reports
  `1`, then `2`;
- **slot reuse:** an earlier-deadline later insertion moves token `1` from heap
  slot 0 to slot 1 while token `2` becomes root, disproving slot/pointer
  identity;
- **cancellation tombstone:** token `1` is observed when invalidated and again
  when removed invalid, while only surviving token `2` reaches a callback;
- **capacity:** after 512 accepted rows, the 513th insertion fails and no token
  is fabricated;
- **serialization:** current spike-032 `kind == 9` clearing changes a pending
  token from `1` to `0` before its later dispatch.

Fuzz case: seed `0x504c414944`, 200,000 mixed operations, 96,018 accepted
inserts, 34,277 cancel operations and 80,950 valid callbacks. After every
operation, queue clock/size/live heap rows were bit-for-bit equal between the
baseline and sidecar models. Visible-state trace SHA-256:
`b10f8a5d4c4f3de8e64519b9d7665d0fa360ba937a0fab465506cb9265690d79`.

The run was repeated twice and outputs compared byte-for-byte.

## Falsification: savestate creation already breaks spike 032 identity

The continuous-execution hypothesis survives heap mutation, but current spike
032 does **not** survive serialization. Its observer executes
`queueIdentitySlots.fill(0)` for both reset (`kind == 1`) and serialize
(`kind == 9`) regardless of whether the serializer is reading or writing.

Pinned N64 `System::serialize` calls `s(queue)` for a normal save. Therefore a
pending PI row loses its token merely because a savestate was *created*; no
load is needed. A later `kind == 5` reports token zero and cannot be joined back
to the request. The experiment reproduces exactly this sidecar state change.

A load is harder still: the upstream queue payload contains only emulator state
(clock, size, entry clock/event/valid), so duplicate rows do not encode their
pre-save provenance. PI serialization likewise contains no Plaid identity.

Thus repeated dynamic observation cannot justify a global request -> completion
identity across serializer boundaries using the current observer alone.

## Recommended contract

For continuous execution between serializer boundaries, adopt the sidecar join:

1. mint only on successful final insertion;
2. associate the PI request synchronously with that token;
3. mirror every heap copy exactly as spike 032 does;
4. record token-specific tombstone invalidation;
5. at root removal, capture `{token,event,valid,ordinal}`;
6. consume that exact record at CPU callback and require event/validity match;
7. treat failed insertion as an explicit no-token scheduling failure.

For serialization:

- on **save**, do not clear live tokens;
- on **load**, do not pretend old identities are recoverable from the upstream
  heap payload. Start a new identity epoch and invalidate pre-load request joins
  unless Plaid also restores a separately persisted provenance sidecar;
- if post-load queue rows must remain traceable, add a post-deserialization
  observation that mints fresh epoch-local identities for occupied rows;
- if cross-load request provenance is required, persist token/request metadata
  out-of-band with the savestate and verify it against the restored queue. Do
  not infer it from `(clock,event)` when duplicates are possible.

## Limitations

- This worker could not clone/build pinned ares because the local execution
  sandbox has no outbound DNS. Exact pinned source was inspected through the
  GitHub connector, and the executable experiment is a semantic reproduction
  of the small priority-queue algorithm rather than an instrumented full ares
  binary.
- The experiment proves neutrality of the modeled queue state, not whole-emulator
  timing neutrality. Spike 032 already supplies the in-source observer placement
  and its earlier neutrality result; a primary integration patch should still
  rerun the full ares oracle.
- No claim is made that PI DMA itself is a complete executable-byte provenance
  witness. This result only closes the scheduler identity edge between request,
  cancellation/removal and completion for continuous execution.
- Savestate provenance remains unresolved unless an out-of-band persistence
  contract is implemented and tested.

## Recommendation

**PRIMARY-INTEGRATOR-REVIEW.** Adopt the continuous-execution request -> token ->
root-removal -> callback join, but do not promote it to a global completion
identity until serializer behavior is fixed and cross-load provenance policy is
explicitly tested.
