# Primary integration: guest EPC writer generations through returned execution

Base:a90d5afbdd5c7ab30cbc2b88cb05ba854bd19c1d. Claim:6143882048.
Controlled v16 harvests the current selected-EPC writer invariant from already
reviewed research/eret-target-provenance-gpt56sol381bb9f24aa277f516d8157dc71cc42362a27a7e
into the existing source/writer/cache/exception/ERET graph. No raw research model,
branch CI, static ERET admission or standalone consumer.

Actual MFC0 read358 -> GPR8 -> equal-value MTC0 writer363 -> ERET368 selects363
while retaining exception frame332. Returned fetch370/burst371/fill372/decoder374
consumes replacement NOP with CPUwriter348/load342/read343 -> DMEM ingress152/
RAMwriter58/original RSP parents. No host PC setters after first handler entry.
Handler code remains declared-input/ultimate-source UNKNOWN.

EPC read/write states are captured in the decoder scope, after epilogue and before
pipeline.end for completed effects. Ordinary snapshot PC therefore remains the
decoder PC. Full before/completed state and independent GPR steps are checked.
MFC0 sign-extends low32 EPC; MTC0 writes the full source GPR. The initial supported
scope is a held current read/same-value write in an uncut kernel32/ERL0/IE0 frame.
CP0 held ancestry is separate from physical SP/RAM load ancestry. LW/XORI/ADDU
destination writes cut it, even for equal values; opaque roots cut the frame and
held definitions. Equal MTC0 creates a fresh ID. An old held read cannot witness a
second write after the selected generation changes. ERET's optional guest writer
ID stays distinct from its exception-frame ID; old report shape omits it.

Actual375 events/59 matched complete reported machine/cache/CP0/pipeline controls,
41 CPU decoder pairs (21 uncached+20 cached),7 RSP definitions,3 identity IMEM
copies,7 DMA requests,8 commits,1 supersession,4 DMA+5 CPU RAM writers,4 Dual IMEM
installs,2 DMEM ingress stores,7 bursts/fills,5 invalidations,1 exception entry,
1 EPC read,1 EPC write,1 ERET/returned entry and21 RSP words. Baseline/disabled/
enabled/repeat steps/images/states/checkpoints match; each checkpoint includes
all512 cache tuples, EPC/cause, EXL/ERL/BEV/IE/LLbit/address mode and pipeline state.
Enabled source exact; independent complete source/image/register/cache/root/
CP0/return/parent graph agrees with Rust.

Source:e381a1c33251818be76b498d4cb40376e70fb4d5e8689bc662d44feac170be04.
Report:170c7bd6fed9e6f132ff42e57ce4935370e31be9a0d5a9ad713c720245f4331f.
Ignored actual controls:target/guest-epc-return-primary; reports/rechecks:
target/guest-epc-integration-primary; gate logs:target/epc-*.log.
All SIXTEEN v0-v15 reports byte EXACT; repeated/stale generation PASS.

Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04; existing CPU header/
IPU/exception/cache/DMA/memory guards retained. SCC source SHA
 df7252d14f532e9fa44a39147be05afeb9851196a7d5249ab325900cee2aa722 authenticates
MFC0/MTC0/EPC setter and ERET effects. One required small combined baseline/sensor;
no old reference/full-ROM rebuild. Baseline b55a1878ff7ea9d4c5fbcad64c4abb22ec7b08cd192125c3b01100afd9f5e0e8;
build56a1e4ad23eb0e3947911c33d15ffdbd0ed9b3aba5b31448d73d9c4e5643337c;
sensor b5b06f8e4be8618a9ee5151e0a9e10ae9953d5747f5b02811d4ebe272e006584;
build9d5486af95c2021ecca49f96eeafe8d8f843c307c9241db4481f3629f9980779;
results5f5b4f8e4aeaffbfb2002da51225b1260f6ca0b6b88fa1e25410bc687cefe63e.
Original project getters/fixtures only; no reference implementation copied/linked.

LOCAL PASS46 focused Rust, complete synthetic/actual CLI/all earlier adversaries
plus15 EPC source/8 report forgeries and3 full-handler lifetime cases. The latter
insert same-value XORI/ADDU register rewrites or a second equal MTC0 and require
precise missing-held-read/stale-generation rejection, not an unrelated malformed
fixture failure. Unit checks include a fresh read of the new generation. Full64/
reserved operand/selector/privilege/scope/cardinality/completed state/GPR/source/
report/parent gates retained. Source guards caught incorrectly copied digest
literals before building; restored exact canonical hashes. Synthetic dictionary
aliasing corrected so negative tests mutate only the intended snapshot. No
assertion waiver. Full fmt, strict locked workspace/all-target Clippy --jobs2,
full locked workspace --jobs2 including outer fixed-point deletion, canonical CLI
and diff PASS. No Actions/skips/progress milestone/ROM/assets/native fallback.

This composes guest return-register generation with actual executable ancestry;
changed EPC targets/arbitrary CP0 sources/other CP0 writes/ErrorEPC/ERL/interrupt/
reset/restore/complete source/root/mutation/mapping/lifetime/whole-ROM/native remain
OPEN. All general certification flags false. Static discovery still rejects ERET.
