# PI completion requires actual queue identity

Primary source/container receipt, 2026-10-08. The last observed buffered write
and a later PI busy/interrupt transition do not establish that write's scheduled
completion. `python spikes/031-ares-pi-queue-contract/run.py` checks clean ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04` source and compiles its actual nall
priority queue header separately with preserved ISC/BSD notices, WSL Ubuntu x64,
G++ 15.2. The original probe executes the container, not the CPU/PI or hardware.

The CPU queue dispatcher maps both `PI_DMA_Read` and `PI_DMA_Write` to
`pi.dmaFinished()`. The common method clears busy and raises interrupt. PI status
reset removes both event classes. `CPU::queueInsert` returns silently when the
container rejects an insertion; PI I/O continues to invoke the data-copy method.
These are pinned-source findings, not independently executed PI/CPU behaviors.

Actual container cases confirm:

| Case | Observed result |
| --- | --- |
| Two write IDs at different deadlines | Both dispatch as ID 1; no insertion identity survives |
| Cancel write, then insert read | Only read ID 0 dispatches |
| Cancel all 512 populated entries | Entries stay in the heap; new insertion fails until drained |
| Drain canceled entries | No callback; insertion subsequently succeeds |
| Deadline across one 32-bit clock wrap | No early callback; dispatch occurs at the expected step |

The two executions match exactly. Complete result SHA-256
`426aeb8712dc52cd7c3f439f8748518c66f65b896bf033d3fa8f18f9c31f02cb`.

Therefore the current boot PI status callback may expose only its observer's
last unfinished write context, not a proven queue-to-transfer relationship.
Count actual busy/interrupt transitions while keeping completion certification
false. Even queue direction alone cannot distinguish duplicate write IDs. A
future sensor must retain successful insertion, a distinct token, cancellation/
removal and actual dispatch provenance, including failed insertion and any
restore policy. Completed byte effects remain independent of queue outcome.
Broader clock/scheduler/device correctness and hardware timing remain unverified.
