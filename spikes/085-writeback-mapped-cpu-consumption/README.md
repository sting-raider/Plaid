# Complete writeback composes with stale and refilled mapped CPU execution

Run `python spikes/085-writeback-mapped-cpu-consumption/run.py` or
`--verify-existing`, then `python scripts/test_rsp_definitions.py --writeback-cpu
--source target/writeback-mapped-cpu-consumption-primary/source.json`.

Fixture28 reuses the v26 production protocol and verifier. Actual mapped NOP at
VA/PAe02c, fetch731/end732/decoder733, still selects I-cache fill503 and CPUwriter473
despite the later complete D-cache export699 containing equal bytes. Guest
HitInvalidateI739/operation740 ends503. Fresh mapped fetch743/burst744/fill745/
decoder747 selects export699 at byte offsets12..15. The complete32-byte fill
retains all16 exported occurrences plus16 Unknown bytes. Slot417/page405/TLBR438
mapping identities stay unchanged and distinct from cache/backing writers.

The748-event/127-control source,97 CPU steps/33 RSP words matches baseline,
disabled, enabled and repeated runs and the complete independent graph. All28
older report bytes remain exact. Source/report adversaries reject substituted
backing for stale residency, ended-fill reuse, false invalidation/refill and stale
mapping/export/clean-lane identities. No new source format/standalone consumer,
production Rust change, native admission, Actions, ROM/assets or older/full-ROM
reference rebuild. General source/mutation/root/lifetime/hardware/whole-ROM/native
remain OPEN; all flags false. Static ERET stays unsupported.
