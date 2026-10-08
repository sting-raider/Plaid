# PI request identity through queue dispatch/status boundary

Result: **PARTIAL**.

## Question

Can the already-validated external nall queue insertion identity be composed with
pinned ares PI request creation and CPU dispatch/status boundaries strongly enough
to name the scheduled PI lifecycle event, while failing closed on cancellation,
rejection and serialization and without pretending the queued event performed the
byte copy?

## Scope and exact references

Plaid research base: `5a24b9ccf3064d96f2f0d50fd3df1e50ee6d4862` on
`codex/executable-discovery`.

Research branch: `research/pi-request-queue-dispatch-gpt56sol`.

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Relevant pinned sources and SHA-256:

| Source | SHA-256 |
| --- | --- |
| `ares/n64/pi/io.cpp` | `f85015aa7cc10ef79164db4b8febc4516c5d3246607d99565527f6dfd6ac002e` |
| `ares/n64/cpu/cpu.cpp` | `65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1` |
| `ares/n64/pi/dma.cpp` | `296b7e1a8a096082f99a7b52d976acbabd20709062dbceb2f6f23481c900fab6` |
| `nall/nall/priority-queue.hpp` | `e54d6ca2cef5de37ae1ea8d57f756a329a53c2496cd609531943e5825dbf67f7` |

## Source map

The pinned PI write path first rejects non-status MMIO while `dmaBusy` or `ioBusy`
is set. For an accepted PI DMA request it then sets the length/busy/origin state,
calls `cpu.queueInsert(...)`, and immediately executes `dmaRead()` or `dmaWrite()`.

`CPU::queueInsert` returns `void`; if the finite queue's `insert` returns false it
returns silently. The PI caller has no success result and still executes the data
copy after the call.

The CPU scheduler calls `queue.step(...)`. Valid due PI DMA events route both
`PI_DMA_Read` and `PI_DMA_Write` to `pi.dmaFinished()`. That method clears
`dmaBusy`, sets the PI interrupt bit and raises the MI PI interrupt. It does not
perform the DMA bytes.

The pinned nall queue's `step` calls `remove()` first and invokes the callback only
if the returned event is valid. Thus an external observer of the actual valid root
removal can carry its exact token into the immediately following callback. A
canceled/invalid root is drained without that callback.

PI status reset clears busy/error and invalidates both PI DMA event classes in the
queue. Serialization can preserve the reference queue state while the external
identity observer deliberately forgets tokens; those are different facts.

## Experiment

`spikes/033-ares-pi-request-queue-dispatch/` reuses the generated observer hooks
from spike 032, so token metadata remains external to the queue object. It compiles
and executes the exact pinned queue with:

- original-header baseline;
- generated observer header with observer disabled;
- generated observer header enabled twice for deterministic replay.

The PI/CPU lifecycle is a synthetic harness whose ordering is guarded against the
exact pinned source text. This intentionally avoids claiming that the full ares
PI/CPU components were executed.

Adversarial cases:

1. equal event and equal deadline entries, to attack event/deadline joining;
2. PI cancellation followed by due-root draining;
3. all 512 queue slots occupied by invalid entries so a later lifecycle insertion
   fails;
4. save/read serialization boundary followed by a real valid dispatch whose
   external request identity must remain unknown.

The equal-valid pair is only a queue-container identity stress test. The pinned PI
MMIO busy gate means a second normal guest PI DMA request while one is live is
rejected before it reaches `queueInsert`.

## Results

Clean GitHub Actions run `37846025705` on Ubuntu 24.04 executed the pinned checkout,
then reran the recovered spike 032 and this spike.

Recovered spike 032 remained bit-for-bit at result SHA-256:

`c1388fb65891853c214d3651e3a9069f317ef19f22857e778a1de2fe412c14d0`

It again reported 523 successful insertions, one rejection, distinct identities for
equal event/deadline removals, two known canceled removals and unknown identities
across serialization.

Spike 033 result SHA-256:

`ca8d5b75da19f00f2a4b4963de65cca9c82a10d757c190baa6f01797cecc69d0`

Observed receipt:

- actual pinned queue executed: true;
- compared baseline/observer-disabled/repeated-enabled semantics equal: true;
- equal event/deadline tokens distinct: token `1`, token `2`;
- canceled event invoked no CPU callback: true;
- full-capacity request insertion accepted: false;
- that rejected request had no later dispatch: true;
- source-guarded immediate copy-effect model still advanced for the rejected request;
- post-serialization valid callback request identity: unknown (`0`), not guessed;
- full ares PI/CPU component executed: false;
- queue dispatch proves byte-copy completion: false.

The first clean CI run failed because observer-only token assertions were also run
when the generated observer was disabled. The correction gated only those
observer-specific assertions on tracing; it did not relax any identity or lifecycle
expectation. Subsequent clean runs passed.

## Conclusion

The hypothesis is **PARTIAL**.

For the pinned queue implementation, an external successful-insertion token can be
transported soundly through actual valid root removal into the immediately
following CPU callback, and from there used to identify the PI busy/interrupt
lifecycle transition. Cancellation and serialization provide concrete fail-closed
boundaries. This is stronger than joining by event type, deadline, current status
or the observer's latest PI context.

However, the scheduled event is not the DMA byte-copy operation in pinned ares.
The copy is performed synchronously in the PI MMIO request path after the
`queueInsert` call, and queue insertion can fail silently before that copy still
runs. Therefore a PI lifecycle token must never be treated as a byte-origin or
copy-completion witness.

## Candidate integration contract

- Allocate PI request context before `CPU::queueInsert`.
- Associate a queue token with that request only at actual successful insertion.
- Explicitly mark insertion rejection; do not synthesize a token and do not erase
  immediate data-copy evidence.
- Preserve DMA read/write byte provenance independently from the lifecycle queue.
- At valid root removal, export the exact token as a one-shot pending dispatch
  identity and consume it in the immediate CPU queue callback.
- Canceled roots do not dispatch. Repeated cancellation must not create a new
  identity.
- Reset/save/restore boundaries invalidate external identity unless an explicit
  restore proof reconstructs it. Unknown must remain unknown.
- `pi.dmaFinished()` may be attributed to a request only through the consumed
  token, never by equal event/deadline or latest-request heuristics.

## Remaining gaps

This spike does not execute a guest PI MMIO fixture through the full ares CPU/PI
components. That is the next direct validation step for observer neutrality and
hook ordering. Power/reset/save-state restore identity policy also remains open,
as does an audit for every internal producer of PI DMA queue events. Hardware
scheduling/timing is not proven. Most importantly for Plaid, this result does not
join the lifecycle event to actual RDRAM/PBUS byte-origin witnesses, I-cache fills,
or executable-generation identity.

Recommendation: **PRIMARY-INTEGRATOR-REVIEW**. The identity/lifecycle contract is
a useful candidate to transplant, while the byte-copy and lifecycle evidence must
remain categorically separate until actual backing transactions are joined.
