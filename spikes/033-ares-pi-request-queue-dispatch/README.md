# PI request -> queue token -> dispatch/status join

## Hypothesis

A fail-closed external observer can join one PI DMA request to the exact successful
nall queue insertion and later CPU dispatch/status transition by carrying the
actual queue token through valid root removal. Event value, deadline, latest PI
context, or status transition alone are insufficient. Queue dispatch must remain
separate from the byte-copy fact.

## Reproduce

Pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

```bash
python3 spikes/032-ares-queue-identity/run.py
python3 spikes/033-ares-pi-request-queue-dispatch/run.py
```

`run.py` checks the clean pinned revision and source ordering in:

- `ares/n64/pi/io.cpp`
- `ares/n64/cpu/cpu.cpp`
- `ares/n64/pi/dma.cpp`
- `nall/nall/priority-queue.hpp`

It compiles and executes the exact pinned nall queue twice with the generated
observer plus an original-header baseline. PI/CPU sequencing is a synthetic,
source-guarded harness; this spike does **not** execute the full ares PI/CPU
components or claim N64 hardware timing.

## Verdict: PARTIAL

Clean GitHub Actions run `37846025705`, Ubuntu 24.04, passed both the recovered
spike 032 and this composition spike. The recovered queue result remained
`c1388fb65891853c214d3651e3a9069f317ef19f22857e778a1de2fe412c14d0`.
This spike produced:

`ca8d5b75da19f00f2a4b4963de65cca9c82a10d757c190baa6f01797cecc69d0`

### Evidence

- Pinned PI MMIO sets `dmaBusy`, calls the `void` `CPU::queueInsert`, then calls
  `dmaRead()` / `dmaWrite()` synchronously. `CPU::queueInsert` silently returns
  when the finite queue rejects an insertion. Therefore byte-copy effects are
  independent of a later scheduled PI lifecycle event.
- Pinned queue `step()` removes a due root and invokes the callback immediately
  only when that removed root is valid. The existing external identity sensor can
  therefore expose one valid root token to the immediately following CPU switch
  without matching event/deadline values.
- Two equal event/deadline queue entries retained distinct tokens `1` and `2` and
  joined to distinct synthetic request contexts. This is an adversarial container
  identity test only: pinned PI MMIO rejects a second normal guest request while
  PI is busy, so it is not evidence that two live guest PI DMAs are normally
  reachable.
- PI status cancellation invalidated the queued PI event; draining that invalid
  root invoked no CPU callback.
- With 512 invalid-but-still-occupied queue entries, a PI lifecycle insertion was
  rejected while the source-guarded model still recorded the immediate copy
  effect. No dispatch followed for that request.
- At serialization entry the observer deliberately loses queue identity. A later
  valid callback still occurred, but the request join was `unknown` instead of
  being reconstructed from event/deadline coincidence.
- Original-header, generated-header observer-disabled, and repeated enabled runs
  agreed on the compared semantics. The first CI attempt failed because the probe
  incorrectly asserted token presence while the observer was disabled; the test
  was fixed by gating observer-only assertions rather than weakening evidence.

### Source SHA-256

- CPU: `65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1`
- PI DMA: `296b7e1a8a096082f99a7b52d976acbabd20709062dbceb2f6f23481c900fab6`
- PI I/O: `f85015aa7cc10ef79164db4b8febc4516c5d3246607d99565527f6dfd6ac002e`
- nall queue: `e54d6ca2cef5de37ae1ea8d57f756a329a53c2496cd609531943e5825dbf67f7`

## Fail-closed integration contract

1. Create a PI request identity/context before calling `cpu.queueInsert`.
2. On actual successful queue insertion, associate the new queue token with that
   request. On actual rejection, record `no_queue_token` and do not invent one.
3. Keep PI data-copy provenance independently at the immediate `dmaRead` /
   `dmaWrite` effects. Never require or wait for the lifecycle token to certify
   those writes.
4. On valid due-root removal, expose that exact token as a one-shot pending CPU
   dispatch identity. Consume and clear it in the immediately following CPU queue
   callback before routing to `pi.dmaFinished()`.
5. Cancellation invalidates the token lifecycle; draining an invalid root must not
   manufacture a dispatch.
6. Reset/serialization/restore epochs must invalidate or explicitly rebuild token
   identity. If proof is absent, later dispatch identity is `unknown`.
7. Never join a PI completion from event type, deadline, latest request context, or
   busy/interrupt state alone.

## What remains unknown

The full ares PI/CPU components were not instrumented and executed end-to-end in
this spike. A guest MMIO fixture should verify the same hook ordering and state
neutrality inside the emulator. Power/reset/save-state identity policy, all other
possible producers of PI queue events, hardware timing, and composition with
actual byte-origin witnesses remain separate obligations.

Recommendation: `PRIMARY-INTEGRATOR-REVIEW`. Adopt the fail-closed identity
contract as a candidate sensor design, but do not promote queue dispatch into a
byte-copy-completion or hardware-timing certificate.
