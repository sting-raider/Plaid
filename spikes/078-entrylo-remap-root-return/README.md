# Guest page-frame writers compose with physical executable remapping

Run `python spikes/078-entrylo-remap-root-return/run.py` or `--verify-existing`,
then `python scripts/test_rsp_definitions.py --entrylo-remap --source
target/entrylo-remap-root-return-primary/source.json`.

Controlled v20/fixture21 extends the unified source clock with an observational
callback inside exact pinned ares's EntryLo0 setter, after masked fields and
before break. Completed full GPR/decoder/CP0/staged/table data bind each write.
Only normalized low-region/non-global/4KiB, kernel32/IE0 pre-trap state is admitted.
Installed entries cannot change at this setter. Same-value writes are distinct;
TLBWI records which completed page writer was actually installed. A subsequent
staged write cannot replace an installed slot's parent without another TLBWI.

The CPU copies known SP/DMEM NOP, transforms it to BREAK and writes physicale028
at391. Actual EntryLo0 writes398/405 stage page e000, with405 an equal rewrite.
Mapped hit408/decoder410 still selects old installed slot332/PA6028/fill292.
TLBWI417 installs the new physical page and retains page writer405 separately
from ASID writer358. Guest CACHE423 misses the old physical tag and preserves
fill292; the mapped e028 fetch426/refill428 replaces it with physicale028/
CPUwriter391. BREAK430/exception431 saves virtuale028. Natural handler writers
447/452 replace physicale028/e02c; CACHE457 ends428; EPCread462/XORI466/MTC0writer
471/ERET478 selects virtuale02c. Returned fetch480/fill482/decoder484 retains
physicale02c/CPUwriter452/DMEM/DMA/RSP ancestry. No host setter drives the handler
or return; pre-trap entry seeds remain opaque roots.

Complete485 events/77 existing full machine/cache/CP0/pipeline/TLB controls and59
CPU steps agree baseline/disabled/enabled/repeat. The independent complete event
and report graphs agree. Existing source/report pairs are replayed without old
reference builds. Equal BREAK words at old/new physical locations cannot borrow
writer identity. Source/report adversaries retain all previous proof obligations.

Initial captured GPR/staged inputs remain UNKNOWN. Other CP0/PageMask/EntryLo1/
Index/TLBWR/TLBR/global/address modes, reset/restore/hazards/root/mutation census,
whole-ROM and native closure remain OPEN; all flags false, static ERET unsupported.
Cache colors are congruent; preserve ares/Gopher index disagreement rather than
assert hardware truth. No upstream implementation copied into production; raw
reference objects/notices/controls stay ignored under target/.
