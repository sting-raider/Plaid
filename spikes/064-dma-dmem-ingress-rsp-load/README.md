# Actual DMEM DMA ingress feeds an RSP load definition

Extend the canonical round trip with promoted RAM0x6028 -> DMEM0/4 ingress and
one performed RSP LW. The pinned DMEM path reads both source Words before either
destination store. Observe each existing returned read and lower completed DMEM
Word effect once; suppress the duplicate higher callback. No extra guest read,
invented split or nearest-value association.

```sh
python spikes/064-dma-dmem-ingress-rsp-load/run.py
python spikes/064-dma-dmem-ingress-rsp-load/run.py --verify-existing
python scripts/test_rsp_definitions.py --dmem-ingress --source target/dma-dmem-ingress-rsp-load-primary/source.json
```

The independent COMPLETE152-event census expects seven definitions, three
promoted requests, two DMEM ingress Word stores, one Dual IMEM install, eleven
CPU fetch/decoder pairs and nineteen RSP fetched words. Read144/145 precedes
store146/147; actual RSP load151/context150 keeps store146/read144/RAMwriter55
parents. The other lane retains store147/read145/RAMwriter56 independently.
Plain, disabled, enabled and repeated runs agree on twenty-three independent
machine/timing/exception checkpoints, CPU steps, reported state and full reported
bank/RAM hashes. New guest behavior requires a new small baseline/sensor.

Typed promotion/completion distinguishes DMEM egress, IMEM ingress and DMEM
ingress. Full descriptor-derived count/skip/wrap/end progression remains required.
Missing successful reads and unsupported failed/OOB sources cannot provide
successful-source ancestry. Equal-valued read lanes retain their own identities.
V0-v6 source/report contracts remain compatible.

General producer/mutation census, pending/FIFO/hardware/cache/mapping/reset/
restore/lifetime coverage and whole-ROM/native closure remain OPEN. All flags
stay false. Generated reference shadows/binaries/captures remain ignored under
target/dma-dmem-ingress-rsp-load-primary, preserving ISC notices. No Actions.
