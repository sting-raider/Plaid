# Spike 043: RSP DMEM writer lineage through SP write-DMA

Status: **IN PROGRESS / claimed in issue #4**.

This bounded exact-pin experiment asks whether actual decoded RSP DMEM sink
effects can be exported through a real SP write-DMA (SP memory -> RDRAM)
without inferring provenance from matching payload values.

The fixture composes existing, independently validated observation primitives:

- actual RSP instruction begin/end context plus completed primitive DMEM writes;
- completed identity-RDRAM scalar writes with `RBusDevice::SP_DMA`;
- the exact pinned ares current SP-DMA descriptor, read only by the observer at
  the completed RDRAM-write callback.

Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` performs each DMEM
write-DMA fragment as two `dmem.read<Word>` operations followed immediately by
two `rdram.ram.write<Word>(..., RBusDevice::SP_DMA)` operations, and advances
the current PBUS/DRAM addresses only after those writes. Therefore the observer
can derive the exact source DMEM offset from the nested current descriptor when
the successful RDRAM effect fires. Payload bytes are checked only afterward for
trace integrity; they are not used to select an origin.

The adversarial fixture contains:

- a same-value decoded RSP `SB`, which must still create a newer writer;
- a decoded scalar `SW`;
- a decoded vector `SDV`;
- a later CPU-origin SP-memory word write that replaces four of the vector
  writer bytes;
- a two-row write-DMA with DRAM skip, proving one request can export distinct
  byte origins across rows;
- an unaligned decoded RSP `SW` crossing `0xfff -> 0x000`;
- a 16-byte write-DMA beginning at DMEM `0xff8`, proving source lineage wraps
  within the 4 KiB bank;
- forged histories that delete or relabel writers or corrupt source/descriptor
  identity and must fail closed.

`run.py` builds an unchanged-reference baseline and an observer-capable exact-pin
build, then compares baseline, observer-disabled, observer-enabled, and repeated
enabled architectural state. Generated upstream shadows remain under `target/`
and are never committed.

Reproduce after fetching the exact ares pin into `.refs/ares`:

```bash
python3 spikes/043-ares-rsp-dmem-dma-egress/source_guard.py
python3 spikes/043-ares-rsp-dmem-dma-egress/run.py
```

The experiment is reference-implementation evidence, not a hardware timing
oracle or a whole-ROM closure proof. It does not claim that all possible DMEM
writers have been observed, nor does SP -> RDRAM by itself make bytes executable.
Its purpose is to validate or reject one causal producer-export link that later
copy/overlay provenance may compose with executable consumers.
