# RSP definitions through DMEM and CPU into IMEM

Compose the prepared ORI/ADDU definition invariants with canonical spike047's
actual full RSP/CPU snapshots and one source clock. The optional prefix executes
an ignored zero-register write, two equal ORI definitions and two ADDU definitions
before the existing RSP SW -> CPU LW -> IMEM SW path. The next phase repeats the
same payload from opaque inputs and must not borrow the first phase's definition.
Other mixed/unknown/vector and same-value CPU clobber controls remain intact.

```sh
python spikes/058-rsp-defined-imem/run.py
python spikes/058-rsp-defined-imem/run.py --verify-existing
python scripts/test_rsp_definitions.py --source target/rsp-defined-imem-primary/source.json
```

This requires the exact clean pinned ares reference; Windows delegates to WSL.
Retain baseline, callback-disabled, enabled and repeated outputs, all sixteen
independent machine/timing/exception checkpoints, CPU steps and final full bank/
RAM hashes. An independent complete fixture census checks every captured event
and all definition nodes. Synthetic source/report forgeries exercise the generic
Rust consumer; source and output bytes remain ignored.

The legacy fixture/profile remains unchanged by default. Full before/after
snapshots are already captured; no selected-register input is expanded into a
manufactured full state. Register generations use original begin contexts and
explicit parents; repeated equal definitions stay distinct. Captured incoming
registers and instruction-byte ancestry remain opaque, and reentry clears tags.
No complete mutation census, DMA/cache/TLB/interleaving/restore policy, IMEM
execution/lifetime, hardware consensus, whole-ROM or native closure is claimed.
No upstream implementation or branch-only Actions scaffolding is copied.
