# RSP producer graph reaches IMEM DMA installation and RSP consumption

Base:2288305a8247756bdf9cb876aea02467c72b1321. Claim:6127991566.

Reconcile remaining PR29/research/rsp-imem-install-lifetime-gpt56sol Dual IMEM
installation atoms onto the canonical original-clock RSP definition/DMEM/reverse-
DMA/RAM writer/request/CPU execution graph. Reject separate caller-label/value
joins and retain the preceding incomplete-request counterexample. Controlled v6
requires an actual successful Dual RAM read before each exact completed Dual IMEM
sink. Compare its returned bytes to current modeled backing, snapshot all eight
latest byte parents and install per-byte IMEM identities retaining promotion/
read/write/raw physical source. Actual RSP fetched-word consumption keeps those
installed parents. The graph follows both executable paths without flattening
unknown ancestry or inventing an atomic executable residency generation.

The pinned path originally performs read<Dual> -> imem.write<Dual>. Existing
callbacks observe those actual results; no extra guest read, width change or
invented Word split. Direction-specific completion requires every expected Dual
install for IMEM ingress versus two Word writes per DMEM egress block, including
count/skip/row/PBUS wrapping and final endpoints. Opaque equal-valued IMEM writes
cut earlier install parents; equal-valued RAM decoys retain their own unknown roots.

The fixture extends the prefix after CPU execution with real RAM0x6028 ->
IMEM0x300 eight-byte DMA ingress and single-issue execution of the installed NOP.
This changes guest behavior, so a new small unchanged-reference baseline and
sensor are necessary. Baseline/disabled/enabled/repeat agree on all21 independent
machine/timing/exception checkpoints, CPU steps, reported state and full reported
bank/RAM hashes; repeated source exact. No full-machine state coverage is inferred.

Independent COMPLETE142-event census/image/definition/byte-parent/request replay
agrees: six definitions, three CPU IMEM copies, two reverse-DMA Word writes, one
Dual read/install, two promoted requests, eleven CPU fetch/decoder pairs and
eighteen RSP fetched words. Second promotion137 -> read138 -> install139 ->
completion140 -> RSP fetch141/end142 executes NOP at IMEM0x300. Its four parents
retain RAM writer55, whose parents are RSP stores33..36/context32/definition30.
The other installed word retains writer56's opaque initial DMEM roots and is not
executed. Initial IMEM0x300 is already zero; equal bits still receive a new writer.

Source SHA256:
4a7a17b616a835b465764fbaf6f64718a0693b560d47dda569b51ec45bafd1b1.
Report SHA256:
d92545cafd00535adef9b28a3fe7d77c114a57385d64539b578e91f837b173c7.
All six v0-v5 reports remain EXACT; prior v5:
344789d2e2c288c91f79e113a7c19ac4b1e4001b0b8aa3b4a4ad9e22ee8c9b4a.

Focused24, actual/synthetic CLI, complete source/report rechecking and independent
graph comparison PASS. Adversaries include missing/duplicate/reordered read/sink,
descriptor/bank/address/payload/parent/direction forgeries, incomplete declared
progression, equal decoy and opaque replacement cuts, mixed roots, count/skip/wrap
and report deletion. Complete multi-Dual count/skip/wrap progression retains actual
install ordinals. Exact clean ares9408cb43d4948fc3ea6e152a307a34348df3fe04 and its
DMA/RDRAM/layout source guards remain the reference boundary, with ISC notices.
No upstream implementation or branch-only workflows are imported; no Actions.
Full local fmt, strict locked workspace/all-target Clippy, locked workspace tests,
canonical CLI and diff gate PASS with two build jobs. No checks skipped or source
obligation weakened; older source compatibility uses retained evidence.

PR29's core install/lifecycle rules are semantically reconciled into the stronger
source graph, with its looser grouping verifier rejected. Raw histories are not
wholesale merged. Mutable pending/accepted request/FIFO policy, DMEM ingress,
broader scalar/vector actors, general mutation/hardware/cache/TLB/reset/restore/
continuous lifetime and whole-ROM/native remain OPEN. All certification flags
stay false. No progress milestone, ROM/assets or native fallback. Generated
controls/source/reports stay ignored under target/dma-ram-imem-roundtrip-primary
and target/dma-roundtrip-integration-primary.
