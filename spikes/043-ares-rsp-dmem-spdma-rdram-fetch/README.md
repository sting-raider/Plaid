# RSP DMEM -> reverse SP DMA -> RDRAM -> CPU fetch

Status: **VALIDATED** bounded exact-pinned ares interpreter fixture.

Primary receipt: GitHub Actions run `37916462499` at research head
`94203baaaf70b2d45974e23b67b9a3b6326ec5e5`, `results.json` SHA-256
`f443d1c594e199e15aba2f805f630659f527cad3e2824f148ae83d870f2eb5d8`.

Hypothesis: in the controlled interpreter scope, byte provenance from actual decoded
RSP DMEM stores can be carried through an actual SP write-DMA into RDRAM and then
into a later uncached VR4300 instruction fetch only by joining ordered storage
facts. Address/value equality is insufficient.

The fixture composes three already-established observation boundaries:

1. decoded RSP instruction contexts plus primitive completed DMEM sinks;
2. ordinary RDRAM scalar effects, including `RBusDevice::SP_DMA` writes;
3. CPU fetch begin/end boundaries plus the exact `VR4300_UNCACHED` RDRAM read.

The exact pinned ares `rsp/dma.cpp` reverse-DMEM path reads two current DMEM words
into local `dataLo`/`dataHi` values and immediately writes those same locals to
RDRAM with requestor `SP_DMA`. The source guard requires that source shape and the
current-descriptor promotion path to remain unchanged. No extra guest read is
introduced by the observer.

Cases:

- `rsp_sw_dma_fetch`: decoded RSP `SW` creates `ORI t0,zero,0x1234`; reverse SP DMA
  copies it to RDRAM and an uncached CPU fetch executes it.
- `same_value_latest_writer`: two equal decoded RSP `SW` instructions produce two
  distinct four-byte primitive writer contexts. Replay must retain the second
  writer context even though backing bytes never differ.
- `partial_byte_lineage`: decoded RSP `SB` changes only byte 3 of an existing
  instruction from immediate `0x1234` to `0x1256`; the other three fetched byte
  roots must remain the explicit initial snapshot.
- `same_value_cpu_overwrite`: after DMA, a decoded uncached VR4300 `SW` writes the
  same word through the real CPU memory path. The later fetch must root in that
  CPU write, not the older SP-DMA/RSP chain.

`verify.py` replays per-byte origins and rejects seven measured-history forgeries:
latest equal-writer deletion, DMA destination drift, partial-store payload drift,
post-DMA CPU destination drift, fetch-read payload drift, fetch physical-address
drift and an orphaned RSP context.

Run:

```bash
python3 spikes/043-ares-rsp-dmem-spdma-rdram-fetch/run.py
```

The runner builds an independent uninstrumented baseline, a generated sensor build
with callbacks disabled, an enabled sensor build and a repeated enabled run. Full
reported machine digest and case outputs must match across all four; repeated
instrumented stdout must be byte-identical.

This does **not** prove reverse-DMA timing on hardware, arbitrary multi-row/wrapped
transfers, restore/reset identity, RSP recompiler behavior, ultimate producer
origin before the measured DMEM snapshot, or whole-ROM mutation completeness.
It establishes only this controlled causal composition at the exact pinned ares
revision. Transfer identity still follows the separately validated current/pending
lifecycle rules; a length-register write is not treated as completion.
