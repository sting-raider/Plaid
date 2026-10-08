# RSP-originated stores remain in DMEM at the tested pins

Status: **VALIDATED for the bounded primary fixture**, 2026-10-09.

Recovered original in-progress fixture from `research/rsp-self-store-imem-gpt56sol`
at `41fc9b6`. Unlike CPU-visible SP memory routing, ordinary RSP scalar/vector
store handlers write the separate 4-KiB DMEM object; bit 0x1000 does not select
IMEM in that data path. RSP instruction fetch uses the separate IMEM object.

The initial primary execution failed the fixture's blanket nonzero-mutation
assertion for `SRV@0x1000`. Exact pinned SRV writes `address & 15` bytes, so an
aligned address legitimately writes zero. The fixture now requires that case to
preserve both banks rather than omitting it or pretending it mutated. All other
27 decoded probes must change DMEM, and all 28 must preserve every IMEM byte.

Executed against ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` with both
recompilers disabled, using original synthetic vector/scalar payloads and actual
instruction decoding followed by BREAK. The four scalar probes cover SB at bit
12, SH at 0xfff, unaligned SW wrapping at 0xffe and SW at bit 12. All 12 vector
store families execute at 0x1000 and 0xfff. Repeated JSON is byte-identical.

Result SHA-256:
`440637fc28ad84e7b047c29c2eebb1a0723453cc66ef9c613f48e5536c7c9ec0`.
Driver SHA-256:
`e66655cfe985cd82437b2c5519323714c0b6607912c8c644216237759b4ed6e1`.

Exact source guards cover every scalar/vector handler and separate memory/fetch
objects. Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7` independently masks
RSP stores into the lower 4 KiB of its combined SP image. n64-systemtest
`196f5421173220eb2f63a7a99c64795dc0ea0698` encodes scalar wrap and vector address
expectations. These independent comparisons are source-only, not fresh emulator
or physical hardware executions.

Adopt the bounded address-domain distinction: ordinary RSP-originated stores
cannot be assigned a CPU-to-IMEM sink merely from bit 12. DMEM can still carry
code/data later copied by CPU/SP DMA, which needs a separate observed lineage.
CPU writes, SP DMA, debugger/reset/restore and general IMEM lifetime remain
mutation obligations. This test does not prove all RSP behavior, reachability,
full state neutrality or whole-ROM closure. The reference itself is unmodified;
licensed upstream builds and all generated results stay ignored.
