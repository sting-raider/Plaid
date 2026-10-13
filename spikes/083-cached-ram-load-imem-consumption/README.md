# Cached operand ancestry composes with RAM writers and RSP execution

Run `python spikes/083-cached-ram-load-imem-consumption/run.py` or `--verify-existing`,
then `python scripts/test_rsp_definitions.py --cached-ram-imem --source
target/cached-ram-load-imem-consumption-primary/source.json`.

Controlled v25/fixture26 binds actual direct-KSEG0 Word LW to the canonical
DcacheReplay. Original-clock backing bursts capture current RAM byte parents;
actual fills, delivered reads and full16-byte/tag/index/dirty snapshots bind
resident generations. Existing RAM writes update that same state's captured
backing diagnostics. Held CPU expressions and RAM/IMEM copies retain explicit
cached-read/resident/physical-byte parents rather than borrowing current RAM.

Burst616/fill617 -> LW615/read618 selects handler/RAM copy writer595. IMEM624 is
consumed at RSP626. XORI631 derives ADDU21; actual uncached RAMwriter637 changes
e02c. LW642/read643 still delivers resident NOP from617/595; IMEM649/RSP651 stays
on those byte parents despite captured backing637/21. Actual guest HitInvalidateD
657 ends that resident; burst663/fill664 -> LW662/read665 selects637/21, then
IMEM671/RSP673 consumes ADDU. Both older reads retain their original parents.

The674-event/114-control capture,86 CPU steps/31 RSP words matches baseline,
disabled, enabled and repeated runs and the complete independent graph. All26
earlier report bytes remain exact. Source/report adversaries reject substituted
backing/resident/fill/read identities, altered full snapshots, omitted invalidation
and old equal IMEM parents. A pure negative-word check retains signed64 results
and Unknown fill parents; altering an untouched resident lane also rejects.

Scope is clean cached direct-KSEG0 aligned Word LW and actual matching
HitInvalidateD, kernel32/IE0/BEV0/EXL0/ERL0/non-delay/big-endian, at the exact ISC
ares pin. Warm unsensed/dirty/mapped/degraded/failed/other accesses, cached stores/
writebacks and general source/mutation/root/lifetime/whole-ROM/native remain OPEN.
All flags false; static ERET unsupported. No Actions/ROM/assets/upstream production
reuse or older/full-ROM reference rebuild. Reference callbacks remain passive;
debug cache reads are excluded from the execution read hook.
