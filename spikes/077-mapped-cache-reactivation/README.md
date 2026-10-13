# Nonidentity mapped cache reactivation composes with executable ancestry

Run `python spikes/077-mapped-cache-reactivation/run.py` (or `--verify-existing`)
and `python scripts/test_rsp_definitions.py --mapped-reactivation --source
target/mapped-cache-reactivation-primary/source.json`.

Fixture20 reuses the existing v19 production protocol and unified source clock;
no new consumer, schema, opcode admission or completeness waiver is introduced.
At the exact ISC ares pin, actual guest TLBWI installs VA e000 -> PA6000. Mapped
PC e028 therefore consumes physical6028, while exception EPC and transformed
ERET target remain virtual e028/e02c.

Two mapped hits, before and after actual EntryHi ASID7->8->7->7 operations, retain
old fill292/CPUwriter276 and execute ADDU21 while current RAM already contains
BREAK from writer318. Context operations preserve that resident. The second hit
selects latest completed context writer358 and distinct TLB slot writer332.
Only subsequent guest HitInvalidateI ends292; the new BREAK refill then selects
writer318, enters the copied handler and naturally returns through changed EPC
to fresh NOP/CPUwriter398/DMEM/DMA/RSP ancestry. No host setter drives handler or
return. Pre-trap instruction entry seeds are explicitly opaque control roots.

The independent complete431-event graph checks every source event and report
parent. Baseline/disabled/enabled/repeat compare68 full existing machine/cache/
CP0/pipeline/TLB controls and50 CPU steps. Earlier sources/reports are reused.
Adversaries reject virtual/physical substitution, stale-current writer borrowing,
wrong restored context, wrong cache/tag/content and rewritten return targets.

The virtual/physical cache colors are congruent. Retain the ares virtual-index vs
Gopher physical-index disagreement; no new hardware, synonym or hazard claim.
Initial inputs remain UNKNOWN. Changed physical selection, broader mapping/CP0/
root/reset/restore/mutation coverage and whole-ROM/native closure remain OPEN;
all general proof flags false, static ERET unsupported. Generated reference
objects, notices, controls and reports stay ignored under target/.
