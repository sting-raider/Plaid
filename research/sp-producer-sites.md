# Observed CPU/SP producer sites in the bounded boot prefix

Hypothesis: complete source-bound SP chronology can identify observed writer
sites without claiming register dataflow or ultimate byte provenance.

The strict v3 report was fully reconstructed against its raw source. The new
inventory independently checks the complete source SHA-256, consecutive raw
ordinals and footer before joining each CPU SP Word store to the most recent
same-PC fetched instruction. These are observed sites, not a retirement or
source-dataflow certificate. The fixed trace contains no unmatched writer site.

The 610,000-call prefix has 54,253 normalized CPU SP stores: 3475 to DMEM and
50,778 to IMEM. There are 69 distinct PC/instruction/bank sites. The fetched
opcodes at those sites account for 51,991 SW stores, 2256 SB stores and six COP1
SWC1 stores. The callback observes the actual full-Word SP sink even for SB;
these counts are effects, not nominal opcode widths or hardware atomicity.

An integer-SW-only producer census would miss the subword and FPR stores.
Instruction matching alone cannot identify the source register's origin, prove
retirement, or establish memory immutability. FPR producers require the already
validated FR-sensitive semantics, and same-value stores remain separate events.

All 512 observed DMA stores target IMEM and retain unknown source receipts
because their DRAM addresses exceed the declared 8-MiB backing. Ordinary RSP
DMEM writes are a separate producer domain requiring actual execution contexts.
Reset/restore, host mutation and general coverage remain open.

Raw source SHA-256:
`1a5873ca62b802ceecdaa2da4cc21e246b9cab9bdc792d89fa41a90774c620dd`.
Inventory result SHA-256:
`4c5b0c24cf4e4e5fc4b2dca380a9cd8f49ba449867922288c2cd1819d0d7ad2c`.
Run `python spikes/040-ares-boot-sp-history/inspect_producers.py`; raw data and
result remain ignored. All mutation/lifetime/native certification flags are false.
