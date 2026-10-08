# Current cache tags differ from resident-byte history

2026-10-08. Hypothesis: a guest CACHE index-store-tag can make a successful cached
fetch's effective page differ from the last fill's burst page, without a new fill.
The pinned CPU::CACHE implementation changes line.tagKey/valid state for opcode
0x08; index invalidate 0x00 clears validity. Neither operation replaces words.

Spike 013 sets up two original RAM words, 0x24100001 at 0 and 0x24100009 at 0x4000.
Original guest CACHE instructions execute uncached between cached fetches. Host
fixture setup supplies TagLo/target registers and entry PCs, while guest opcodes
perform every tag/invalidation change. The seven-step tag sequence is
1/0x4001/0x4001/0x4000/0x4001/1/1, with fill counts 1/1/1/1/2/2/2. After retagging,
effective PA 0x4000 fetches resident word 0x24100001 filled at burst 0; after the
second retag, effective PA 0 fetches 0x24100009 filled at burst 0x4000. Explicit
guest invalidation forces the intervening refill. The current tag is therefore
an access identity, not a certificate for resident-byte origin.

A separately built baseline without the fill callback matches instrumented plain/
traced/repeated CPU/COP0/timing and full RAM/cache checkpoints. JSON repeats
exactly. Count=103, hits=2, misses=2, final s0=9; full GPR/HI/LO/PC and exception
checks pass. RAM SHA-256:
`acadcf93aed6b50df4253efb0a898bef4aa107253e68c3a2038a75315a65db82`.
Cache SHA-256:
`f1fae837b5c53982dab46e78c4aa73ed3b082f54c63b8bf26b2578c12c5d315e`.
Both recompilers remain disabled; no additional bus/coherence/translation access
or guest clock is introduced by the sensor.

This does not discard an observed historical fill: tag stores retain its data.
Data history and effective access need separate records, with actual backing
read/copy witnesses and explicit tag/invalidation/reset/restore boundaries before
general lifecycle construction. The production snapshot importer already retains
unknown backing and creates no images/epochs; these tests justify that boundary.
No production lifetime or native output is promoted.
