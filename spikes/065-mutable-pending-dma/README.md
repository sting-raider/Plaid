# Mutable pending DMA composed with executable consumption

Run `python spikes/065-mutable-pending-dma/run.py` locally, then
`python scripts/test_rsp_definitions.py --pending --source target/mutable-pending-dma-primary/source.json`.
`--verify-existing` checks retained controls without rebuilding.

Controlled v8 extends the existing original-clock producer/RAM/IMEM/DMEM graph.
Capture the initially empty pending slot and completed SP address/length-register
mutations, before the length path calls transfer-start. Replay the pinned masks;
retain latest address writers separately from length-commit occurrences. A FULL
pending length recommit replaces its predecessor even when values match. Later
address writes mutate the same pending slot, rather than freezing its descriptor.
Only actual promotion consumes that latest pending state. Completion and all
byte/fetch parents use the existing canonical progression rules.

The added fixture starts A, commits B while BUSY, recommits identical C while
FULL, then changes PBUS and rewrites DRAM before immediate handoff. C installs
the previously produced RAM bytes at IMEM0x3c0; one actual RSP NOP consumes them.
Both memory images and full reported architectural/control checkpoints are
compared across baseline, disabled sensor, enabled sensor and repeated execution.
The independent verifier reconstructs the complete 180-event census and graph,
including the six commits, one supersession and five promoted requests.

This is pinned ares behavior under controlled host-driven MMIO. It proves no
guest MMIO operand ancestry, general pending/FIFO policy, physical hardware
timing, complete mutation census, reset/restore/cache/mapping lifetime or
whole-ROM/native closure. Initial pending address ancestry stays unknown until
a captured write. No runtime interpreter/native fallback is added. Reference
source remains external and pinned; generated shadows and captures are ignored.
