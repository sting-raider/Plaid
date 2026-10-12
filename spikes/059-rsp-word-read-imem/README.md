# Actual RSP word reads through register definitions into IMEM

Extend the canonical arithmetic prefix on the same complete source clock with
an RSP SW, actual LW and ADDU before the existing DMEM -> CPU -> IMEM copy. The
read observes the original `readUnaligned<Word>` return once, before register
assignment. No extra guest access, changed opcode/width or fabricated full GPRs.
Baseline/reference behavior remains unchanged by default when read sensing is off.

```sh
python spikes/059-rsp-word-read-imem/run.py
python spikes/059-rsp-word-read-imem/run.py --verify-existing
python scripts/test_rsp_definitions.py --word-reads --source target/rsp-word-read-imem-primary/source.json
```

Retain plain, disabled, enabled and repeated outputs and all sixteen independent
machine/timing/exception checkpoints, CPU steps and final full bank/RAM hashes.
The independent complete census expects79 events and six definition nodes.
The LW keeps four distinct captured byte parents and its actual read ordinal;
same bits from a decoy location or a missing read cannot supply that link.
Reentry still clears tags even when payloads repeat.

The v2 profile is controlled/non-interleaved and supports only this direct DMEM
LW extension. Incoming data/instruction roots, general mutation census, DMA/cache/
TLB/restore interleavings, IMEM execution/lifetime and native/whole-ROM closure
remain uncertified. Legacy v0/v1 sources and report bytes stay compatible.
All generated reference shadows/captures remain ignored, with ISC notices.
