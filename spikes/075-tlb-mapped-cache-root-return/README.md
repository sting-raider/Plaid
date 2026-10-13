# TLB writers compose with mapped cached execution and return ancestry

Controlled v18 extends the shared original-clock RSP/DMA/CPU/cache/root/return
graph at exact ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04. Run `python run.py`
or `--verify-existing` for retained controls; artifacts stay ignored under
`target/tlb-mapped-cache-root-return-primary`.

Two actual decoded TLBWI operations install the same normalized mapping in slot0
at write325 and332. The observer runs after selected-slot write/synchronize and
before the existing debugger callback. Equal operation332 replaces325 without
changing any table bytes or retiring I-cache fill292. Guest CACHE338 later ends292.
Mapped BREAK345 at VA6028/PA6028 uses332 and raises exception346. Handler LW356/
SPread357 feeds separate CPUwriters362 at6028 and367 at602c. CACHE372 ends343;
EPCread377/XORI381/MTC0writer386/ERET393 selects virtual602c. First mapped returned
fetch395/fill397/decoder399 uses332 and separate executable writer367 ancestry.
Handler/return execute naturally without host PC setters; pre-trap controlled
TLB instruction entries retain explicit opaque CPU roots.

Complete400-event source and independent full graph agree. Baseline/disabled/
enabled/repeat agree on45 CPU steps and63 complete reported machine/cache/CP0/
pipeline/TLB/staged controls; enabled source exact. All32 entry fields are passive
getters; no Random-register queries. Fingerprints derive from normalized entry
bytes, not arbitrary digest labels. Original ordinals are retained within this
capture; earlier v0-v17 sources/reports remain byte-exact compatibility receipts.

Mapped fetches require current raw table/ASID/kernel32 context, unique matching
low-region4KiB entry, valid CCA3 and exact translated physical address. Invalid
matches also count for ambiguity. No TLBWI generation before completed decoder,
no initial valid entry recovered without an actual writer, and no ignored mapping
metadata on uncached/foreign rows. TLB writes preserve I-cache eligibility.

Pin-specific scope and matching virtual/physical colors only. Retain ares/Gopher
synonym index-source disagreement. General replacements/ASID/TLBR/TLBWR/context/
geometry/endian/reset/restore/census/root/lifetime/whole-ROM/native remain OPEN;
all flags false, static ERET unsupported. No upstream implementation copied/linked.
