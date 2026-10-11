# Primary harvest: finite decoded RSP store isolation

2026-10-11. Source behavior reconciled under spike 052; lifetime stays OPEN.

Reviewed complete note/driver/runner and closeout 6070073590 at
`research/rsp-self-store-imem-gpt56sol` exact head
`761d1b53625bb78c6e0b0fa7fc93d076f4532516`. Successful code-head Actions
37851625324 and final-head Actions 37851858417 supply identical results,
SHA-256 `44804ce672e597e812753c20121dcccdfefbcfc7e72347b4df3e5009315e8929`.
The unchanged original ISC driver matches historical SHA-256
`e5d254099f953106fd105f7bb377334542c15676ba74a82bccdb12e71ac74135`.

Fresh unmodified exact-ares execution reproduces all 29 ordered probe records
and the historical source audit. Four scalar probes exercise bit 12 and wrap;
all twelve vector families execute at 0x1000 and 0x0fff; SRV also executes at
0x100f. The driver compares all 4096 IMEM bytes before/after each decoded store
and aborts on any change. Every comparison passes. Aligned SRV changes zero
DMEM bytes, while nonaligned SRV changes fifteen; preserve both controls.
Repeated stdout is identical. This directly checks IMEM preservation for these
probes, not complete machine state or every operand combination.

Inspected exact ares scalar/vector store handler bodies and RSP memory helpers:
all sinks target DMEM, with byte masking and unaligned decomposition inside
its separate 4-KiB allocation. Ten exact source blobs and three clean pins are
guarded. Gopher64 and n64-systemtest corroborate address-domain/encoding/wrap
expectations by source only. Neither independent runtime nor physical hardware
is executed. Recompiler paths are disabled and not covered. No implementation
from those references is copied or linked into Plaid native mode.

The old runner checked names and nonzero/zero changes but accepts replacing a
reported store instruction with BREAK, changing the base and falsifying its
digest. Main's strict finite typed report checks every instruction/base/change
count/digest in order, final digests and exact schema. All 122 measured mutations
reject; four synthetic tests also retain missing/extra/duplicate-name controls.
The frozen expected metadata contains only synthetic instruction facts and
hashes, no copyrighted ROM/assets/firmware. Full plaid-core, fmt and strict
locked workspace/all-target Clippy pass.

Fresh stdout SHA-256:
`5ab72a485fe5534434fe0d4471796e2dadb5d2bbd7cdfefaa8cef8d28da40154`.
Primary schema-0 result SHA-256:
`06df90cf22e09e724b646328ffb138770644baee20fcc41b1a0ee5fa20f3d990`.
Reproduce with `python spikes/052-ares-rsp-store-isolation/run.py`.

Disposition: retain the unmodified finite oracle and strict report adversaries;
old branch runner acceptance is superseded by the canonical validator. Ordinary
RSP scalar/vector data stores stay in DMEM for this pinned interpreter/source
contract. This classification does not remove CPU/SP-window, SP-DMA, reset,
restore, debugger/frontend or other IMEM mutation obligations. Complete producer
census, task activation/retirement, executable lifetimes, hardware/recompiler
coverage and whole-ROM/native closure remain OPEN. No progress milestone change.
