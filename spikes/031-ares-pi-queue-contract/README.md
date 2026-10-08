# PI queue identity contract

Hypothesis: a last-returned DMA write and a later shared busy/interrupt transition
cannot establish transfer completion without queue direction, insertion identity,
cancellation and insertion-success evidence.

```powershell
python spikes/031-ares-pi-queue-contract/run.py
```

The original probe compiles the actual pinned nall priority queue header, checks
PI/CPU source routes and exercises duplicate identifiers, cancellation, full
capacity with invalid entries and clock wrap. It does not execute the CPU or PI
components, and supplies no hardware timing or whole-ROM certificate.

## Verdict: PARTIAL

### Evidence

- The command passes against the clean pin. Actual container dispatches duplicate
  write IDs `[1,1]`; canceling a write then enqueuing a read dispatches `[0]`.
- All 512 canceled slots still occupy capacity until drained; a new insertion
  fails in that interval. One wrap-boundary dispatch also passes and repeats.
- Source guards confirm both PI queue directions call the same completion method,
  guest PI reset removes both directions and CPU insertion failure returns silently.
- Result SHA-256:
  `426aeb8712dc52cd7c3f439f8748518c66f65b896bf033d3fa8f18f9c31f02cb`.

### Constraints and surprises

- Container execution and source routing are distinct from full device execution.
- Completion callbacks lack unique insertion identity; equal event IDs may coexist.

### Recommendation

- Sense successful queue insertion with a distinct observer token, removal and
  actual dispatch identity before certifying DMA completion. Retain data writes
  independently; insertion failure or cancellation need not erase those effects.
