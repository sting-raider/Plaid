# SI/PIF completion -> MI.SI -> CPU interrupt-root composition

Date: 2026-10-11

Result: **VALIDATED** for the bounded exact-pinned reference scope below.

## Question

What causal evidence is sufficient to connect an N64 Serial Interface operation to a maskable CPU interrupt root without laundering provenance through final status-bit equality?

This composes the already-validated maskable CPU interrupt-root contract with an actual SI producer path. It also tests the negative claim: an observed SI interrupt / MI.SI / Cause.IP2 state does **not** by itself prove that the producer was SI DMA.

## Exact inputs

- Plaid canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`
- Research branch: `research/si-interrupt-root-compose-gpt56sol`
- Final code-tested head: `5cb8b1104f329234086e629b08bd465f49a69634`
- ares pin: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 pin: `e96debac941a26ba4961e5145056c0821d3a56f7`

Exact guarded blobs:

- ares `ares/n64/si/dma.cpp`: `c2690ab2b0d4adaaec233871be98bea04b63d92b`
- ares `ares/n64/si/io.cpp`: `9fd94bb082cb8cf4a70313a62df23b903ad1d7a5`
- ares `ares/n64/mi/mi.cpp`: `5c2421cc7d9cc9c62b6d9445c978bb1c1d58a4c9`
- ares `ares/n64/cpu/cpu.cpp`: `41964d49c8983ae9a97b25625174cd4c4316c4a8`
- ares `ares/n64/cpu/exceptions.cpp`: `870e7d420f38fbda862cb4c7cb88481155b19251`
- Gopher64 `src/device/si.rs`: `35460182400db0bd2cf28299e5bc5f7a69dd118d`
- Gopher64 `src/device/mi.rs`: `ae3cfdb3e706a50b0ecbe02754cf0380cfaab94a`

No upstream emulator source was patched.

## Prior research composed

This lane composes `research/ares-maskable-interrupt-roots.md`, which validated that architectural maskable entry requires:

1. `(Cause.IP & Status.IM) != 0`;
2. `Status.IE == 1`;
3. `Status.EXL == 0`; and
4. `Status.ERL == 0`.

That result intentionally left device-specific producers open. This experiment fills one bounded SI path and attacks any proof rule that equates final SI pending values with unique DMA causality.

## Exact source composition

At the exact ares pin:

- SI read/write DMA register writes set DMA state and queue distinct `Queue::SI_DMA_Read` / `Queue::SI_DMA_Write` events.
- CPU queue dispatch maps those exact events to `SI::dmaRead()` / `SI::dmaWrite()`.
- Those completion routines perform the real PIF/RDRAM transfer, clear DMA state, set `io.interrupt = 1`, and call `mi.raise(MI::IRQ::SI)`.
- `SI_STATUS` write is an acknowledgement operation that sets `io.interrupt = 0` and calls `mi.lower(MI::IRQ::SI)`.
- `MI::poll()` composes `irq.si.line & irq.si.mask` into the RCP line and forwards that to the CPU RCP pending bit.
- the existing CPU gate then requires Status.IM2 + IE + !EXL + !ERL before ordinary general-vector entry.

The final source guard also checks a second SI path end to end:

- direct PIF bus write queues distinct `Queue::SI_BUS_Write`;
- CPU queue dispatch maps it to `SI::writeFinished()`;
- `writeFinished()` clears SI busy state, sets the same SI interrupt latch, and raises the same MI.SI source.

Pinned Gopher64 independently agrees on the DMA side: an `EVENT_TYPE_SI` completion clears busy state, sets the SI interrupt latch and raises `MI_INTR_SI`; status acknowledgement clears it, and enabled RCP interrupt state connects to CPU Cause.IP2. This is independent implementation agreement, not hardware truth.

## Critical falsification: equal final state does not authenticate DMA provenance

The executable matrix contains two different histories:

1. a real SI DMA read completion;
2. a direct PIF bus-write completion.

Immediately before the CPU boundary they have equal observed values for:

- SI interrupt latch;
- MI.SI line;
- MI.SI mask; and
- CPU Cause.IP2.

Both can legitimately enter the same CPU interrupt vector, but their producer identities are different.

Therefore final SI/MI/Cause values can support **root availability**, subject to the masks and CPU gate, but cannot authenticate the stronger claim **“SI DMA caused this root.”** Producer event identity and generation must survive composition.

## Executable fixture

`experiments/si-interrupt-root-compose/driver.cpp` boots the exact unmodified pinned ares N64 core headlessly with CPU/RSP recompilers disabled and identity RDRAM. It plants `ADDIU $s0,$zero,0x1234` at uncached KSEG1 PC `0xffffffffa0000000`.

One CPU instruction boundary distinguishes entry from suppression:

- interrupt taken first: `$s0 == 0`, EPC receives the planted PC, EXL becomes one, PC becomes the general vector;
- interrupt suppressed: the planted instruction retires, `$s0 == 0x1234`, PC advances four.

All RCP sources are explicitly lowered before each case. SI DMA uses RDRAM buffer `0x1000`, disjoint from the planted code. Each case is executed twice and must produce byte-identical JSON.

## 13-case matrix

The exact-pinned matrix covers:

- DMA read completion, BEV=0;
- DMA read completion, BEV=1;
- DMA write completion;
- DMA request without completion;
- completion with MI.SI mask off;
- completion with CPU Status.IM2 off;
- completion with IE off;
- completion with EXL set;
- completion with ERL set;
- completion then SI_STATUS acknowledgement before CPU boundary;
- empty acknowledgement;
- completion -> acknowledgement -> second completion;
- direct PIF bus-write completion as equal-final-state non-DMA decoy.

All 13 matched the composed causal rule and repeated byte-identically.

Validated vectors:

- BEV=0: `0xffffffff80000180`
- BEV=1: `0xffffffffbfc00380`

Important controls:

- request-only sets DMA busy but does not assert SI interrupt or take the root;
- MI mask off leaves SI/MI source latched but keeps CPU RCP pending low;
- CPU IM off, IE off, EXL on, or ERL on suppress entry while upstream pending state can remain live;
- SI_STATUS acknowledgement clears the live SI/MI generation before entry;
- a second completion after acknowledgement is a new live generation and can take the root;
- CPU interrupt entry does not itself acknowledge SI, so SI/MI pending remains asserted after entry in taken cases.

## Generation-aware adversarial replay

`experiments/si-interrupt-root-compose/model.py` separately tracks:

- SI completion generation;
- SI producer kind (`dma` versus direct `bus`);
- SI acknowledgement/clear generation;
- MI-mask write generation;
- SI pending state;
- RCP pending state; and
- CPU gate state.

A root certificate may bind a producer only when the claimed producer kind and completion generation are still live at the CPU boundary.

The replay rejects:

- deleted completion;
- direct bus completion relabelled as DMA;
- stale completion generation after ACK + recompletion;
- claimed root after ACK;
- claimed root with MI.SI masked;
- claimed root with CPU Status.IM2 masked.

Repeated same-value MI-mask writes remain distinct operation generations.

Final model result:

```text
MODEL_SHA256=16ae3b129402fa97fe4b2c0376e845d761aa1b90691394682751794c69bc3b72
PASS: 11 causal controls and 6 forged histories
```

## Final dynamic evidence

Final fail-closed GitHub Actions run against code-tested head `5cb8b1104f329234086e629b08bd465f49a69634`:

- run: `38098816312`
- job: `114350262350`
- result payload SHA-256: `c1fb6f6f15b5bd45f260591bb97a48c7a2aa8917b8a3c497f6adc1f95472b78e`
- model log SHA-256: `873ad7b3f663f76790e4399dcb90bc7a74d743b1860dceb287431fce2ff7c65f`
- executable-run log SHA-256: `a2a10a1279a8b0a5c950c284549c2cf007008e294b2058a7153ad66f88493a39`
- artifact ID: `11686723789`
- artifact ZIP SHA-256: `38096e20773dbc830bb53b878484e0741a35fa9bf566201fe8033c1fa057ac89`

The workflow uses `set -o pipefail` for piped verifier commands. The exact source guard checks request queue origin, queue event identity, queue dispatch target, completion behavior, acknowledgement, MI gate and CPU root contract.

## Diagnostic failure intentionally excluded from evidence

Initial run `38098446139` caught two research-fixture bugs.

First, the fixture originally put the SI DMA destination at RDRAM zero, the same address as the planted CPU discriminator. A real SI read completion therefore overwrote the instruction. The DMA buffer was moved to `0x1000` before any result was accepted.

Second, the workflow originally used `python ... | tee` without `pipefail`, allowing a Python assertion failure to appear successful until the later hash step noticed the missing result file. The workflow was made fail-closed before accepting evidence.

Run `38098446139` is diagnostic-only and must not be cited as semantic validation.

## Certificate rule for this bounded path

A future whole-ROM certificate attributing a CPU interrupt root specifically to SI DMA should retain ordered evidence for at least:

1. SI request identity and operation kind;
2. matching completion event generation and producer kind;
3. any intervening SI_STATUS acknowledgement/clear generation;
4. live MI.SI source and MI-mask generation;
5. CPU Cause.IP2 / Status.IM2 state plus IE/EXL/ERL gate at the relevant boundary;
6. resulting exception-root transfer.

If producer kind or completion generation is UNKNOWN, DMA provenance remains UNKNOWN even when SI interrupt, MI.SI and Cause.IP2 have expected values. An acknowledgement cuts the live generation; a later completion is a new generation, not resurrection of the old one.

## Reproduction

With `.refs/ares` and `.refs/gopher64` checked out to the exact pins above:

```bash
python3 experiments/si-interrupt-root-compose/source_guard.py
python3 -m py_compile \
  experiments/si-interrupt-root-compose/model.py \
  experiments/si-interrupt-root-compose/run.py
