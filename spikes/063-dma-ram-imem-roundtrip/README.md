# RSP producer through RAM and IMEM DMA back to RSP execution

Extend the canonical promoted-DMEM/CPU execution prefix with actual eight-byte
RAM0x6028 -> IMEM0x300 DMA ingress and one single-issue execution of the installed
NOP. Capture the existing successful Dual RAM read and completed Dual IMEM sink
separately; no extra read or invented Word split. Each installed byte retains the
actual read/install/promotion IDs, physical RAM address and current RAM writer.

```sh
python spikes/063-dma-ram-imem-roundtrip/run.py
python spikes/063-dma-ram-imem-roundtrip/run.py --verify-existing
python scripts/test_rsp_definitions.py --roundtrip --source target/dma-ram-imem-roundtrip-primary/source.json
```

This new guest behavior requires a new small baseline and sensor. Plain, disabled,
enabled and repeat must agree on twenty-one independent machine/timing/exception
checkpoints, CPU steps, reported state and full reported bank/RAM hashes. The
independent COMPLETE142-event census/image/parent/request replay expects six
definitions, three CPU IMEM copies, two reverse-DMA Word writes, one actual Dual
RAM read/install, two promoted requests, eleven CPU fetch/decoder pairs and
eighteen RSP fetched words. Read138 -> install139 -> RSP fetch141 retains RAM
writer55, which links back to RSP stores33..36 and definition30. The second
installed word retains writer56's opaque DMEM roots and remains unexecuted.

Dual ingress completion counts one actual install per eight-byte block; DMEM
egress counts two actual Word writes. Exact descriptor count/skip/row/wrap/end
progression is required for each direction. Equal RAM decoys and opaque same-value
IMEM overwrites cannot inherit old parents. V0-v5 reports stay exact.

The declared identity-RAM/direct controlled prefix is not a general mutation,
DMA/FIFO/hardware/cache/mapping/reset/restore or executable-lifetime census.
Whole-ROM/native closure and all certification flags remain OPEN/false. Captures,
reference shadows and binaries stay ignored under target with ISC notices.
Only compiler-time reference execution is involved; no native fallback is added.
