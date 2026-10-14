# Lower IMEM effects on the existing executable lineage clock

Spike092 extends canonical spike086/090/091 sensing and shared SP writer state.
No additional guest memory reads or source parents are invented.

Raw v8 records exact completed lower IMEM Byte/Half/Word effects and full-bank
fill/load cuts. Both existing consumers revoke affected candidate writers,
including equal-value writes. Already captured CPU/RSP reads keep frozen parents;
subsequent SP DMA installation has separate writer identity. Restore/retirement
rejects without an execution-epoch source contract. Earlier policies reject new
records and retain their old admitted behavior.

- `test_consumer.py`: scalar/equal/full cuts before and after reads, frozen CPU
  reads, partial lanes, fresh DMA installation, malformed effects and legacy
  rejection; canonical consumers and independent replay agree.
- `run.py --verify-existing`: rechecks authenticated pinned ares controls without
  rebuilding. Actual control graph: 342 records, 40 full machine/backing
  checkpoints, 42 lower IMEM effects, 56 IMEM reads, 42 performed instructions.
- `boot_driver.cpp` / `observer.hpp`: optional raw-clock capture, selected by
  spike057 `--history storage-sp-exec`.

These controls do not establish exhaustive writer coverage, task/register
ancestry, hardware consensus, continuous lifetime or whole-ROM/native closure.
All broad proof flags remain false. See the durable integration receipt.
