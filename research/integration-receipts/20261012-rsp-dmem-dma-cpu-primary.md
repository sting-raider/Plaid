# Original-clock RSP producer graph reaches CPU execution through DMA

Base:db4706868e68b553ca53d2bd6577caa8b8ab8f79. Claim:6125268595.

Reconcile PR37/direct-integration/rsp-dmem-egress-gpt56sol-direct-rsp-dmem-egress-
20261011-c3 and research/rsp-dmem-dma-egress-gpt56sol's validated descriptor-selected
byte-parent invariant with the canonical full-snapshot RSP definition/IMEM graph.
Reject a caller-only label/value bridge between the separate prepared histories.
Controlled v4 records each completed successful reverse-DMA RAM Word write with
the current descriptor, selects its DMEM lanes before checking payload and keeps
every RSP definition/writer or unknown byte parent. Equal-valued writes advance
identity; an unknown writer cuts only its touched lanes.

The same source clock includes actual CPU uncached fetch begin/read/end followed
by decoder begin/end and full GPR snapshots. The read must match current modeled
backing bytes, the fetch result must match that completed read, and the immediate
decoder must match the exact fetched PC/word. Retain raw read/write/decoder IDs,
full4096-byte DMEM/IMEM and the explicit bounded48-byte identity-RAM snapshot.
All eleven CPU code roots are checked; initial code remains opaque. No fabricated
Word split, extra guest read or virtual/backing/cache identity substitution.

After the existing RSP SW/LW/ADDU/store chain, a real eight-byte reverse SP-DMA
exports DMEM0/4 into RAM0x6028/0x602c. The CPU later fetches and executes the
exported legal NOP at its next sequential PC. Initial RAM0x6028 is already zero,
so actual write identity is necessary despite equal bytes. Baseline/disabled/
enabled/repeat agree on all19 independent machine/timing/exception checkpoints,
CPU steps, reported state and full reported bank/RAM hashes; repeated source exact.
Independent COMPLETE134-event census and byte-image/parent replay agree on six
definitions, three CPU IMEM copies, two DMA Word writes, eleven CPU fetch/decoder
pairs and seventeen RSP fetched words. No full-machine state coverage is inferred.

DMA write54 to RAM0x6028 keeps RSP stores33..36/context32/definition30. CPU fetch
context130/read131 consumes those four DMA byte writers, then decoder133 executes
word0. DMA write55 exports the second word with opaque initial DMEM parents;
that word is not executed. Both write occurrences remain separate from accepted
request/completion lifetime and hardware atomicity.

Source SHA256:
0e6d95cb879272bbf123981d6c8fe91753ddcf8fe456abefdbe450c09714fc9b.
Report SHA256:
bc71405ad5a1c0e69a8465b95d36864c6e627df8f80b59d36d02bd6b4bd347c8.
V0/v1/v2/v3 actual reports remain EXACT respectively:
2dc31e222304cb1818d863bb3134eb3bf4dc76eb7885057f813899aa77005896;
e32c0d7fc7860210a1a4c8dc01adf9087486c246166178438737bd8417dbde9a;
d4d49f277965ecb207ab611581eb51e97da6c495c7101d83f853d63c08a6e3b4;
387a1c8e787543dfbb2852a48f73bcbae2c8a4ad4c396afbd18f0e41e2bf0775.

Focused16 and actual/synthetic CLI/source/report rechecking and independent graph
comparison PASS. Adversaries cover descriptor/bank/source/payload/order, missing/
duplicate reads after full reclocking, cached/decoy fetches, forged decoder/writer/
definition parents, contradictory snapshots, equal unknown replacements and mixed
byte ancestry. Exact clean ares9408cb43d4948fc3ea6e152a307a34348df3fe04 source
guards retain prepared DMA/RDRAM/layout checks using canonical Git hashes rather
than Windows line endings. Existing callbacks observe actual completed values
without extra guest access. ISC reference/shadow notices preserved; no upstream
implementation import, branch-only CI or Actions execution.
Full local fmt, strict locked workspace/all-target Clippy, locked workspace tests,
canonical CLI and diff gate PASS with two build jobs. The retained reference run
rechecks without rebuilding; no tests skipped or proof obligation weakened.

PR37's core descriptor-selected DMEM egress invariant is semantically reconciled
onto the stronger canonical source graph; its raw selected-register module is not
merged. Broader scalar/vector widths and complete producer/consumer coverage remain
pending. This profile does not certify general mutation census, SP request/lifecycle,
asynchronous actors, cache/TLB/reset/restore lifetime, hardware consensus, whole-ROM
or native completeness. All corresponding flags stay false. No progress milestone,
ROM/assets or new broad native architecture. Generated controls/source/reports stay
ignored under target/rsp-dmem-dma-cpu-fetch-primary and target/rsp-dma-integration-primary.
