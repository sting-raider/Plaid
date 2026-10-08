# Buffered PI copy provenance

Hypothesis: a successful delegated ROM half-read must join through the actual
PI DMA block/buffer lane to a completed RAM byte write; adjacent read/write
matching cannot explain a whole block that is read before writes begin.

```powershell
python spikes/028-ares-pi-buffered-copy/run.py
```

Eight original component cases cover an aligned copy, identical reload from a
different source, changed reload, misaligned destination, odd length, row boundary,
out-of-bounds destination and unmapped/open-bus source. The fixture invokes real
`dmaWrite`/`dmaFinished` components directly; it claims no guest MMIO setup,
queue/scheduler duration or CPU execution. Completion of byte writes is separate
from the later busy/interrupt transition.

Project-owned sensors use existing buffer/results and fields without guest
accesses or clocks. Ignored generated PI/RDRAM TUs are separately compiled with
the pinned reference's ISC/BSD notices. Source buffers, ROMs and traces stay
ignored. No production image/lifetime identity is created.

## Verdict: VALIDATED

### Evidence

- The command passes on pinned ares with both recompilers disabled. A separately
  compiled original-PI baseline, disabled callbacks and repeated traces agree on
  all reported CPU, RAM/hidden hashes and eight PI/memory checkpoints.
- 479 records retain 111 byte attempts, 103 successful writes, 95 exact canonical
  ROM origins, eight unknown open-bus origins and eight failed destinations.
  Identical reloads retain different source offsets and transfer ordinals.
- A row-crossing first block reads two bytes but writes none; misalignment and
  odd length also discard lanes. Missing completion, forged writes and duplicate
  ordinals fail; an equal-byte source substitution removes its origin witness.
- Result SHA-256:
  `ec467fd50f91c42354172079e9548196f24eabb308619743ff2debbead81dca7`.
- `python spikes/028-ares-pi-buffered-copy/test_recipe.py` checks opt-in generation
  and reuse without claiming CPU execution. The prior six-case recipe also passes.

### Constraints and surprises

- Ordinary RDRAM witness policy is successful identity-only; OOB/translated paths
  cannot produce a destination witness even if the source half-read is known.
- Open-bus/latch values can be written to RAM without a ROM-origin witness.
- Buffer lanes, discarded bytes, partial blocks and DMA completion are distinct
  obligations. Exact observed writes do not prove immutable executable lifetimes.

### Recommendation

Compose these measured transfer contexts with actual RAM fetch/fill observations
next, preserving backing writers separately from resident cache data. Broader boot
integration needs a separate schema/implementation decision.
