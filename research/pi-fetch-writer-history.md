# PI backing writers versus resident fetches

Primary receipt, 2026-10-08. Hypothesis: consumed buffered PI sources can join
through successful destination bytes and actual read/fill contexts to finite
fetch evidence. Later backing writers must not replace a valid cache line's
historical origins, including identical reloads.

`python spikes/029-ares-pi-fetch-history/run.py` passes on pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, WSL Ubuntu x64, G++ 15.2, both
recompilers disabled. All sensors copy existing results/fields without guest
accesses or clocks. Direct host setup invokes PI DMA/completion components;
the CPU executes actual ORI/NOP, SW and CACHE instructions. Guest DMA MMIO,
scheduler duration and hardware agreement remain outside this fixture.

The original checker retains each successful RAM byte writer, snapshots those
origins only through an adjacent actual burst/completed fill, and preserves
resident history through subsequent backing writes. Uncached word attribution
requires exactly one eligible read in its actual fetch interval. Every cached
word agrees with the complete retained line and effective tag; guest hit
invalidation checks before/after snapshots before removing residency.

| Backing transition at RAM 4000 | Cached fetch | Uncached fetch |
| --- | --- | --- |
| Transfer 1, ROM 1000, word 34081111 | Transfer 1, first fill | Transfer 1 |
| Transfer 2, identical ROM 2000 | Transfer 1, same resident writers | Transfer 2 |
| Transfer 3, changed ROM 3000, word 34083333 | Transfer 1, word 34081111 | Transfer 3 |
| Guest SW writes 34084444 | Transfer 1, word 34081111 | Successful CPU writer, unknown ROM origin |
| Guest CACHE hit invalidate | New fill, CPU writer, unknown ROM origin | Unchanged backing |
| Transfer 4 copies three bytes from ROM 1000; guest invalidation | New fill, word 34081144, mixed byte origins | Same mixed origins |

Numbers are hexadecimal. The last word's first three bytes derive from transfer
4 and its last byte retains the guest SW writer. It has no contiguous ROM-word
origin. NOP at 4004 still derives from transfer 3, proving untouched-byte history
is retained. Equal words never select the latest transfer by equality.

481 records retain 99 PI byte writes, 16 actual fetches, three actual RAM-backed
fills and two guest invalidations. The independently compiled original-source
baseline, disabled sensors and repeated complete traces preserve all reported
checkpoint fields and final GPR/HI/LO/PC/Count/exception, full RAM/hidden and
instruction-cache data/tag hashes. Final Count 970, exception 0, t0 1144.

- RAM SHA-256: `244f6213e481b6380a6173976a5a68084a92a4fdc9e97d0e42ab424110642221`.
- Hidden SHA-256: `bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8`.
- Cache SHA-256: `624c32899483563cffde7b68e4f24041652c6b175b0ca4eccf6dbc27fa026607`.
- Complete result SHA-256: `b98481bdccdd2e408048fa82342dd7505d8e14815fe642d9cc1fac72c2e9a68f`.

Seven forged value/fill/invalidation/resident-line/completion/order cases fail.
An equal-byte substituted ROM offset removes corresponding origins; an extra
eligible scalar read removes uncached attribution. A fixture encoding error
initially used t0 for CACHE while setup supplied s0; explicit opcode/register
encoding corrected it, and original-source and observed executions now pass.

This is finite reference byte/writer evidence, not an executable installation,
image lifetime, complete mutation census or closure certificate. D-cache,
retag/writeback variants, translated memory and restores retain their separate
obligations. Next capture PI source blocks and destination contexts in the
broader boot chronology under a distinct version, preserving the complete v0
projection/v5 source and keeping scheduled completion separate from byte effects.
