# Primary integration: live EPC through handler mutation and return consumption

Base:0f9c53aa0ece0ac65b798dfb2fef502c387d18a7. Claim:6141674124.
Controlled v15 composes existing writer/cache/exception facts with selected EPC
generation and actual ERET/first returned instruction. No standalone consumer,
raw branch/workflow/native import or static ERET closure admission.

Live candidate EPC ownership begins at the verified exception transfer and ends
at opaque control seeds or the bounded return. Only the permitted continuous
handler instruction stream can retain it. Unsupported CP0 writes/reset/restore
reject. ERL0/kernel32/IE0 ERET must match the current uncut frame's selected EPC/
state, clear EXL/LLbit, preserve complete GPRs, and immediately fetch/decode the
cached target. Equal numeric target labels cannot reconstruct lost ownership.
Consuming this bounded frame does not modify physical EPC.

Actual365 events/57 matched complete reported machine/cache controls,39 CPU
decoder pairs (21 uncached+18 cached),7 RSP definitions,3 identity IMEM copies,
7 DMA requests,8 commits,1 supersession,4 DMA+5 CPU RAM writers,4 Dual IMEM
installs,2 DMEM ingress stores,7 bursts/fills,5 invalidations,1 exception/handler
entry,1 ERET/returned entry,21 RSP words. Baseline/disabled/enabled/repeat all
steps/images/states/checkpoints match; every checkpoint includes all512 cache
tuples plus EXL/ERL/BEV/IE/LLbit/address mode and CPU pipeline state. Enabled source
repeat exact; independent complete event/image/register/cache/root/return/parent
graph matches Rust. No host PC setters execute after first handler entry.

Original BREAK331/transfer332 saves EPC80006028. Handler NOP338 -> actual sequential
LW342/SPread343 -> SW347/RAMwriter348 replaces BREAK with NOP -> CACHE352/
invalidation353 ends fill329 -> ERET357/transfer358 selects live EPC producer332.
Returned fetch360/burst361/fill362 -> decoder364 consumes NOP with CPUwriter348/
load342/read343 -> DMEM ingress152/RAMwriter58/original RSP parents. Initial
handler184..190 code bytes remain declared-input/ultimate-source UNKNOWN; first
root NOP's separate CPUwriter307 ancestry remains retained.

Source:1732818b0b1baa6733b137d09dec5853b6917bf7c4bee157de9a831948404c0e.
Report:98c0905d5192c79a23571725b3349f1f86df8f9ca0a28cc04b05fcd1b9b3f6dd.
Ignored controls:`target/live-epc-handler-return-primary`; rechecks/reports:
`target/eret-return-integration-primary`; gate logs:`target/eret-return-*.log`.
All FIFTEEN v0-v14 actual reports byte EXACT; repeated/stale generation PASS.

Harvest: read exact research/eret-target-provenance-gpt56sol
381bb9f24aa277f516d8157dc71cc42362a27a7e and
research/eret-errorepc-hardware-gpt56sol1293fa7. The actual common-EPC branch model
raw source SHA784786765d85c95143ded606fab79bf2ab9cfa79df56d6a4bbc6f0d3015403a9
differs from historical note23350e13ccfa6df122aa25a829471ce688c4dd1afbc3556fe7e2aae0ab2189b1;
neither CRLF conversion nor branch drift explains that note mismatch. Read actual
source, enroll its immutable Git bytes and repeat unchanged: stdout exactly
7d94d6f6c7692ef39ff288b2656123d7678e1a7eb3f7e6fea883cb5fcc8a462e and semantic
994d5fa3a83c7ced1ad2ebc40c4fbf9b1c95f1b298fe2f4d94b243a41969b530 reproduce.
100000 histories/624838 returns preserve the reported capture-only errors and
current-generation rule. Artifacts:`target/eret-primary-review`. This self-generated
model is proof-shape evidence, never an external production chronology certificate.
Retain exact pinned Mupen pure-interpreter ERL stop vs ares/Gopher/target-contract
research; no new physical-console receipt or ERL support claimed here.

Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04; prior exception/cache/
DMA/memory guards match. SCC source SHA
df7252d14f532e9fa44a39147be05afeb9851196a7d5249ab325900cee2aa722 authenticates actual
EPC selection/EXL/LLbit path. Original project getters around actual decoders;
no upstream code copied/linked. One required new small baseline/sensor; no old
reference/full-ROM rebuild. Baseline af8b7f1447b610af40314f932b04283881ffdea815a4cb502b3145bbd1dc9c9e;
build38d01d4f137ee7ac4c57ec15b68c0402f6f2f6bdf3e26677b09f8a0895da00f2;
sensor4683b8eb7e1de535f5fbbf96e49720e80aa23ee1bf9637006b1070296d0fcdc9;
buildaf3abb357a4939216e514dbd9e137d1060bb753957971edb9c0c42e51061dac9;
results740319628112cfec9487d6797462573262b2431e255c8a76289af80a688fe108.

LOCAL PASS44 focused Rust, complete actual/synthetic CLI/all earlier adversaries
plus11 return source/5 report forgeries; current-vs-past EPC/opaque cut/ERL/IE/
target/EXL/LLbit/scope/cardinality/first-fetch/truncation/parent/source/report checks.
Old XORI report negative selected the last writer, now an identity handler copy;
changed to the last actual transformed writer. No assertion waived. Full fmt,
strict locked workspace/all-target Clippy --jobs2, full locked workspace --jobs2
incl outer fixed-point deletion, canonical CLI and diff PASS. No Actions/skipped
test/milestone/ROM/assets/native fallback; ADR0118/STATUS/NEXT/DEVELOPMENT updated.

Common selected-EPC/live-generation invariants now compose with actual continuous
handler/executable mutation/cache effects and returned consumption. Guest EPC/
ErrorEPC writes (including same-value generations), ERL/interrupt returns,
reset/restore/complete CP0/source/mutation/root/mapping/lifetime/whole-ROM/native
coverage remain OPEN; all general certification flags false. Static discovery
continues to reject ERET; no finite observation becomes an all-target certificate.
