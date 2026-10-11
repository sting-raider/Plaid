# Primary composition: cached pointer reads and canonical D-cache exports

Base: fcd39a35cedb412dcb78c8492f50f07def9f5a77. Claim: 6115276081.
Candidate PR #5 @ d10ebb3823ee18e891bfd9ec9b3501727ef97c2a and recovered
pointer-dcache @ 57aa9295cee27f8467277ed07e7a96bb333e0312; source research
pointer-table-dcache-load-source-gpt56sol @ 8da5cc98d03a522509c1f5c307de6552d08605f4.

One canonical resident engine now supplies both normalized cached Word read and
successful writeback receipts. V1 adds completed backing Word mutations without
refreshing resident bytes, preserving exact fill/mutation generations/revisions
and byte lanes through all reads/exports. Direct identity geometry, conflicting
slots, invalidation, changed/missing sinks, source/report forgery and backing
contradictions reject. The old v0 contract and nine regressions remain unchanged.
This replaces the candidate's independent state machine; it does not import
branch CI or its unbound instruction-word check as decoded CPU dataflow proof.

Retained actual capture byte SHA256:
6a1bdf2b2f59916ba32f9951db6bae2378eec4fa21854ceae0660970c222f0e9.
Canonical complete capture SHA256, authenticated by original actual log:
feab0c6e4d651116f1267c4f5a36e047c6be81634a062d35c2067a5765e21d28.
Original independent replay reproduced exactly with twelve forgeries:
fbd918c9b8d93a838921df8c086d91dc63fe2015fa101c0a9e0b2a25a21efa39.
Pinned ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 dcache.cpp and
rdram.hpp match recorded hashes and are clean; driver, observer and recipe
match the source branch. Historical baseline/disabled/repeat controls were
retained by the exact source recipe/log. No new emulator build or Actions run.

The adapter retains all successful cached Word callbacks and relevant backing
bursts/scalar effects, normalizes their ordinals and materializes the completed
fill implied by each observed miss and its exact preceding burst. Fill rows
are a derived projection, not an additional raw sensor. The optional committed
CLI test binds both raw and canonical capture hashes and checks every case:
stale resident vs current backing, same-value backing generation, changed refill,
equal-payload conflict/refill and resident-only pointer. Captured tag validity,
direct index and miss/preceding-burst identity remain checked by the adapter and
original independent replay. No initial writer or CPU register definition is
invented. Entire five-report canonical set SHA256:
e31ac3dff47c55b42140049691ee0b0b8e3d5a912a6633bde4cc6cd6ac7c17d1.

Local PASS: three shared read/export/replacement/geometry/deletion regressions,
nine retained writeback tests, CLI source/report/input boundaries and all five
authenticated actual cases with ten fresh forgeries; fmt, strict locked
workspace/all-target Clippy, full locked workspace including the actual outer
fixed-point deletion adversary, canonical CLI and diff check. Ignored local
inputs/logs are under target/pointer-cache-primary. ADR-0119 and STATUS/NEXT/
DEVELOPMENT updated. Progress unchanged.

Superseded: PR #5 standalone pointer D-cache engine and recovered duplicate
branches. Physical pointer-immutability candidates are reviewed but remain
pending composition; no false exhaustive certificate from a finite clean
history. Initial backing/operand roots, complete sensing, decoded CPU LW/JR
definitions, TLB/cache/reset/restore lifetime and executable target generations
remain OPEN. All closure/census/native flags remain false; no solver waiver.
