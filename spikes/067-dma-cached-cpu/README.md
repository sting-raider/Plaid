# DMA RAM ancestry through actual cached CPU consumption

Run `python spikes/067-dma-cached-cpu/run.py`, then
`python scripts/test_rsp_definitions.py --cached-cpu --source target/dma-cached-cpu-primary/source.json`.
`--verify-existing` authenticates retained controls without rebuilding.

Controlled v10 extends the original-clock producer/DMEM/DMA graph with actual
completed32-byte I-cache burst/fill observations and selected resident snapshots.
Reuse `FetchCacheLine.validate` for direct-KSEG0 identity-RAM slot/tag/index/word
selection; retain all32 fill-time byte parents. Cached consumption keeps those
parents through later backing changes. Cached receipts have real burst/fill IDs
and no invented uncached scalar-read identity.

Two explicit host PC control seeds enter cached6030 and6028. Each seed preserves
captured GPRs and cuts derived register definitions; it is an unknown execution
root, not a proven guest jump. The first fetch fills6020 including the previously
DMA-produced NOP at6028. A debugger write then changes backing6028 to BREAK;
the second CPU decoder still executes resident NOP with the old DMA/fill parents.
The first cached6030 word retains unknown initial ancestry. All unfetched lanes
are checked against the complete burst and retained in the fill receipt.

Baseline/disabled/enabled/repeat agree on31 checkpoints, including all512 I-cache
tags/indexes/words hashed at every checkpoint. Complete independent replay checks
208 events,14 CPU fetch/decoder pairs (12 scalar,2 cached),one burst/fill,21 RSP
fetched words and all images/parents. The original207-event capture omitted the
first host root; canonical admission rejects it for PC discontinuity. It remains
ignored negative evidence, not a valid source.

The fixed guest baseline is authenticated and reused after the sensor-only root
annotation correction. Its original shared-driver hash must match current source
with exactly that annotation removed; all other enrolled extras must still match.
Fresh/mismatching environments build normally. Only the corrected sensor needed
a rebuild. The controlled post-decoder drain schedule and all general hardware,
cache/mapping/restore/producer/mutation/root/lifetime/whole-ROM/native obligations
remain uncertified. Ten older v0-v9 source/report receipts remain byte-exact.