python3 experiments/si-interrupt-root-compose/model.py
python3 experiments/si-interrupt-root-compose/run.py
sha256sum target/si-interrupt-root-compose/results.json
```

The branch-only workflow `.github/workflows/research-si-interrupt-root-compose.yml` performs exact pin fetch, source/blob guards, adversarial replay, executable matrix, hashes and evidence upload.

## Closed-world impact

**VALIDATED, bounded:** an SI DMA completion can be causally composed through SI interrupt latch -> MI.SI source/mask -> CPU RCP/IP2 mask -> CPU interrupt gate -> BEV-sensitive general root. Request/busy state alone is insufficient; acknowledgement can terminate the live generation; recompletion creates a new one.

The stronger negative result is equally important: the same final SI/MI/IP2 values can come from a non-DMA SI bus completion. A closure solver must preserve producer identity rather than infer DMA provenance from final interrupt values.

This reduces one device-specific root uncertainty but does not close WholeRom.

## Remaining gap

- No physical N64 hardware was run. ares is the executed oracle; Gopher64 is an independent exact-pinned source cross-check.
- The fixture performs real SI request setup and directly invokes the exact completion methods rather than waiting the scheduled delay. Queue origin/event/dispatch are exact-source guarded, but arbitrary timing races are not exhausted.
- The direct PIF bus-write producer is enough to reject unique-DMA inference, but this is not a complete census of every SI/PIF producer under every peripheral configuration.
- Delay-slot timing, simultaneous device producers, save/restore chronology, reset/NMI interactions and arbitrary interleavings remain outside this bounded experiment.
- Handler-byte provenance/immutability for an arbitrary ROM is not proved here.
- Dynamic observations are not exhaustive whole-ROM reachability and are not a closed-world proof by themselves.

## Integration recommendation

**ADOPT the evidence-model invariant, not final-value inference.** Represent SI request/completion producer identity and acknowledgement as explicit ordered generations, then compose the live generation with MI and CPU gate evidence. Do not infer “SI DMA caused this interrupt root” solely from SI_STATUS, MI_INTR or Cause.IP2 values. Keep the obligation OPEN when producer identity or chronology is missing.

No production Plaid code was changed and nothing was merged into `main`; the primary integrator can selectively adopt the invariant and fixtures.