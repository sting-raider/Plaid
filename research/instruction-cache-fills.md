# Completed instruction-cache fill events

2026-10-08. Hypothesis: the actual completed fill can distinguish equal resident
snapshots without an extra guest access or time step. At the pinned ares revision,
CPU::InstructionCache::Line::fill sets tag/valid state, steps 96 CPU clocks and
calls the existing busReadBurst with tag|index. An optional original callback
after that call samples the returned eight words, slot and request/burst address.
The slot derives from array position; no host pointer appears in output. The
generated reference header and binaries remain ignored with LICENSE preserved.

Spike 012 reuses the twelve controlled fetches from spike 010. Plain/traced/
repeated CPU/COP0/timing and full RAM/cache checkpoints match the prior fixed
goldens; repeat JSON is identical. Nine completed fills correspond to observed
fetch links 1/1/none/2/3/4/5/6/6/7/8/9. Count=444, cache misses=9 and hits=2;
all GPRs, final PC and complete hashes are unchanged. Equal payloads after
eviction have distinct event ordinals, while hits reuse a prior fill. Cache slots
129/1 retain distinct fills for identical physical lines. Reverse-endian fetches
select a different lane of the same fill result.

This proves finite completed-fill observation for these controlled cases.
It does not prove backing memory identity: a bus burst address can pass through
device decoding, RDRAM mapping or other policies. It also does not establish a
general interval from fill to fetch. The pinned CACHE implementation can store
tag/valid state or invalidate a line independently of fills; resets/restores and
CPU/device writes add more boundaries. Those events and copy/mutation sources
need explicit witnesses. A fill ordinal is therefore neither an immutable code
image nor an executable/cache epoch. No production handling or native output
is promoted.
