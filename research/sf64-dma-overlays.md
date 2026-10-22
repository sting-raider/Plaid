# Star Fox 64 DMA overlays

## Evidence

The US Rev 1 ROM uses a virtual-to-physical DMA catalog. Its 16-byte entries
contain a logical VROM start, physical ROM start and end, and a compression
flag; the catalog ends with a zero record. Physical files are packed from ROM
offset zero, while VROM keys describe the decompressed address space. The
catalog is found at ROM offset `0xDE480` in this dump. The VROM keys therefore
must not be rejected merely because they exceed the physical ROM length.

Scene records in the main image name an overlay's VROM start and end, followed
by BSS, text, and data bounds. For the executable records, text starts at
`0x80187520`; several distinct overlays share that address. Their data begins
at the end of text, BSS begins at the end of data, and the file's decompressed
length equals text plus data. The decomp source loads the overlay at
`SEGMENT_VRAM_START(ovl_i1)`, obtains physical extents from `gDmaTable`, and
calls MIO0 decompression when `compFlag` is set.

The MIO0 header's decoded size matches the scene VROM span for all nine
overlay entries. For raw catalog entries, the physical span can include
padding; `Load_RomFile` copies the scene-requested length, so analysis must
bound raw bytes by the logical VROM span rather than use the whole physical
extent.

This supports discovering executable files from the ROM's own catalog and
scene descriptors, without title checks, fixed table addresses, or per-game
load declarations. Shared link ranges become content-bound alternate slots;
the native binding still checks the live RAM bytes before dispatch. The
catalog is discovery evidence only and does not close unobserved targets.

## Source and reuse

The research source was the Star Fox 64 US Rev 1 decomp repository at commit
`4235c59f00b04440e3fd5fec49f0bc80e48cf212`. Its repository declares CC0-1.0.
Relevant files are [`fox_load.c`](https://github.com/sonicdcer/sf64/blob/4235c59f00b04440e3fd5fec49f0bc80e48cf212/src/engine/fox_load.c),
[`sf64dma.h`](https://github.com/sonicdcer/sf64/blob/4235c59f00b04440e3fd5fec49f0bc80e48cf212/include/sf64dma.h),
[`dmatable.c`](https://github.com/sonicdcer/sf64/blob/4235c59f00b04440e3fd5fec49f0bc80e48cf212/src/dmatable.c), and
[`overlays.yaml`](https://github.com/sonicdcer/sf64/blob/4235c59f00b04440e3fd5fec49f0bc80e48cf212/yamls/us/rev1/overlays.yaml).
No source code was copied. Plaid's MIO0 decoder is an independent
implementation of the format.

## Validation

The baseline SF64 run reported 296 blockers in closed analysis and 294 with
residual dispatch. Deterministic synthetic tests cover MIO0 literals,
backreferences and malformed bounds, plus catalog-driven discovery of
compressed overlays sharing one link address and raw files with physical
padding. Real-ROM after-counts and native validation are recorded in ADR-0252
once measured.
