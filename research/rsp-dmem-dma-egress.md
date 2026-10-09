# RSP DMEM producer lineage through SP write-DMA

Date: 2026-10-09

Status: **IN PROGRESS**

Branch: `research/rsp-dmem-dma-egress-gpt56sol`

## Question

Can actual decoded RSP DMEM store effects be causally exported through a real
SP write-DMA into exact RDRAM byte mutations without relying on payload equality,
while preserving same-value writer generations, partial/vector coverage, CPU
overwrite boundaries, multi-row skip, and 4 KiB DMEM wrap?

## Hypothesis

For exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, a
completed identity-RDRAM `RBusDevice::SP_DMA` Word write can inherit the latest
ordered DMEM writer identities for its four source bytes when all of these are
true:

1. the SP DMA is a stable current write transfer targeting DMEM, not IMEM;
2. the completed RDRAM-write callback occurs inside the exact current fragment;
3. source DMEM offsets are derived from the current descriptor and destination
   lane, not from matching values;
4. DMEM writer generations come from measured completed sink effects;
5. any intervening CPU/SP mutation replaces the covered byte writers before the
   DMA export.

A same-value RSP store must still advance writer identity. Missing/unclassified
DMEM history or a RDRAM effect that cannot be joined to the current descriptor
must remain unknown.

## Exact source contract inspected before execution

Pinned ares `ares/n64/rsp/dma.cpp` performs the DMEM write-DMA branch as two
`dmem.read<Word>` calls followed by two `rdram.ram.write<Word>` calls tagged
`RBusDevice::SP_DMA`; only afterward does it increment current DRAM/PBUS
addresses. `ares/n64/rsp/io.cpp` commits SP write-DMA direction through
`SP_WRITE_LENGTH`. `ares/n64/rdram/rdram.hpp` performs an ordinary identity-RAM
write and hidden-RAM update before the existing successful scalar observer hook
used by Plaid research. The source guard pins exact file hashes and snippets.

This supports a causality test stronger than value matching: at the completed
RDRAM effect, the observer can derive source DMEM offset from the still-current
DMA descriptor. The emitted value is checked only as an integrity assertion
against replayed source bytes.

## Fixture

Durable spike: `spikes/043-ares-rsp-dmem-dma-egress/`.

Planned executed chronology:

1. explicit 4 KiB initial DMEM byte pattern;
2. decoded same-value scalar `SB` at `0x040`;
3. decoded scalar `SW` at `0x044`;
4. decoded vector `SDV` at `0x048`;
5. CPU-origin SP-memory word overwrite at `0x04c`;
6. two-row write-DMA from `0x040..0x04f` to DRAM rows `0x1000` and `0x1010`
   with an eight-byte DRAM skip;
7. decoded unaligned `SW` at `0xffe`, wrapping into `0x000`;
8. 16-byte write-DMA from `0xff8`, wrapping source to `0x000`, into DRAM
   `0x2000..0x200f`.

The replay verifier starts with the explicit byte snapshot, applies only observed
completed DMEM sinks in order, and snapshots those byte writers at each completed
DMA-backed RDRAM effect. It also mutates measured histories adversarially and
requires rejection.

## Execution receipt

Pending exact-pin CI execution.

## Result

Pending. Allowed final state will be one of VALIDATED / REJECTED / PARTIAL /
BLOCKED based on executable evidence; no success conclusion is claimed yet.

## Explicit non-claims

This slice does not prove hardware timing/atomicity, exhaustive RSP mutation
coverage, DMA reachability, RDRAM-to-executable copying, overlay lifetime,
instruction-cache visibility, or whole-ROM closure. SP -> RDRAM is only a
producer-export step; later executable use requires its own causal joins.
