# Primary integration: nonidentity mapping and cached context reactivation

Base:43f79887dd796a4c5d5e8f214f7f5845a567300c. Claim:6146962472.
Harvest retained spike053/research/asid-icache-lifetime-gpt56sol
a23c432ebc11ad2efdda8a33db7b5af6b9401896 and EntryHi research de423733.
Reconcile into the existing unified v19 protocol; no raw branch merge, new
consumer/schema or opcode admission. The core already expresses separate
virtual PCs/physical parents and survives context changes; this batch makes
their combined contract reproducible and retains adversarial regression gates.

Actual TLBWI325/332 maps VA e000 -> PA6000. Mapped hit335/decoder337 consumes
physical6028 ADDU21 from old fill292/CPUwriter276 although RAM already contains
BREAK/writer318. EntryHi344/351/358 changes ASID7->8->7 then repeats7 without
installed-table changes. Mapped hit361/decoder363 retains the same fill/writer,
selecting context358 and slot332. CACHE369 ends292; mapped BREAK fetch372/fill374/
decoder376 selects writer318. Exception377 saves virtual e028. Natural handler
LW387/read388 feeds RAMwriter393 at6028 and398 at602c; CACHE403 ends374.
EPCread408/XORI412/MTC0writer417/ERET424 selects virtual e02c. Returned fetch426/
fill428/decoder430 consumes physical602c, retaining writer398/read388/DMEM/DMA/
RSP ancestry. No host setter drives handler or return. Pre-trap instruction
entry seeds stay explicit opaque roots. Congruent cache colors retain the
ares/Gopher index disagreement without a hardware/synonym/hazard assertion.

Actual431 events/68 existing full machine/cache/CP0/pipeline/TLB/staged controls
and50 CPU pairs agree baseline/disabled/enabled/repeat. Complete independent
event and report graphs agree. Twenty earlier v0-v19 report bytes stay EXACT;
repeated generation and stale report rejection PASS. Initial captured inputs
remain UNKNOWN; all general ancestry/census/lifetime/native flags false.

Source:00ea9cb759e1f9b35c773efb4de7a0327fbbb4a3d3314065e4e54aba84444553.
Report:1a55fd0ca2ae53505c66a385535bdd7673d04714ba000837a4233911c59735f5.
Baseline:14521e08d71e0f5cc3290506cd8b6b698094b47ba4c520b2437c9da1637ba3e8.
Sensor:6167ba0ca72b9d27c6608ca9a08a08c3f2a5f4b9ce38da6c8818d77cb8262eb2.
Results:1cfe617338aceb0dd43729356047c2e56eae46f49fa1f2b3171fd85b729bce23.
Ignored source/controls:target/mapped-cache-reactivation-primary; reports:
target/mapped-reactivation-integration-primary; logs:target/mapped-reactivation-*.
Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04 and retained
header/IPU/SCC/TLB/exception/DMA/cache source guards PASS. No upstream code reuse.

LOCAL PASS54 focused Rust, complete actual/synthetic CLI/all earlier applicable
adversaries plus9 reactivation source/8 report forgeries. Wrong virtual/physical
identity, changed backing borrowed as stale content, replaced fill identity,
wrong ASID/restored occurrence/tag/cache snapshot/EPC/parents reject. Original
v19 actual adversaries rerun; twenty old reports replay without reference builds.
The independent rebase initially changed a DMA physical-address operand and was
corrected to preserve physical values. The in-flight reference process had
loaded that older model before compiling; fresh --verify-existing checks all
retained raw events against the corrected independent model without rebuilding
or changing actual execution. No assertion waiver or production-policy change.

Full local fmt, strict locked workspace/all-target Clippy --jobs2, locked
workspace --jobs2 including outer fixed-point deletion, canonical CLI and diff
checks PASS. No Actions/skips/ROM/assets/native fallback/milestone promotion.
STATUS/NEXT/DEVELOPMENT/ADR0118 reflect this validated composition. Changed
physical selection, broader CP0/root/mutation/reset/restore/lifetime and
whole-ROM/native closure remain OPEN; static ERET remains unsupported.
