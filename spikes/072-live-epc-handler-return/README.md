# Live EPC generation composes with continuous handler and returned code

Original controlled v15 extension of spike071 at exact ISC ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. Run `python run.py`; use
`--verify-existing` to recheck controls without rebuilding. Outputs stay ignored
under `target/live-epc-handler-return-primary`.

After actual BREAK331/transfer332, handler NOP338 executes at the derived root.
Its next instructions execute naturally without host PC setters: SP LW342/read343,
SW347/RAMwriter348 replaces BREAK with NOP, CACHE352/invalidation353 ends fill329,
then ERET357/transfer358 selects the live exception-produced EPC. First returned
fetch360/burst361/fill362/decoder364 consumes NOP with fresh CPUwriter348 ancestry.
The returned target is the selected current EPC generation, not an equal old label.

Baseline/disabled/enabled/repeat agree on39 CPU steps and57 complete reported
machine/cache checkpoints. They include all512 I-cache tuples plus EXL/ERL/BEV/
IE/LLbit/address mode and CPU pipeline state. Enabled sources repeat exactly;
independent complete source/image/register/cache/root/return/parent graph matches
Rust. Exact pinned guards include EPC selection, EXL/LLbit effects and prior
exception/cache/DMA contracts.

Only a live uncut exception frame, ERL0/kernel32/IE0 ERET and immediate cached
target entry are admitted. Opaque control seeds cut candidate EPC ownership;
unsupported CP0 writers/reset/restore reject. The frame is consumed for this
bounded return scope; physical EPC is not cleared. Existing static discovery
continues to reject ERET. General EPC/ErrorEPC writers, interrupts/ERL returns,
mutation/root/mapping/lifetime and whole-ROM/native coverage remain OPEN.
