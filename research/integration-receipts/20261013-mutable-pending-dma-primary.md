# Primary integration: mutable pending DMA to executable consumption

Base:716cf64cc03559cce6e5fb34bac9c2f5d1e4dee8. Claim:6138951693.
Source research: canonical `research/sp-dma-lifecycle.md` and
`spikes/034-ares-sp-dma-lifecycle`, which rejected immutable pending identity at
length commit and sampled BUSY falling-edge completion. Exact ares:
9408cb43d4948fc3ea6e152a307a34348df3fe04, ISC, external clean checkout.

Reconcile these invariants into the existing original-clock RSP definition,
RAM byte writer, DMA read/install, CPU/RSP consumption graph. Controlled v8
captures initially empty pending state and actual masked register mutations before
transfer-start. Keep latest PBUS and DRAM writes separate from length commit;
record equal-value FULL recommit supersession. Promotion consumes the latest
pending descriptor/direction and parents exactly once. Idle FULL must immediately
promote; current completion still requires all descriptor-derived effects and
endpoints. No generic FIFO or immutable-at-length abstraction is introduced.

Actual combined fixture:180 events,26 independently matched checkpoints,
seven RSP definitions,three CPU IMEM copies,five promoted requests,six length
commits,one supersession,two reverse-DMA Word writes,three Dual IMEM installs,
two DMEM ingress stores,eleven CPU fetch/decoder pairs,twenty RSP fetched words.
Baseline/disabled/enabled/repeated runs agree on all reported architectural
snapshots,CPU steps and full reported bank/RAM hashes; repeated capture is exact.
Independent Python replay checks the complete census, images and all graph parents.

The added sequence has A active (promotion165), B pending (commit168), an
identical recommit C169, then PBUS/DRAM mutations170/171. Completion174 directly
hands off to promotion175 with C169's length/direction and170/171's addresses.
Read176/install177/completion178 precedes actual RSP fetch179/end180 at IMEM3c0.
The four consumed bytes retain RAMwrite58 and its original RSP producer parents.
No writer at the superseded destination380 is invented. Equal schedule/payload/
descriptor values do not recover the replaced occurrence.

Source SHA256:
ff4b802dd693e546f41eb93d8f4e4345a7bcc92328bedb7abc7fb6fd23af800d.
Report SHA256:
7f9b563f2b612caf9190f514ed37d9a422984caff17a6236430a6707eddcd5f5.
Ignored controls: `target/mutable-pending-dma-primary`.
Ignored integration reports/logs: `target/pending-dma-integration-primary`.
All EIGHT v0-v7 actual source/report checks PASS and report bytes remain EXACT;
prior v7:1f4b08b05dd910ea06bf06e34bc63377a2b47eab4b8a00d6a6bbf546b9b7aafb.

LOCAL PASS:30 focused Rust regressions, complete independent synthetic/actual
CLI replay and source/report/input adversaries, repeated standalone/SP-composed
shadow generation including stale-output guards, exact pin/source guards;
fmt check,strict locked workspace/all-target Clippy --jobs2,full locked workspace
--jobs2 (including outer fixed-point deletion regression),canonical CLI and diff.
The new small guest behavior required one baseline/sensor build; no prior
reference rebuild,full-ROM recapture,Actions or waived gate.

Spike034's pending mutation/recommit/immediate-handoff invariant now composes
with the canonical writer/consumption graph rather than remaining an isolated
finite experiment. Broader hardware disagreement is retained. This controlled
fixture drives CPU-origin MMIO from its host harness; it proves no guest MMIO
operand ancestry. Initial pending field ancestry remains unknown until an observed
write. General mutation/producer/FIFO/hardware/cache/TLB/root/reset/restore/
continuous executable lifetime and whole-ROM/native coverage stay OPEN;
all certification flags remain false. No progress milestone changed, copyrighted
ROM/assets committed,upstream implementation copied or native fallback added.

REA was directly tried on the supplied local raw `.z64` and returned
`target_unavailable`,reason `unsupported binary format`. No analysis Evidence or
runtime observation was returned. This does not affect the pinned N64 source and
capture contracts; no format coercion or REA coverage claim is made.
