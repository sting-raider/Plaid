# RSP DMEM through reverse DMA into actual CPU execution

Reconcile PR37's descriptor-selected DMEM byte-parent invariant onto the
canonical full-snapshot RSP definition/IMEM-consumption clock. After the RSP
LW/ADDU/store prefix, actual eight-byte reverse SP-DMA exports DMEM0/4 into
RAM0x6028/0x602c. The CPU later fetches and executes the exported legal NOP at
its next sequential PC. Equal zero bits intentionally require the actual DMA
writer identity to replace the initial opaque seed.

```sh
python spikes/061-rsp-dmem-dma-cpu-fetch/run.py
python spikes/061-rsp-dmem-dma-cpu-fetch/run.py --verify-existing
python scripts/test_rsp_definitions.py --dma --source target/rsp-dmem-dma-cpu-fetch-primary/source.json
```

Capture two separate successful RDRAM Word callbacks with the current DMA
descriptor, actual uncached CPU fetch begin/read/end, then decoder begin/end and
full GPR state. Original callbacks consume existing values without extra guest
reads. Full4096-byte DMEM/IMEM and a declared48-byte RAM span are independently
replayed. Each exported byte retains its RSP definition/writer or unknown parent;
each fetched byte retains its exact backing writer, separately from the decoder.

The independent complete census expects134 events, six definitions, two DMA
Word writes, eleven CPU fetch/decoder pairs and seventeen RSP fetched words.
Baseline, disabled, enabled and repeated runs must agree on nineteen independent
machine/timing/exception checkpoints, CPU steps, reported state and full bank/RAM
hashes. Legacy v0-v3 histories/reports/default fixture behavior remain compatible.
The exact-pin source guard reuses the prepared DMA/RDRAM/layout contract with Git
canonical hashes so Windows line endings do not change source identity.

The profile is bounded identity-RDRAM/direct KSEG1, single-clock and controlled.
It does not establish a general writer census, atomic DMA generation, accepted
request/completion lifetime, cached/mapped consumption, asynchronous actors,
reset/restore epochs, hardware consensus or whole-ROM/native closure. All
certification flags stay false. Reference shadows/binaries/captures stay ignored
under target/rsp-dmem-dma-cpu-fetch-primary with ISC notices. No Actions.
