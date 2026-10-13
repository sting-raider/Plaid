# Primary integration: guest page-frame writer to remapped executable ancestry

Base:915e8e12a4fcbb97b5331f6835c81a39e500d936. Claim:6147245634.
Reconcile retained ASID/remap findings into the unified TLB/context/writer/cache/
root/return graph. No raw branch/workflow merge or standalone consumer.

Controlled v20/fixture21 captures actual MTC0 EntryLo0 after its masked setter
and before break at clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04.
Bind nonzero decoded GPR/full value to global/valid/dirty/CCA/PFN fields plus
before/completed full CP0/staged/32-entry state. Only normalized non-global low-
region4KiB/kernel32/IE0 pre-trap writes are admitted. Installed entries remain
unchanged. Same-value writes still acquire fresh occurrence identity. TLBWI
fixes its slot's installed page-writer parent; later staging cannot alter that
parent. ASID writer, page writer, slot operation, RAM writer and cache fill stay
separate. Optional new report parents remain omitted from all earlier profiles.

CPU LW369/read370 -> XORI375 -> RAMwriter391 copies known DMEM NOP as BREAK to
physicale028. Actual pointer XORI380/385 binds changed store/CACHE operands.
EntryLo0 writes398/405 stage pagee000;405 is an equal rewrite. Hit408/decoder410
still selects old installed slot332/physical6028/fill292 despite new staging.
TLBWI417 installs pagee000 and retains page writer405/ASIDwriter358. CACHE423
misses old physical tag, preserving292. Mapped virtuale028 fetch426/burst427/
fill428/decoder430 selects new physicale028/CPUwriter391 even though old
physical6028 also contains equal BREAK bits. Exception431 saves virtuale028.
Natural handler LW441/read442 feeds CPUwriters447/452 atphysicale028/e02c;
CACHE457 ends428. EPCread462/XORI466/MTC0writer471/ERET478 selects virtuale02c.
Return480/burst481/fill482/decoder484 retains CPUwriter452/read442/DMEM ingress/
RAMwriter58/RSP parents. No host setter drives handler or return; pre-trap entry
seeds remain explicit opaque roots. Cache colors congruent; no hardware/synonym/
hazard generalization of the retained ares/Gopher index disagreement.

Actual485 events/77 complete existing machine/cache/CP0/pipeline/TLB/staged
controls and59 CPU pairs agree baseline/disabled/enabled/repeat. Enabled source
exact; independent complete event and report graphs agree. All TWENTY-ONE older
source/report pairs (v0-v19 plus fixture20) remain byte EXACT; repeated generation
and stale report rejection PASS. No old reference/full-ROM rebuild or Actions.

Source:b9666bb7cb5866a47d203b22bb3f3e4ada971c99749470c551816787c8ced5cc.
Report:4687149abb8a8b1217774e9a588884ae944c520a66fe7198d2416e328aac6dd2.
Ignored controls/source:target/entrylo-remap-root-return-primary; reports:
target/entrylo-remap-integration-primary; logs:target/entrylo-remap-*.
Guard exact CPU header/IPU/SCC/TLB/exception/DMA/cache source digests and clean
reference state. Observation hook is a free function pointer/getters, no changed
upstream object layout or guest effects; no upstream production code copied.

Focused56 Rust and complete actual/synthetic CLI/all applicable prior adversaries
PASS, plus14 page/remap source and10 report forgeries. Missing/repeated/misbound
effects, wrong full GPR/selector/masked fields/table/privilege/physical mapping,
staged-vs-installed parent borrowing and equal BREAK at another PA reject. Rust
also checks later staged writes cannot replace an earlier installed parent and
that installation cannot precede write completion. Fixture20 actual adversaries
rerun. The independent model restored old PA602c's DMA bytes after the handler
moved to new backing; unit fixture dirty bits were aligned with actual masked
operands. Generic older same-content/cache-replacement forgeries now flip/select
the actual facts so they remain real mutations with a third TLB operation and
additional hit. No assertion waiver or fail-closed weakening. The in-flight
builder loaded the earlier model; fresh --verify-existing compares retained raw
execution to the corrected model without rebuilding references.

Canonical gate on the final tree: cargo fmt --all -- --check; cargo clippy
--locked --workspace --all-targets --jobs2 -- -D warnings; cargo test --locked
--workspace --jobs2 (including outer fixed-point deletion); python scripts/test_cli.py;
git diff --check. Exact results and CAS/fetched verification belong to the
corresponding issue4 main-integration closeout. STATUS/NEXT/DEVELOPMENT/ADR0118
record the bounded production change. No progress milestone/ROM/assets/native
fallback change. Initial GPR/staged inputs stay UNKNOWN; other CP0/global/
geometry/privilege/reset/restore/hazards/source/root/mutation/lifetime/whole-ROM/
native remain OPEN, all general flags false; static ERET unsupported.
