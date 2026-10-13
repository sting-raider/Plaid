# Primary integration: EPC transforms through changed return targets

Base:23e11b9a4fe5451383552f8f53911ce3c80cf3b2. Claim:6144184370.
Controlled v17 composes canonical single in-place XORI semantics and current
selected-register generation research into the actual handler/cache/root/return
proof graph. No raw branch/model/CI import or isolated finite consumer.

BREAK transfer332 saves EPC6028. Actual handler LW342/SPread343 feeds SW347/
writer348 at6028 and SW352/writer353 at602c. CACHE357/invalidation358 ends fill329.
MFC0 read363 -> XORI367 derives602c from6028 -> MTC0 writer372 -> ERET379 selects
that completed EPC. Returned fetch381/burst382/fill383/decoder385 consumes known
NOP at602c with separate writer353/load342/read343 -> DMEM ingress152/RAMwriter58/
original RSP parents. No host PC setters after first handler entry. ERET's own
code at1a0 has separate fill376 with honest initial-source UNKNOWN parents.

A held current EPC read retains original bits and one in-place XORI expression
using the existing CpuXorTransform receipt. Validate full64/unsigned-u16 results
and all GPR effects. MTC0 binds the computed full source GPR to completed EPC;
ERET/later MFC0 select the latest writer's state, never the original exception
capture. Repeated/renamed/unattributed transforms cut held ancestry; current
writer generation checks prevent borrowing old equal reads. Opaque roots cut
frame/register candidates. V16 retains its stricter transform cut. No CP0 value
is mislabeled as physical SP/RAM load ancestry.

Actual386 events/61 matched complete reported machine/cache/CP0/pipeline controls,
43 CPU pairs (21 uncached+22 cached),7 RSP definitions,3 identity IMEM copies,
7 DMA requests,8 commits,1 supersession,4 DMA+6 CPU RAM writers,4 Dual IMEM installs,
2 DMEM ingress stores,8 bursts/fills,5 invalidations,1 exception entry,1 EPC read,
1 EPC write,1 ERET/returned entry,21 RSP words. Baseline/disabled/enabled/repeat
steps/images/states/checkpoints match; all512 cache tuples/EPC/cause/EXL/ERL/BEV/
IE/LLbit/address mode/pipeline fields retained. Enabled source exact; independent
complete source/image/GPR/cache/root/CP0/transform/return/writer graph agrees.

Source:c6b6f2d24e595bcdaf1e45de2c978edb1aee05de78e2439a87221e00acc1b640.
Report:2308048a4a40d9a36a5bf8494310c64f9f5ef30ba1bdea9533eca2672ec26577.
Ignored controls:target/epc-transform-target-primary; rechecks/reports:
target/epc-target-integration-primary; gate logs:target/epc-target-*.log.
All SEVENTEEN v0-v16 actual report bytes EXACT; repeated/stale generation PASS.

Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04; prior SCC/IPU/header/
exception/cache/DMA/memory source guards retained. One required small combined
baseline/sensor; no old reference/full-ROM rebuild. Baseline86c7f30ee60524620548c804566620debacc814ab782b86cf38a4813849ecf67;
build1d56bf63a48f928ea5f0c7c2bf4f3adb2c9ed9d37df7b634c663009eb32191b6;
sensor36d37cae6586d923b0aa40341f0df537ef1023a6d9d34355ed86f60b181305fd;
build5d4d143606fb2fc39ab3a4b2b191c126c251df52bea412a16a374f7b6bc4b88e;
results94c10e07fe9dbaf6cc3561f03e6b55e3273eb8bef7e6fd106e7a19880aa931d8.
Original project fixtures/getters only; no upstream code copied/linked.

LOCAL PASS48 focused Rust; complete actual/synthetic CLI/all earlier applicable
adversaries plus8 changed-target source/8 report forgeries. Fresh current-generation
read after changed write passes; original capture cannot select new target.
Repeated/renamed/unattributed/full64/unsigned-immediate/high-bit/old-profile/
opaque-cut/operand/selector/state/GPR/scope/cardinality/source/report/transform/
writer-parent checks retained. Replayed original v16 actual source and all its
three exact-error full-handler lifetime regressions with current production.
Focused-test call sites updated to typed held ancestry; no assertion waived.
Full fmt, strict locked workspace/all-target Clippy --jobs2, full locked workspace
--jobs2 including outer fixed-point deletion, canonical CLI and diff PASS.
No Actions/skipped test/progress milestone/ROM/assets/native fallback changes.

Changed return targets now carry a real register expression and independent
executable writer/refill ancestry. Broader transforms/arbitrary CP0 sources/
ErrorEPC/ERL/interrupt/reset/restore/complete source/root/mutation/mapping/lifetime/
whole-ROM/native remain OPEN; all general certification flags false. Static
ERET remains unsupported. Next compose mapping generations with this graph.
