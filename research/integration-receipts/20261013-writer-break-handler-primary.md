# Primary integration: writer ancestry through BREAK and first handler fetch

Base:85cab06f1c36db5e28da2225f970b8270252f33b. Claim:6141358619.
Controlled v14 composes canonical `resolve_exception_root` and exact pinned
general-vector behavior with the original-clock RSP/DMA/CPU/cache graph.
No standalone consumer/raw research/workflow/native import.

Require actual BREAK pre-state in the decoder and one completed exception
transition before its end. Validate non-delay/non-nested BEV0/kernel32/kernel
General vector, cause9, EPC equal triggering PC, EXL set, remaining captured
state and complete GPRs. Required first cached handler fetch/decoder cannot be
replaced by opaque PC reseeding, unrelated actors, equal bytes or truncation.
Keep triggering-code and handler-code writer/fill ancestry distinct. Root identity
selects the expected next PC; ordinary sequential CPU continuity remains strict.

Actual339 events/52 matched complete reported machine/cache controls,34 CPU decoder
pairs (21 uncached+13 cached),7 RSP definitions,3 identity IMEM copies,7 DMA requests,
8 commits,1 supersession,4 DMA+4 CPU RAM writers,4 Dual IMEM installs,2 DMEM ingress
stores,6 bursts/fills,4 invalidations,1 exception transfer/handler entry and21 RSP
words. Baseline/disabled/enabled/repeat steps/images/states/checkpoints agree;
every checkpoint hashes all512 cache tuples. Enabled source repeat exact;
independent complete event/image/definition/cache/root/parent graph matches Rust.

Root296 -> LW300/SPread301 supplies DMEM NOP with ingress152/read153/write155 ->
RAMwriter58 -> original RSP parents. SW306/RAMwriter307 installs handler NOP at180.
XORI312 -> SW317/RAMwriter318 installs BREAK13 at6028. CACHE323/invalidation324
ends fill292; burst328/fill329 -> decoder331 executes BREAK. Captured transition332
sets actual root80000180/cause9/EXL/EPC80006028. After decoder333, root fetch334/
burst335/fill336 -> handler decoder338 preserves CPUwriter307 parents. The driver
asserts the actual exception PC and does not call its host setter for this step.
Declared RAM expands to0..6080 (24704 bytes) to retain root backing separately.
Incoming r20 pointer/setup remains captured input, not ultimate initialization.

Source:c5ab4a5f6700e507094c57c184121df74ad186d9095bb197978f39ab9f6883e6.
Report:25c2e3f38e6bc3a4be2634eafccfa778e81d222bc94d5a4c875e05c6ae3f6168.
Ignored controls:`target/writer-break-handler-primary`; reports/rechecks:
`target/break-root-integration-primary`; gate logs:`target/break-root-*.log`.
All FOURTEEN v0-v13 actual reports remain byte EXACT; repeat/stale generation PASS.

Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04. Prior canonical
DMA/memory/cache/header/XORI guards match; exception source SHA
e24b2877fb5d629ca3f10f64dba9a612babb879c53ed142b42557920f216ffa7 authenticates
actual EPC/EXL/general vector/pipeline transfer. Original project-owned state
getters execute around real decoder effects; no upstream code copied/linked.
One required new small combined baseline/sensor, no old-reference/full-ROM rebuild.
Baseline d59191ef1c415509a982558e6ef48e490589ef399ec89918763bec1cf9d5fb45;
build cfa056e81526c33094a10543a323cf6256ee72540c2b44e0a9b91a7e957a0ef9;
sensor bb362b307d4a217a2b6ecffa979f96730fb36dc35b10a38b050006e8d2d302dc;
build 6aaaf0b8a239d0e94f81613d85fec8762c309b7b290d6fe55178c83f1d5fb0bf;
results76b0155d7883d7dc84576686f78e930d3d660a3169280b8597606072b010fa25.

LOCAL PASS42 focused Rust, complete actual/synthetic CLI/all prior adversaries
plus14 root source/6 report forgeries; overwritten sentinel EPC, nested/delay/
BEV/mode/privilege/cause/EXL/BD/scope/required effect/first-fetch/opaque reseeding/
truncation/source/report/parent checks. Full fmt, strict locked workspace/all-target
Clippy --jobs2, full locked workspace --jobs2 incl outer fixed-point deletion,
canonical CLI and diff PASS. No Actions/assertion waiver/skipped check/milestone/
ROM/assets/native fallback. ADR0118 and STATUS/NEXT/DEVELOPMENT reflect this boundary.

Canonical root selection and retained handler/cache writer invariants are now
joined to an actual triggering executable producer and first handler consumption.
This is one controlled occurrence; general interrupt/exception/TLB/nested/delay/
reset/restore/root/producer/mutation/mapping/continuous lifetime/whole-ROM/native
coverage remains OPEN. All general certification flags remain false.
