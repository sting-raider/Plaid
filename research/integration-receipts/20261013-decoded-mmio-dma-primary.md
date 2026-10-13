# Primary integration: decoded CPU MMIO to DMA executable consumption

Base:cf6baf80da6ef6c9ed4efe9f71ce9f55ba2d5045. Claim:6139221295.
Compose current v8 pending mutations and promoted writer/consumption facts with
the actual pinned CPU SW -> RSP ioWrite -> synchronous transfer-start path.
Exact external ares:9408cb43d4948fc3ea6e152a307a34348df3fe04,ISC,clean.
No new standalone mutation consumer or raw research/workflow merge.

Controlled v9 validates one decoded aligned direct-KSEG1 SW into represented SP
address/length registers. Check exact instruction/context/PC/phase, register
address,low32 source value and full unchanged GPR state. A pending effect belongs
to one SW. Synchronous promotion inside that decoder scope is allowed only
immediately after its exact accepted length write, and keeps the pending commit's
decoder context. Unscoped host writes remain separately represented. Existing
complete descriptor progression and byte/read/install/fetch ancestry are reused.

New actual fixture:195 events,29 matched controls,seven RSP definitions,three
CPU IMEM copies,six promoted requests,seven length commits,one supersession,
two reverse-DMA Word writes,four Dual IMEM installs,two DMEM ingress stores,
twelve CPU fetch/decoder pairs,twenty-one RSP fetched words. All complete
reported architectural/control checkpoints,CPU steps and full reported bank/RAM
hashes agree baseline/disabled/enabled/repeat; repeated source is exact. Independent
Python replay checks every event,complete image and output parent.

Host PBUS/DRAM writes181/182 set IMEM3e0/RAM6028. Debugger code write183 replaces
RAM602c with SW r0,8(r17), an explicit UNKNOWN byte cut. Fetch184/read185/end186
consumes those current bytes; CPU decoder187 performs pending length effect188.
Actual synchronous promotion189 retains decoder187 before CPUend190.
Read191/install192/completion193 precedes RSPfetch194/end195, executing NOP at3e0.
Its first four installed byte parents retain RAMwriter58/prior RSP producer.
The second unexecuted installed word retains code-write183's unknown source.
Address base r17 is a captured input; r0 remains architectural zero. No ROM or
ultimate initialization ancestry is manufactured.

The controlled fixture skips the shared harness's post-instruction synchronize
call for this added SW, then drains DMA separately after decoder completion.
Baseline and all sensor modes use exactly that declared schedule. This is not
an automatic concurrent scheduler,hardware timing/atomicity or general FIFO claim.

Source SHA256:
b1f210567f3f9e4bbaf8c5232bb4720fe8bab8bf48ce2734e49e4e4f68d80dc9.
Report SHA256:
1869d66087d78d50dc8027c96e2fb8edf9407315a2dcd0ddc437a261b11d216b.
Ignored controls: `target/decoded-mmio-dma-primary`.
Ignored gate/reports: `target/decoded-mmio-integration-primary`.
All NINE v0-v8 actual source/report checks PASS and report bytes stay EXACT;
prior v8:7f9b563f2b612caf9190f514ed37d9a422984caff17a6236430a6707eddcd5f5.

LOCAL PASS:31 focused Rust regressions,complete independent synthetic/actual
CLI source/report/input and decoded-scope/address/value/duplicate/missing/
promotion-order/GPR/parent adversaries,repeat/stale-output shadow generation,
exact pin/source guards; fmt,strict locked workspace/all-target Clippy --jobs2,
full locked workspace --jobs2 including outer fixed-point deletion,canonical CLI
and diff. Two old CLI negatives selected the wrong final event after extension;
they now select the required full commit and known DMA-backed fetch explicitly.
No production defect was hidden by weakening a negative control.

One necessary new small baseline/sensor build, no old reference rebuild/full-ROM
recapture/Actions/waiver. STATUS/NEXT/DEVELOPMENT and ADR0118 updated; no milestone,
copyrighted ROM/assets,upstream implementation or native fallback committed.
General initialization/base/source ancestry,producer/mutation census,concurrent
hardware/cache/TLB/root/reset/restore/continuous executable lifetime and
whole-ROM/native closure stay OPEN; all certification flags remain false.
