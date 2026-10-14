# Reverse SP DMA carries computed SP writers into RAM executable bytes

Raw v11 adds exact reverse-SP-DMA (DMEM/IMEM -> RDRAM) source reads and their
completed RAM sinks to the original PI/SP/fetch clock. Each source read freezes
the shared SP writer parents of its bytes at the read ordinal; the sink must be
the immediately preceding identity-RAM scalar write (device 4) with the same
address, width, value, context and PC. Completed sinks install computed byte
chains in RAM; a later CPU executable read or cached fill can select them.

Computed writers are never relabelled as PI/ROM origins: `fully_attributed_
fetches` stays zero for these bytes. Any later RAM storage effect or full backing
cut revokes the computed chain, including equal values; mutations after the
actual CPU read keep that read's frozen parents. SP mutations after the DMA read
do not alter the already-frozen copy, while mutations before it do.

`test_consumer.py` builds the complete synthetic graph rooted ORI -> scoped SW
-> DMEM writer -> reverse DMA -> RAM -> CPU executable fetch and checks both
consumers against the independent `verify.py` replay and digest, plus cuts on
either side of the read and RAM sink. `run.py` builds the pinned ISC ares oracle
with and without the sensor and requires identical machine/backing checkpoints
for baseline, disabled, enabled and repeat runs, then validates every actual
DMEM (Word pair) and IMEM (Dual) reverse-DMA read/sink pair.

Paused by ADR-0125: no further RSP-side composition until an OoT blocker or the
synthetic native slice requires it. Task/reset roots, vector producers, writer
census, lifetimes and whole-ROM/native closure remain OPEN; all broad
certification flags stay false.
