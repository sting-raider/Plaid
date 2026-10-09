# PI DMA copy/completion versus I-cache executable provenance

Result: **VALIDATED** for the bounded exact-pinned ares scope below, 2026-10-09.

This result does **not** claim hardware timing truth, a complete PI mutation census,
or whole-ROM closure. It establishes a compositional proof boundary that Plaid must
preserve: PI queue/completion identity is neither necessary nor sufficient for
cacheable CPU instruction visibility.

## Question

Can Plaid safely use PI queue insertion/completion identity as either:

1. a prerequisite for attributing executable bytes to a PI copy, or
2. evidence that the copied bytes are now the cache-visible instruction bytes?

The answer is **no** in both directions for pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`.

A defensible cacheable executable chain is instead:

`PI source/copy operation -> concrete successful RDRAM writer generation -> witnessed I-cache backing read/fill -> current resident generation -> fetched instruction`

Queue insertion token / dispatch / `dmaFinished()` identity remains separate
PI device-lifecycle evidence. It cannot substitute for any byte-writer or cache
residency edge.

## Prior research composed

This lane composes, rather than reopens, previously validated boundaries:

- `research/pi-request-queue-dispatch.md`: pinned ares performs PI DMA byte copies
  synchronously after attempting `CPU::queueInsert`; a full queue can reject the
  completion event while the copy still executes. Queue identity is needed only
  to prove request -> later dispatch/completion identity.
- `research/icache-rdram-chronology.md`: an eligible RDRAM burst joined to a
  completed I-cache fill installs resident provenance; later backing mutation
  does not retroactively replace that resident generation.
- `research/cached-code-patch-visibility.md`: cacheable execution can remain stale
  after backing changes until a cache visibility transition.
- `research/pi-fetch-writer-history.md`: concrete PI/RDRAM writers can be joined
  to fetched resident bytes and equal payloads do not collapse writer identity.
  Its direct-host PI helper sequence did not exercise the request/queue-failure
  boundary addressed here.
- `research/rsp-spdma-icache-compose.md` is a read-only precedent for the same
  backing-writer -> fill -> resident join on the RSP/SP-DMA producer path. This
  lane tests the independent PI copy-versus-completion boundary.

The current production PI history implementation was also inspected. It already
keeps synchronous returned copies separate from observed completion status:
`writes_without_observer_status` is first-class and
`transfer_completion_certified` remains false. The boot PI observer ends source
copy scope at PI event 7 (copy return), not event 8 (completion). Therefore this
work validates a cross-seam proof invariant; it did not uncover a production
`pi_history.rs` bug requiring a core patch.

## Exact source contracts

`experiments/pi-dma-icache-compose/source_guard.py` checks 21 contracts against
exact pinned ares. The important seams are:

- the N64 event queue is a fixed 512-entry priority queue;
- insertion failure returns false and `CPU::queueInsert` silently returns;
- PI write-length MMIO sets busy, attempts `PI_DMA_Write` queue insertion, and
  then calls `dmaWrite()` immediately;
- the actual byte loop writes RDRAM with `RBusDevice::PI_DMA`;
- `dmaFinished()` later changes PI busy/interrupt state but does not perform the
  byte copy;
- cacheable CPU fetch hits return the resident I-cache line, while a miss reads
  backing via the I-cache RDRAM burst path and fills the line.

Guarded source SHA-256 values from successful Actions run `38005081724`:

| exact pinned file | SHA-256 |
| --- | --- |
| `ares/n64/cpu/cpu.cpp` | `65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1` |
| `ares/n64/cpu/cpu.hpp` | `6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27` |
| `ares/n64/cpu/memory.cpp` | `55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74` |
| `ares/n64/memory/bus.hpp` | `1cbe65b06ab32c10134912b45b33100dfec4b1703104fadb304dcf03b343b295` |
| `ares/n64/mi/bus.hpp` | `f59d20c5d7d8d0ef53032af320f1c96b9343971bb513668b749ca6cda8c4d372` |
| `ares/n64/n64.hpp` | `8b0e3c6035eb40980d782bd78d6e27ee1dd42dfca8897ff83e5cf93fd376ae6a` |
| `ares/n64/pi/dma.cpp` | `296b7e1a8a096082f99a7b52d976acbabd20709062dbceb2f6f23481c900fab6` |
| `ares/n64/pi/io.cpp` | `f85015aa7cc10ef79164db4b8febc4516c5d3246607d99565527f6dfd6ac002e` |
| `nall/nall/priority-queue.hpp` | `e54d6ca2cef5de37ae1ea8d57f756a329a53c2496cd609531943e5825dbf67f7` |

## Actual pinned-core experiment

Artifacts:

- `experiments/pi-dma-icache-compose/driver.cpp`
- `experiments/pi-dma-icache-compose/baseline.cpp`
- `experiments/pi-dma-icache-compose/run.py`
- `.github/workflows/research-pi-dma-icache-compose.yml`

Both CPU and RSP recompilers are disabled. The fixture uses actual PI MMIO writes,
the real 512-entry queue, real `CPU::synchronize`, real `PI::dmaWrite`, real
`PI::dmaFinished`, actual guest CACHE invalidation, and actual cacheable CPU
instruction fetches.

The observer records only already-completed boundaries: delegated PI source
halfwords while the copy is active, successful identity-RDRAM PI byte writes,
copy return/completion callbacks, target I-cache RDRAM burst reads, completed
target fills, and target fetch boundaries.

The run compares:

1. an uninstrumented baseline;
2. the callback-capable build with observers disabled;
3. the callback-capable build with observers enabled; and
4. a repeated enabled execution.

All architectural checkpoints/final state agree, and the repeated enabled trace
is byte-identical.

### Counterexample A: completion is insufficient

1. RDRAM target `0x4000` contains `0x34080000` (`ORI t0,zero,0`).
2. A cacheable fetch fills and executes that old line.
3. A normal PI MMIO write copies 32 bytes from ROM offset `0x1000`; first word is
   `0x34081111`.
4. The real queued PI completion dispatches and `dmaFinished()` runs.
5. A later cacheable fetch still executes resident `0x34080000`; there is no new
   target fill at this point.
6. Only after guest CACHE hit invalidation and a new RDRAM-backed fill does the
   CPU execute `0x34081111`.

Therefore PI completion did not establish executable visibility of the copied
bytes. The resident I-cache generation remained authoritative.

### Counterexample B: completion is unnecessary

1. After the first refill, all 512 real queue slots are occupied by future
   events.
2. A second real PI MMIO write requests 32 bytes from ROM offset `0x3000`; first
   word is `0x34083333`.
3. `CPU::queueInsert` cannot insert a PI completion event, but the synchronous
   `dmaWrite()` still performs all 32 target RDRAM byte writes.
4. PI remains busy and no completion callback/interrupt transition exists for
   this second transfer.
5. The still-resident target line continues to execute `0x34081111`.
6. Guest invalidation followed by an actual backing read/fill installs and
   executes `0x34083333`.

Therefore a concrete PI copy can become executable through the normal cache
visibility chain even when no PI completion identity exists at all.

### Successful exact-reference receipt

GitHub Actions run `38005081724`, job `114071893550`: **SUCCESS**.

Observed summary:

- 117 recorded events;
- transfer 1: 16 source halfword observations, 32 successful PI/RDRAM byte
  writes, and one real completion;
- transfer 2: 16 source halfword observations, 32 successful PI/RDRAM byte
  writes, and **no** completion;
- target fills install first words in order:
  `0x34080000`, `0x34081111`, `0x34083333`;
- target cached fetches execute first words in order:
  `0x34080000`, `0x34080000`, `0x34081111`, `0x34081111`, `0x34083333`.

Hashes:

- exact actual result SHA-256:
  `219467974727280a8584c156297133fb82d9663225d4b4d60e20e734ec16dd73`;
- exact enabled trace SHA-256:
  `4b6a39c3a46a729a173d404a9a7d9b1a9f3d402d5d8540a8622d8f96b05a8f9f`;
- uploaded evidence ZIP SHA-256:
  `5a9f84d37924d6899112d6156178a778b65895bb8eb3a2b961d329066fc11485`;
- Actions artifact ID: `11651370361`.

The final queue-less state intentionally retains `PI dmaBusy=1` and
`interrupt=0`, so the second transfer's absence of completion is an observed
fixture condition rather than an omitted trace event.

## Adversarial replay

`experiments/pi-dma-icache-compose/model.py` separately models:

- PI copy/backing writer generations;
- queue-token/completion identity;
- I-cache resident generations; and
- fetched provenance roots.

It deliberately keeps these identities separate even when payloads are equal.
An identical restored cache tuple without a fill witness loses lineage and yields
`UNKNOWN` provenance.

The strict replay rejects seven forged histories:

1. using PI completion to promote a stale resident line;
2. using current RDRAM backing to promote a stale resident line;
3. replacing resident provenance with a newer equal-payload PI writer;
4. deleting the queue-less PI copy while retaining the later fill claim;
5. substituting an equal-valued but wrong backing generation at fill;
6. forging the completion token; and
7. resurrecting old provenance from an equal restored resident tuple.

Canonical model receipts from successful Actions run `38005081724`:

- model report SHA-256:
  `351370142ac05174fb44582bb8e374fcf42fcc4477d71520035b393c34989cb1`;
- canonical model trace SHA-256:
  `c8d1858b784f29fb6ce97b0a7cf01b711e559186593f70ffea901062a175633f`;
- emitted `model1.json` SHA-256:
  `5ac041ca7fb077e1345af992788fbd35dd183835000110dc35fcab9f424203e0`.

Naive-policy falsification finds:

- completion-as-visibility disagrees with strict provenance on fetches
  `[5, 13, 15, 18, 20]` in the model trace;
- current-backing-as-resident disagrees on `[5, 10, 15, 20]`;
- valid PI-rooted fetches without any completion occur at
  `[13, 15, 18, 20]`.

## Falsification / harness history

The first Actions attempt, run `38004845495`, passed all source guards and the
adversarial model but failed while compiling the executable fixture. The fixture
included both nall's `queue` template name and the N64 global queue, so two bare
`queue.` accesses were ambiguous to GCC. No reference execution occurred and no
semantic check failed.

The repair did not weaken or change any asserted behavior. `run.py` now asserts
there are exactly two such accesses and generates a build-only same-directory
copy qualifying them as `ares::Nintendo64::queue.`. Pinned reference source is
unchanged. The second run then executed all reference behavior and passed.

## Closed-world impact

For a PI-produced cacheable instruction, a CLOSED proof must **not** require
`dmaFinished`, PI interrupt state, a successful queue token, equal payload, or
current backing equality as an executable-origin edge.

Conversely, none of those lifecycle/value facts can justify changing the
currently executable resident generation.

The proof obligations are independent:

- **PI lifecycle:** if Plaid needs to claim request -> later completion identity,
  require the queue-token/dispatch proof appropriate to that claim.
- **byte provenance:** require the concrete successful destination writer and
  its causal PI source/copy lineage.
- **cache visibility:** require the actual backing read/fill or another validated
  resident transition that installs that writer generation.
- **execution:** bind the fetch to that current resident generation.

If any required byte writer or resident transition is missing, provenance remains
`UNKNOWN` / closure remains OPEN. Completion evidence cannot fill the gap.
Likewise, a missing completion must not erase a witnessed byte writer that later
reaches a proven resident fill.

This matters directly to whole-ROM executable closure because otherwise a proof
system can make either unsound mistake:

- false CLOSED by treating a completed DMA as if its new bytes became executable
  immediately despite stale I-cache residency; or
- false OPEN / lost provenance by discarding a real copied executable generation
  solely because the completion event was never inserted or observed.

## Remaining gap

This experiment is intentionally bounded:

- it is exact-reference evidence for pinned ares, not an N64 hardware timing
  measurement;
- queue saturation is synthetic and chosen specifically to falsify completion as
  a byte-origin prerequisite;
- the target is identity-mapped RDRAM with cacheable KSEG0 fetches;
- D-cache effects, translated/TLB aliases, save/restore, replacement/eviction,
  resets and complete mutation census remain separate obligations;
- it does not certify executable lifetimes or native completeness.

Hardware/system-test evidence, or agreement with additional independent pinned
references where the same queue/copy distinction is representable, would raise
confidence beyond this emulator-specific composition.

## Integration recommendation

No production PI-history patch is justified by this result: current
`pi_history.rs` already preserves returned copies separately from completion
status, and the boot observer scopes source capture to the synchronous copy.

Integrate the invariant and regression fixture selectively:

1. retain PI queue/completion identity as lifecycle evidence only;
2. treat successful PI destination writes as the byte-provenance effect whether
   or not completion is later observed;
3. require a distinct cache-residency transition before those backing bytes can
   replace an already resident executable generation; and
4. keep same-value writers and restore/resident generations distinct.

Do not merge this research branch mechanically. The primary integrator should
reproduce the Actions receipt and cherry-pick or re-express only the durable
research/test artifacts that fit canonical architecture.

## Reproduction

With exact ares pin checked out at `.refs/ares`:

```sh
python3 -m py_compile \
  experiments/pi-dma-icache-compose/run.py \
  experiments/pi-dma-icache-compose/model.py \
  experiments/pi-dma-icache-compose/source_guard.py
python3 experiments/pi-dma-icache-compose/source_guard.py --ares .refs/ares
python3 experiments/pi-dma-icache-compose/model.py
python3 experiments/pi-dma-icache-compose/run.py
```
