# Decoded CPU MMIO commit composed with executable consumption

Run `python spikes/066-decoded-mmio-dma/run.py`, then
`python scripts/test_rsp_definitions.py --decoded-mmio --source target/decoded-mmio-dma-primary/source.json`.
`--verify-existing` checks retained controls without rebuilding.

Controlled v9 extends the same original-clock producer/pending/DMA graph with an
actual CPU `SW r0,8(r17)` to direct-KSEG1 SP_READ_LENGTH. Require the precise
instruction/context, aligned MMIO register, captured base and low32 source value,
exactly one pending sink and unchanged complete GPR state. Synchronous promotion
may occur inside that decoder scope only immediately after its exact length-write
effect. Keep its decoder identity in the pending commit and promoted request.
Represented address-register SW effects use the same address/value verification;
other addresses, alias/mapped/cache paths and instructions remain unsupported.

Host address setup stays independently identified. The fetched SW backing word
is a captured debugger write/unknown source cut, not ROM provenance. The RSP
later consumes the installed NOP's earlier producer-derived RAM byte parents;
the unexecuted second installed word retains the explicit unknown code-write cut.

The controlled scheduler executes the added CPU instruction without the harness's
post-instruction `cpu.synchronize()` call, then drains DMA separately after decoder
completion. This is a bounded reference fixture schedule, not hardware timing or
general concurrent-device policy. Baseline/disabled/enabled/repeat controls all use
that same schedule and compare29 complete reported architectural/checkpoint states.
The independent model reconstructs all195 events and every output parent.

No guest interpreter or reference dependency enters native runtime. Initial base
register ancestry, whole-machine writer/producer census, arbitrary request/root/
reset/restore/cache/TLB lifetime, hardware FIFO policy and whole-ROM/native closure
remain OPEN; all certification flags remain false. Preserve nine older v0-v8
source/report receipts without rebuilding their references.
