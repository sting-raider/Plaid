# PI RAM ancestry through SP DMA to CPU SP consumption

The canonical SP/PI consumer previously discarded SP records even when its
validated projection retained a unique DMA read/store receipt. The synthetic
reproduction had a compatible SP writer but no PI ancestry for its CPU fetch.

The existing PI state now freezes RAM parents at that exact read, then uses the
validated receipt to install them with the SP writer occurrence. Selection and
contradiction revocation reuse `sp_history::WriterLineage`. An equal unscoped SP
write replaces the writer; later RAM changes cannot rewrite an earlier read.
Partial parents stay partial. Missing or ambiguous reads supply no ancestry.

After building the CLI, run:

```text
python spikes/089-pi-dma-sp-consumption/test_consumer.py
python spikes/089-pi-dma-sp-consumption/run.py
python spikes/089-pi-dma-sp-consumption/run.py --verify-existing
```

The consumer contract compares Rust with the independent Python replay and
retains fourteen timing, overwrite, contradiction, ambiguity and missing-parent
controls, plus three forged installation/read identity controls. Existing SP
writer and PI storage regressions remain applicable.

The actual pinned ISC ares fixture extends spike088 with a real Dual RAM read,
SP DMA installation into IMEM and CPU instruction execution from uncached SP.
Identity and translated PI destinations both feed the chain. Its 116 events and
twelve checkpoints compare baseline, disabled, enabled and repeat runs, including
complete ordinary/hidden RAM and SP backing hashes plus selected architectural
state. The disabled source stays byte-identical to baseline. Upstream source and
required notices remain in ignored reference builds; no reference implementation
is linked into production.

Descriptor setup, mapping and DMA component stepping are explicit host controls.
This is CPU SP execution, not RSP execution or scheduler/hardware timing proof.
It does not establish guest MMIO/mapping ancestry, a complete writer census,
executable lifetime, whole-ROM closure or native completion. All broad flags
remain false. Local ROM captures and generated reports stay ignored.

New `sp_writer` fields and the v1 SP/PI report identify consumed PI/RAM/SP DMA
chains. Unused paths retain the old v0 report, absent optional fields and digest.
Full retained ROM replays use previously authenticated complete sources without
recapturing the ROM or rebuilding an equivalent emulator.
