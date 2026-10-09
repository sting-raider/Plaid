# PI DMA copy/completion vs I-cache provenance

This bounded experiment composes two already validated pinned-ares seams:

1. a PI DMA-write request attempts `CPU::queueInsert` and then executes the byte copy synchronously even if the queue insertion fails; and
2. cacheable instruction visibility follows the resident I-cache generation installed by a witnessed backing read/fill, not the current RDRAM contents.

The falsification target is whether PI queue/completion identity is either necessary or sufficient for executable-byte visibility.

`driver.cpp` executes the exact pinned ares core with both recompilers disabled. It first fills a target I-cache line with old code, performs a normal actual PI MMIO write request and dispatches its queued completion, then proves the cached target still executes the old resident instruction. After guest `CACHE 0x10` invalidation, refill executes the PI-written instruction. It then fills every real 512-slot priority-queue entry, issues a second actual PI MMIO write request, proves the synchronous RDRAM copy happened while no PI completion can be queued, and finally proves invalidate/refill executes those queue-less copied bytes.

The traced build records only existing completed boundaries: delegated PI source halfwords while `dmaWrite` is actually copying, successful identity-RDRAM `PI_DMA` byte writes, PI copy return/completion callbacks, exact target I-cache RDRAM burst reads, completed fills, and target fetch boundaries. The uninstrumented baseline, callback-capable observer-disabled build, observer-enabled build, and repeated observer-enabled build must agree architecturally; the repeated trace must be byte-identical.

`model.py` independently replays backing generations, completion tokens, resident generations and fetch roots. It rejects forged completion-as-visibility, current-backing attribution, equal-payload latest-writer substitution, deleted copy effects, wrong equal fill generations, forged completion tokens and restore-tuple lineage reuse. It also counts valid fetches rooted in PI transfers that have no completion, showing why completion is lifecycle evidence rather than a byte-origin gate.

Reproduce after checking out exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` at `.refs/ares`:

```sh
python3 -m py_compile experiments/pi-dma-icache-compose/{run.py,model.py,source_guard.py}
python3 experiments/pi-dma-icache-compose/model.py
python3 experiments/pi-dma-icache-compose/source_guard.py --ares .refs/ares
python3 experiments/pi-dma-icache-compose/run.py
```

This is reference-emulator evidence for the exact pinned scope, not a hardware timing claim or a whole-ROM closure certificate.
