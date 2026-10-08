# ares RSP IMEM provenance

Hypothesis: on pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, a successful
identity-mapped `RBusDevice::SP_DMA` RDRAM read can be joined to the immediately
following IMEM write and then to a later interpreter RSP fetch, but the join must
be generation-sensitive and fail closed when the backing read did not succeed.

Run:

```bash
python3 spikes/018-ares-rsp-imem-provenance/run.py
```

The runner builds an untouched baseline with the existing spike-003 recipe, then
a separately generated observer build. The observer samples only already-completed
operations: successful ordinary RDRAM reads, RDRAM-to-IMEM DMA writes, direct IMEM
writes, and words already fetched by the interpreter. It makes no extra guest
memory/bus accesses. The pinned ares checkout must remain clean.

Adversarial fixture coverage:

- initial 16-byte RDRAM -> IMEM load and fetch;
- byte-identical reload from a different RDRAM address into the same IMEM range;
- changed reload into the same IMEM range;
- count/skip DMA proving `0x4008` poison is skipped and `0x4010` supplies the second block;
- RDRAM -> DMEM transfer, which must never become an IMEM provenance write;
- direct CPU write to IMEM, which must supersede DMA lineage;
- out-of-bounds SP DMA read, which writes zero to IMEM but supplies no successful
  RDRAM backing-read witness and therefore must resolve as unknown.

The script requires exact repeated traced JSON and exact baseline/traced emulator
state equality before accepting any provenance result.

## Verdict

Pending execution on the isolated research branch. Do not promote this spike into
a ProgramMap identity rule until the result section records the executed evidence.
