# Current RAM writers compose through CPU loads with RSP execution

Run `python spikes/082-ram-load-imem-consumption/run.py` or `--verify-existing`,
then `python scripts/test_rsp_definitions.py --ram-load-imem --source
target/ram-load-imem-consumption-primary/source.json`.

Controlled v24/fixture25 extends the shared graph with actual decoded aligned
direct-KSEG1 Word LW. Its operand read is a distinct event from instruction-fetch
reads. Full before/completed control/link/endian and GPR state binds the operation;
the result is signed to64 bits. Each byte's `cpu_ram_load` wrapper retains its
actual read occurrence, physical address and current `RamByteOrigin`. Existing
CPU register/XORI/copy receipts carry these parents into RAM or IMEM sinks.

LW575/read576 atRAMe02c selects handler CPUwriter473, retaining the earlier
DMEM/DMA/RSP graph. Identity XORI581 remains an actual fresh expression. CPU
IMEM writer587 is consumed at RSP589. RAMwriter595 then installs equal NOP from
the held old load/transform; it cannot retroactively change that read. Fresh
LW600/read601 selects595, and IMEMwriter607 is consumed at RSP609. Both RSP words
are equal; their source/copy/write generations differ. Final IMEM0 selects607.

The610-event/102-control capture,77 CPU steps and28 RSP words match baseline,
disabled, enabled and repeat runs and the independent complete graph. All25
earlier report bytes remain exact without rebuilding their reference fixtures.
Adversaries reject missing/repeated/misbound fetch-vs-operand reads, wrong
address/payload/width/state/result, stale equal writers/reads, future writer
substitution and copied RSP/final writer substitution. Unknown backing writers
remain Unknown after equal writes; snapshots are not ultimate origins.

Scope is successful aligned direct-KSEG1 identity-RDRAM LW, kernel32/IE0/BEV0/
EXL0/ERL0/non-delay/big-endian, on the exact clean ISC ares pin. Cached/mapped/
degraded/failed/other loads, global source/mutation census/root/lifetime/whole-ROM/
native remain OPEN. All flags false; ordinary static ERET unsupported. No upstream
production reuse, Actions, ROM/assets or older/full-ROM reference rebuild.
