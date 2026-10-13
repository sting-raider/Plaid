# TLBR context loads compose with installed executable ancestry

Run `python spikes/079-tlbr-context-root-return/run.py` or `--verify-existing`,
then `python scripts/test_rsp_definitions.py --tlbr-context --source
target/tlbr-context-root-return-primary/source.json`.

Controlled v21/fixture22 observes TLBR after actual selected-slot copy at the
exact pinned ares interpreter. It binds full before/completed CP0/staged/table
state, unchanged GPRs and the selected installed TLBWI/page-writer parents.
Canonical `TlbrContextGeneration` fingerprints are derived from normalized raw
entries. Successful equal loads still create fresh occurrences; no installed
slot generation or cache retirement is inferred from a load.

EntryHi424 moves active ASID7->8. TLBR431 reloads installed slot417/page405/ASID7;
TLBR438 repeats equal context. Both later mapped consumers select latest load438,
with ASID write424 retained as an earlier separate occurrence. CACHE444 misses
the old tag, retaining resident292; remapped BREAK fill449/decoder451 selects
physicale028/CPUwriter391. Exception452 saves virtuale028; natural handler/
mutation/EPC/ERET returns through fill503/decoder505 retaining physicale02c/
CPUwriter473/DMEM/DMA/RSP ancestry. No host setter drives handler or return.

Full506-event independent source/report graph and80 existing full machine/cache/
CP0/pipeline/TLB controls with62 CPU steps are compared baseline/disabled/enabled/
repeat. Earlier source/report pairs are replayed without old reference builds.
Latest context selects either EntryHi or TLBR by occurrence, and later staging
cannot replace a previously installed page parent. TLBR restores that parent's
staged lineage for a later TLBWI, rather than borrowing an uninstalled write.

Scope stays captured in-range Index, normalized low-region/non-global/4KiB,
kernel32/IE0 pre-trap load. Out-of-range/exception/no-load/TLBP, arbitrary Index,
other CP0/global/geometry/reset/restore/hazards/source/root/mutation/lifetime/
whole-ROM/native remain OPEN; all flags false, static ERET unsupported. Cache
colors congruent; retain pinned cache-index disagreement without hardware claims.
Reference objects/notices/controls stay ignored; no upstream production reuse.
