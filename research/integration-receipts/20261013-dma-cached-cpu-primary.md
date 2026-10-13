# Primary integration: DMA writer ancestry through cached CPU consumption

Base:791f3d16c31bdebf67e03251e4ce64943da6e992. Claim:6139774054.
Compose the existing RSP/DMEM/DMA RAM writer graph with the retained PI burst/
fill/resident invariant and canonical `FetchCacheLine.validate`. No separate
finite consumer,raw research/workflow merge or native lowering.

Controlled v10 requires completed32-byte RAM burst then immediate matching
I-cache fill in the same cached fetch scope. Verify every word against its own
captured backing image; retain all32 fill-time byte parents. Cached end snapshots
must match the complete resident tuple and selected word. Cached hits retain
original burst/fill/byte identities through changed backing; no invented scalar
read or current-value ancestry. Separate cached receipts from uncached receipts.
Explicit host PC seeds preserve GPRs,cut derived register definitions and bind the
next fetch/decoder; they grant no guest control-flow/root reachability proof.

Actual208-event/31-control source: seven RSP definitions,three CPU IMEM copies,
six requests,seven commits,one supersession,two reverse-DMA Word writers,four Dual
IMEM installs,two DMEM ingress stores,twelve uncached and two cached CPU decoder
pairs,one32-byte burst/fill,twenty-one RSP fetched words. Full reported machine/
bank/RAM/control states and CPU steps agree baseline/disabled/enabled/repeat;
all512 I-cache tags/indexes/words are hashed at each checkpoint. Repeated capture
is exact; independent complete event/image/cache/definition/parent replay agrees.

Opaque root196 -> fetch197/burst198/fill199/end200/decoder201 first consumes
cached6030 with unknown initial ancestry. Fill199 retains DMA RAMwriter58 at6028.
Debugger write203 changes backing6028 to BREAK. Opaque root204 -> cached fetch205/
end206/decoder207/end208 still executes NOP at6028 using fill199/burst198 and all
four RAMwriter58/RSP producer parents. No second memory read or fill is invented.

Source:d8add684d2904b2011df4adb676575a32218b4b4165e91908779dd21ac27b5cc.
Report:c68e3d914164694da89e95ba61fb898961e52e86abd1c8e4d389664c9d5e937b.
Ignored controls:`target/dma-cached-cpu-primary`; gate:`target/cached-cpu-integration-primary`.
All TEN v0-v9 source/report checks PASS and report bytes remain EXACT; prior
v9:1869d66087d78d50dc8027c96e2fb8edf9407315a2dcd0ddc437a261b11d216b.

The first207-event actual capture omitted the first host alias transition.
Source0adc08ecc408aa42736cae75c3bd6f6207e59c87a4aab52771b20ef2121dfc3c
is retained under `target/cache-entry-root-negative`; canonical admission rejects
it with CPU register/control continuity mismatch. Corrected the sensor metadata
instead of weakening PC continuity. The guest behavior is unchanged: the added
first-root callback is compiled out of baseline, and its phase setter is inert.
Baseline binary1ff5822d74c4c84f744c5b4e542ba8aad77c1c615009284cf8a32d5e802d7eb2
and buildca3d30ea92041889a7f14d70b600c3344c6af3417c142b558ae4ffdf5c9ba883
are authenticated. Current shared source with exactly that annotation removed
matches the enrolled baseline extra; every other extra remains identical.
Reused baseline,rebuilt only corrected sensor. A Python result-path shadowing
mistake was repaired and all runs repeated without another compile.

Exact clean ares:9408cb43d4948fc3ea6e152a307a34348df3fe04,ISC. Prior DMA/memory
canonical Git source guard values still match; CPU cache header SHA:
6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27.
No old reference rebuild or full-ROM recapture.

LOCAL PASS:33 focused Rust regressions; full independent synthetic/actual CLI,
burst/fill cardinality/scope/address/unselected lane/tag/value/root deletion/GPR/
parent/source/report/input forgeries,actual207 negative; repeat/stale-output shadow
generation; fmt,strict locked workspace/all-target Clippy --jobs2,full locked
workspace --jobs2 incl outer fixed-point deletion,canonical CLI/diff and exact-head
CAS. No Actions,waiver or skipped check. ADR0118/STATUS/NEXT/DEVELOPMENT updated;
no progress milestone,copyrighted assets,upstream implementation or native fallback.

Broader cache operations/invalidation/replacement,aliases/TLB,restore epochs,
register initialization/producer/mutation census,execution-root completeness and
continuous executable lifetime/whole-ROM/native remain OPEN. All certification
flags remain false. The controlled scheduling/root inputs are explicit and not
promoted into ordinary guest execution or hardware truth.
