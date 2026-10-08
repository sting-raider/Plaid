# RSP IMEM executable provenance

Date: 2026-10-08

Status: EXPERIMENT IN PROGRESS

## Falsifiable hypothesis

For the pinned ares revision, controlled identity-mapped RDRAM -> RSP IMEM DMA can
produce an exact byte-origin witness if and only if Plaid observes both the
successful backing RDRAM read and the completed IMEM write in one chronology.
Each completed IMEM write creates a new resident generation even when the bytes
are identical to the previous generation. A fetch may inherit origin only from
the latest generation covering all fetched bytes. Direct IMEM writes replace that
lineage, DMEM transfers cannot explain IMEM fetches, and an IMEM write caused by
an unsuccessful/out-of-bounds RDRAM read must remain source-unknown.

## Exact upstream source map

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

- `ares/n64/rsp/dma.cpp::RSP::dmaTransferStep`: IMEM DMA reads a `Dual` from
  `rdram.ram.read<Dual>(..., RBusDevice::SP_DMA)` and writes that exact value to
  `imem.write<Dual>(...)`. DMEM DMA instead performs two 32-bit RDRAM reads and
  two DMEM writes.
- `ares/n64/rsp/rsp.cpp::RSP::instruction`: interpreter execution fetches directly
  from `imem.read<Word>(ipu.pc)` (and may fetch `ipu.pc + 4` for dual issue), then
  calls `instructionPrologue` with the already-fetched word.
- `ares/n64/rsp/io.cpp::RSP::writeWord`: direct writes targeting the IMEM half of
  SP memory invalidate the RSP recompiler range and write the supplied word into
  IMEM independently of SP DMA.
- `ares/n64/rdram/rdram.hpp::RDRAM::Writable::read`: in identity mode, an
  out-of-range access returns zero before the underlying `Memory::Writable::read`.
  Therefore a DMA-side destination write alone cannot prove a successful backing
  transaction.

Existing `spikes/016-ares-rdram-bursts` does not cover this path: SP DMA uses the
ordinary templated RDRAM `read`, not `readBurst`.

## Architectural implication under test

The current ProgramMap `Microcode { sha256, imem_start, size, evidence }` is not,
by itself, a lifetime/provenance identity. Same bytes can be reinstalled at the
same IMEM address from a different RDRAM origin, and direct CPU IMEM writes can
supersede part of a prior DMA installation. A future executable-universe proof
needs chronology/generation plus byte origin, not only a content hash.

## Experiment

`spikes/018-ares-rsp-imem-provenance/` builds baseline and generated-observer ares
binaries. The observer records only successful ordinary RDRAM reads, completed
IMEM DMA writes, direct IMEM writes, and already-fetched interpreter words. A
separate Python reducer reconstructs per-byte latest-writer generations and
requires exact byte equality before assigning a fetch source.

Executed result, hashes, limitations and recommendation will replace this section
before CLOSEOUT.
