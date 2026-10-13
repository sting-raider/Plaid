# Primary integration: CPU RAM copies through cached executable ancestry

Base:afc20748230defe9dfdeb7b91dd6f048644eed5c. Claim:6140627158.
Controlled v12 composes the canonical SP LW/held-register verifier with actual
CPU SW RAM writers and the existing original-clock DMA/cache executable graph.
No standalone consumer/raw research/workflow/native import.

One completed aligned direct-KSEG1 SW effect per decoder must match effective
address, context, low32 source value and complete unchanged GPR result. Its copy
parent preserves the held LW context/read/source/byte identities; the held
definition must match the complete source GPR, not only equal low32 bits.
Without a held definition, each byte becomes UNKNOWN at this write, even for
equal values. CPU writer IDs remain distinct from SP DMA IDs. Explicit host roots
cut register definitions; v12 admits uncached fetch/scalar-read boundaries within
such a root before its decoder, using the existing strict fetch scope verifier.

Actual259-event/39 matched complete reported machine/cache controls retain7 RSP
definitions,3 CPU IMEM copies,7 requests,8 commits,1 supersession,4 DMA RAM Word
writers,4 Dual IMEM installs,2 DMEM ingress stores,14 uncached+7 cached CPU decoder
pairs,3 bursts/fills,2 invalidations,1 CPU RAM writer and21 RSP fetched words.
All baseline/disabled/enabled/repeat steps/images/states/checkpoints match; each
checkpoint hashes all512 I-cache tuples. Enabled repeat source exact. Independent
complete source/image/register/definition/cache/parent graph matches Rust report.

Opaque root229 -> fetch230/read231/end232 -> actual LW233/SPread234/end235.
Sequential fetch236/read237/end238 -> SW239/RAMwriter240/end241 copies NOP to6028.
Parent: load233/read234 -> DMEM ingress152/read153/write155 -> RAMwriter58 ->
original RSP definition/store. Root242 -> resident fetch243/decoder245 retains
RAMwriter219/fill225 despite equal CPU backing write240. Root247 -> CACHE250/
operation251 ends225. Root253 -> fetch254/burst255/fill256 -> decoder258 consumes
NOP with CPUwriter240 parents. The original source clock and all distinct writer/
read/fill contexts survive this finite DAG; no producer/census/lifetime closure.

Source:40449baaeeed1277265777a2b22e1851bc68621bfe368c25f08b2ecb63dafc3a.
Report:34f25fa2df0df83deaa036a503d37660a4fed8fed93cfff8e01eb377b0ddc1ac.
Ignored controls:`target/cpu-copy-ram-cached-primary`; receipts/reports:
`target/cpu-ram-copy-integration-primary`; gate logs:`target/cpu-ram-copy-*.log`.
All TWELVE v0-v11 actual report bytes remain EXACT; repeat/stale generation passes.

Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04 and prior canonical
DMA/RDRAM/memory/CPU CACHE/header source guards match. Original project callbacks
observe completed CPU Word writes; no upstream implementation copied. One required
new small combined baseline/sensor, no old-reference build/full-ROM recapture.
Baseline539708c30a6d7f44f79f74e6fa1e9f75924381897ea5c49f009457ba379f663c;
build68d4aa1dae4435c711fae4954cb4f5357dc4e5dff1225a481cf51ee21542256e;
sensoreb5b87ae5ecbdc89b10b2a7958d8aac4155fb6f641cd118b9c63eba578324c97;
build00f09c6b1eeddb5af3c83b326cb5c2ad21011657eef7278f8275e797c9c196a0;
results43f969a3d0008c8bfa8375a4e246dd5b7427bec2fafa406a8e3d3fffb0754a18.

LOCAL PASS38 focused Rust, complete synthetic/actual CLI and all prior adversaries
plus10 CPU RAM source/7 report forgeries; held-register/high-bits/equal-unknown/
width/operand/scope/cardinality/result/parent/source/report checks. The initial
candidate correctly rejected an uncached opaque root's scalar read; v12 now
explicitly admits that boundary through the strict existing read verifier, while
older profiles retain their original policy. A Python local variable accidentally
shadowed the copy module; renamed it and repeated the complete CLI gate. No
assertion waived. Full fmt, strict locked workspace/all-target Clippy --jobs2,
full locked workspace --jobs2 incl outer fixed-point deletion, canonical CLI and
diff pass. No Actions/skipped checks/progress milestone/ROM/assets/native fallback.
ADR0118/STATUS/NEXT/DEVELOPMENT record actual state.

Retained uncached CPU copy/installed executable ancestry invariants are now joined
to DMA source lineage and resident/refilled consumption. Cached data copies/
writeback, transforms/decompression/relocation, ultimate register initialization/
source/producer ancestry, complete mutation/cache/TLB/mapping/root/restore/lifetime
and whole-ROM/native closure remain OPEN. All certification flags remain false.
