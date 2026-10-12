# RAM writer graph reaches actual DMEM ingress and RSP load definitions

Base:bafb49206f9253a085e680a087cd1bafecf9663a. Claim:6128535772.

Compose the retained spike051 successful DMEM ingress/order/decoy source contract
with the canonical original-clock RSP producer/RAM writer/request/IMEM/CPU execution
graph. Controlled v7 explicitly distinguishes DMEM egress, IMEM ingress and DMEM
ingress at actual promotion/completion. The DMEM path performs read Word low,
read Word high, then store Word low/store Word high. Require that actual ordering;
snapshot each returned Word's current RAM parents and bind its exact lower store
before propagating latest DMEM byte parents into a performed RSP LW definition.
Equal values, nearest reads and another lane's parent cannot replace causal identity.

Existing RDRAM return and lower RSP writable callbacks observe the original
operations once. The duplicate higher DMA-store callback is not double-counted.
No extra guest read, invented Word split, fabricated state or raw branch merge.
Full descriptor length/count/skip/row/PBUS-wrap/end progression remains required
for each typed direction. Unsupported failed/OOB or missing successful reads do
not produce successful-source ancestry. Unknown ultimate roots remain explicit.

The fixture extends the prefix with real RAM0x6028 -> DMEM0/4 ingress and one
actual RSP LW. New guest behavior requires a new small baseline/sensor; older
sources supply compatibility without repeat builds. Baseline/disabled/enabled/
repeat agree on all23 independent machine/timing/exception checkpoints, CPU steps,
reported state and full reported bank/RAM hashes; repeated source exact. No
full-machine state coverage is inferred.

Independent COMPLETE152-event census/image/definition/parent/request replay agrees:
seven definitions, three CPU IMEM copies, three promoted requests, two reverse-DMA
Word writes, one Dual IMEM install, two DMEM ingress Word stores, eleven CPU
fetch/decoder pairs and nineteen RSP fetched words. Promotion143 -> reads144/145
-> stores146/147 -> completion148. Actual RSP load151/context150 retains
store146/read144/RAMwriter55 -> earlier RSP stores33..36/context32/definition30.
The second lane independently retains store147/read145/RAMwriter56's opaque
initial DMEM ancestry. Same-value lane identity is not merged.

Source SHA256:
10c810e10226bd722f9d1e7f49e26f2f6eaff8a015482e2f60b750c63b02aefc.
Report SHA256:
1f4b08b05dd910ea06bf06e34bc63377a2b47eab4b8a00d6a6bbf546b9b7aafb.
All seven v0-v6 reports remain EXACT; prior v6:
d92545cafd00535adef9b28a3fe7d77c114a57385d64539b578e91f837b173c7.

Focused27, synthetic/actual CLI, complete source/report verification, independent
graph comparison and seven retained report checks PASS. Adversaries cover missing/
duplicate/reordered reads/stores, premature store before both reads, descriptor/
direction/bank/address/value/parent/end forgeries and report deletion. Complete
multi-block count/skip/wrap ingress retains separate actual read/store ordinals.
Exact clean ares9408cb43d4948fc3ea6e152a307a34348df3fe04 and DMA/RDRAM/layout source
guards remain the boundary, with ISC notices. No upstream implementation or
branch-only CI import, Actions, ROM/assets or native fallback.
Full local fmt, strict locked workspace/all-target Clippy, locked workspace tests,
canonical CLI and diff gate PASS with two build jobs. No skipped checks or weakened
proof/source obligation; no repeated build for older compatibility sources.

This reduces composition debt without completing general mutation/producer census,
accepted pending/FIFO policy, hardware consensus, cache/TLB/reset/restore/continuous
execution lifetime or whole-ROM/native closure. All corresponding flags remain
false; no progress milestone changes. Generated controls/source/reports stay
ignored under target/dma-dmem-ingress-rsp-load-primary and
target/dmem-ingress-integration-primary.
