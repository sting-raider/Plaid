# Primary integration: guest invalidation through fresh DMA executable parents

Base:4d42e94f4dedb8688e9a2267b2dfe5dd493b8e0a. Claim:6140328998.
Extend the existing RSP/DMEM/DMA/cached executable graph with controlled v11;
no standalone consumer/raw research/workflow/native import.

One completed HitInvalidateI must match the actual decoded CACHE selector,
effective aligned direct-KSEG0 identity-RAM address, context and full before/after
slot tuple. Valid matching tags clear only validity; misses change nothing.
Track invalid contents separately from eligible fill parents. Repeated
invalidation cannot revive old parents; a later completed burst/fill captures
its own current byte writers even with equal words. CPU GPR result is unchanged.
Powered initial cache slots are zero/invalid; unsupported operations fail closed.

Actual228 events/34 matched complete reported machine/cache controls,7 RSP
definitions,3 CPU IMEM copies,7 promoted requests,8 commits,1 supersession,
4 DMEM egress RAM Word writes,4 Dual IMEM installs,2 DMEM ingress stores,
12 uncached+4 cached CPU decoder pairs,2 completed bursts/fills,1 invalidation,
21 RSP consumed words. Baseline/disabled/enabled/repeat reported states/images/
steps agree; every checkpoint hashes all512 cache tuples; enabled repeats exact.
Independent complete source/image/definition/cache/parent graph matches Rust.

Root209 -> fetch210/end211 -> CACHE decoder212/HitInvalidateI213/end214 ends
fill199 without changing words. Host pending215/216/length217 -> promote218 ->
RAMwriters219/220 -> complete221. Root222 -> fetch223/burst224/fill225/end226 ->
decoder227/end228 consumes NOP again, but fresh writer219/fill225 supply its four
parents. DMEM source parents retain ingress152/read153/write155 -> RAMwriter58 ->
original RSP definition/store lineage. This is a finite controlled DAG, not a
complete producer/mutation/root/lifetime certificate. Host roots remain opaque.

Source:7b9ec26cce0d1c4fd83e5f91a811808f4541cf256f597a7e2aa6cacc97292efb.
Report:376f53773965e94f04e5a57518d6074df85cfa9955b1471b1bac9b5d60000595.
Controls:`target/dma-cache-invalidation-primary`.
Gate/reports:`target/cache-invalidation-integration-primary` and
`target/cache-invalidation-{focused,cli-synthetic,fmt,clippy,workspace,canonical-cli}.log`.
All ELEVEN v0-v10 actual report bytes remain EXACT; repeat/stale report generation
passes. Compatibility runner's initially abbreviated v2 source directory was
corrected to the actual retained path; no evidence was reconstructed or omitted.

Exact clean ISC ares:9408cb43d4948fc3ea6e152a307a34348df3fe04. Original shared
project-owned callbacks observe completed operations; no upstream code copied
into production. Prior DMA/memory guards match; canonical Git CPU header SHA
6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27 and CACHE
interpreter SHA495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152
verified. One required new small combined baseline/sensor; no old reference build
or full-ROM recapture. Baseline binarydb21f7836a7ae57cf348804af569ec3ea4fb762e964ded6f764d7a48185a4934,
build3a5804156c81513571a684b576e0ead48405cdfa807c7a69d7d93c87bc6aacbb;
sensor49dd8ed935c31c15a48456024f4da7e07364f1089915bafeacf721b929a26ddf,
build00338110d8c0a3ebfb16ba8cbe1327bc0e0a060627e66707dd257636fed7382a;
results05dc95d35883b109c8247e798eafb80ee88a265733f940de4c625b047436aa3d.

LOCAL PASS36 focused Rust regressions, complete synthetic/actual CLI and all
earlier adversaries plus13 invalidation source/5 report forgeries; hit/miss/
repeated/initial-slot/old-parent/equal-refill/unselected-word/operand/scope/order/
cardinality/GPR/profile/source/report checks. Two old negative families selected
the last request, now valid egress: corrected to explicitly select required IMEM
ingress/decoded commit, retaining their intended failing mutations. Full fmt,
strict locked workspace/all-target Clippy --jobs2, full locked workspace tests
--jobs2 including outer fixed-point deletion, canonical CLI and diff checks pass.
No Actions,waiver/skipped test/ROM/assets/progress milestone/native fallback.
ADR0118 and STATUS/NEXT/DEVELOPMENT record the actual production boundary.

Retained hit-invalidate/reload research invariants now compose with original
DMA writer ancestry and executable consumption. Other cache operations, alias/
TLB/mapping/restore/concurrency and complete initialization/source/producer/
mutation/root/executable lifetime/whole-ROM/native coverage remain OPEN;
all general certification flags remain false.
