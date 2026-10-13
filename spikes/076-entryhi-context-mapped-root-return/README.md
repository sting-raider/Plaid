# EntryHi context writers compose with mapped executable ancestry

Controlled v19 extends spike075 at exact ISC ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. Run `python run.py` or
`--verify-existing`; outputs stay ignored under
`target/entryhi-context-mapped-root-return-primary`.

Two TLBWI operations retain slot writer332. Actual EntryHi writes339/346/353 move
ASID7->8->7, then repeat7, without changing installed entries. The callback runs
inside the actual masked setter before its break. Full source GPR/decoder and
before/completed CP0/staged/32-entry data bind every occurrence. Both mapped
BREAK366/fill364 and returned fetch416/fill418/decoder420 select context353 and
slot332 separately. Handler LW377/read378 -> CPUwriter388/DMEM/DMA/RSP ancestry
remains the returned word's source. Handler/return have no host PC setters;
pre-trap guest context instruction entries are explicit opaque CPU roots.

Complete421-event source and independent full graph agree. Baseline/disabled/
enabled/repeat match48 CPU steps and66 complete reported machine/cache/CP0/
pipeline/TLB/staged controls; enabled source exact. All nineteen earlier actual
report bytes stay exact. No installed slot generation from a context write,
no context generation from table/payload inequality, and no cache retirement
from either operation alone. A non-global fetch under ASID8 rejects while ASID7
maps again; same-value final write353 replaces346 as the selected context.

Scope is bounded kernel32/IE0/non-delay/low-region4KiB/CCA3 identity RAM. Captured
initial context/GPR values have unknown ultimate ancestry. General sources/
changed-backing selection/hazards/TLBR/privilege/reset/restore/census/root/lifetime/
whole-ROM/native remain OPEN; all flags false, static ERET unsupported. No
upstream implementation copied/linked, no hardware latency or synonym claim.
