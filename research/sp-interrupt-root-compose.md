# SP/RSP interrupt producer to CPU root composition

Date: 2026-10-10

Result: **VALIDATED** for the bounded exact-reference/source-composition scope below.

## Question

What evidence is minimally sufficient to attribute a BEV-sensitive CPU maskable-interrupt root to the N64 SP/RSP producer rather than merely observing equal HALT/BROKE, MI or Cause register values?

This deliberately starts where the completed maskable-interrupt-root experiment stopped: that earlier exact-pinned ares execution established the CPU admission rule and root, but explicitly left real device producer reachability open.

## Exact inputs

- Plaid canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`
- Research branch: `research/sp-interrupt-root-compose-gpt56sol`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`
- Prior executed root contract: `research/interrupt-roots-gpt56sol-20261009` final tested head `716b0dc18a8bd0427dfa7c629b1bd3d5952d0ad1`, Actions run `37915315945`.

No reference implementation source is copied into Plaid production code and no reference is treated as hardware truth.

## Source-backed causal map

### 1. SP has two producer classes in pinned ares

Pinned ares `RSP::BREAK()` always sets RSP `halted` and `broken`, but calls `mi.raise(MI::IRQ::SP)` only when `status.interruptOnBreak` is set.

Separately, a write to `SP_STATUS` can directly lower or raise `MI::IRQ::SP` with the clear/set interrupt command bits. Therefore BREAK, HALT and BROKE are not necessary conditions for an SP interrupt. Conversely, BREAK/HALT/BROKE are not sufficient: BREAK with interrupt-on-break disabled produces no SP interrupt.

A repository-wide exact-pin search for `MI::IRQ::SP` found the executable raise/lower sites in `rsp/io.cpp` and `rsp/interpreter-ipu.cpp`; the remaining occurrence is debugger labeling.

### 2. Set+clear command pairs are operations but leave the selected state unchanged

For SP interrupt, interrupt-on-break, halt and related SP_STATUS pairs, pinned ares applies a change only when one command bit is set without its opposite.

Pinned n64-systemtest independently encodes this expectation for the SP interrupt and interrupt-on-break controls: after establishing both high and low states, writing both set and clear bits together must leave the prior state unchanged. Its `SP Set/Clear Interrupt` test also directly checks that SP_STATUS set/clear changes `MI_INTR.SP`.

This matters for provenance: the command operation happened, but visible before/after value equality is not evidence that no operation occurred.

### 3. MI source identity is lost by the shared CPU RCP pending bit

Pinned ares stores each MI source line and mask separately. `MI::poll()` computes an OR across `SP/SI/AI/VI/PI/DP` after each source's mask, then writes the single CPU RCP pending bit.

Consequently `Cause.IP2 == 1` is not an SP provenance token. PI or any other enabled MI source can keep IP2 high after SP has been cleared. Multiple sources can also contribute simultaneously. A sound receipt must retain the source-line contributor set, not reverse-infer one source from the shared pending value.

Pinned Gopher64 independently has the same coarse split: SP_STATUS/BREAK updates `MI_INTR.SP`; `MI_INTR & MI_INTR_MASK` controls the shared RCP interrupt state.

### 4. MI mask and CPU gate are independent generations

Pinned ares MI mask writes change the SP mask independently and repoll the aggregate line. Thus an SP assertion can occur while masked, remain asserted, and become CPU-pending later when the SP mask is enabled. The causal receipt must not collapse the SP assertion generation into the later mask operation.

The completed executed CPU-root experiment established that an admitted CPU root requires `(Cause.IP & Status.IM) != 0`, `IE=1`, `EXL=0`, and `ERL=0`; ares checks this before ordinary instruction fetch and takes the interrupt root at `base + 0x180` where BEV selects the base.

## Minimum receipt for an SP-attributed CPU interrupt root

For this bounded composition, an SP-attributed root needs all of the following causal identities:

1. an SP assertion operation generation, with producer kind:
   - RSP BREAK whose exact event observed interrupt-on-break enabled, or
   - explicit SP_STATUS set-interrupt command;
2. no intervening SP interrupt clear/lower that retires that assertion;
3. the relevant current MI.SP mask/register-operation generation with the SP source enabled;
4. the shared RCP pending state derived from the still-live contributor set, retaining SP as a contributor rather than inferring it from IP2 equality;
5. the CPU Status.IM/IE/EXL/ERL gate generation admitted at the architectural boundary; and
6. the resulting exception-root transfer generation.

If multiple MI sources contribute, the receipt should retain the contributor set. It need not pretend there is one unique producer.

Same-value repeated SP raises and same-value repeated MI mask writes are distinct operation/register generations. Final register equality cannot recover which generation was current at root admission.

## Executable adversarial reducer

`experiments/sp-interrupt-root-compose/model.py` is a deliberately small causal model, not an emulator. It preserves operation generations and tries to falsify snapshot shortcuts with ten deterministic histories.

The cases cover:

- BREAK with interrupt-on-break disabled: HALT/BROKE but no SP root;
- direct SP_STATUS raise without BREAK: valid SP contributor despite no HALT/BROKE;
- SP assertion while masked followed by later MI.SP unmask;
- SP BREAK assertion followed by explicit SP clear, then unrelated PI assertion;
- SP asserted but masked while PI alone drives the shared RCP pending bit;
- repeated same-value SP raises producing distinct assertion generations;
- repeated same-value MI.SP mask writes producing distinct register-operation generations;
- simultaneous set+clear command while state is high and while state is low;
- EXL gating and later release; and
- ERL gating.

Two adversaries directly falsify the naive shortcut `HALT && BROKE && RCP-pending => SP-caused root`: after SP is cleared, PI can produce the root while HALT/BROKE remain set. The converse fails too because direct SP_STATUS raise can produce an SP-attributed root without BREAK.

Canonical deterministic case JSON SHA-256:

`c9c3afdc46c2e2ae0a11107b9590c8cad2896f56cebf719c29dbfcd40fb85dcc`

## Exact-pin guard and CI evidence

`experiments/sp-interrupt-root-compose/source_guard.py` fails closed unless all three reference worktrees are at the exact `refs.lock.toml` revisions and the causal source paths above still contain the guarded contracts.

Branch-only Actions workflow:

`.github/workflows/research-sp-interrupt-root-compose.yml`

Successful run:

- run `38046194852`
- job `114196112531`
- tested head `ceab5c2641ab947b12ca967ac952cb20312e9078`
- evidence artifact `11666893593`
- artifact ZIP digest `sha256:c6417985d6bc647edd74d426c11f9bebf31667957412d57a54204ef1035452d4`

The job fetched the exact ares, Gopher64 and n64-systemtest pins, byte-compiled both Python tools, ran the ten-case falsifier, ran every source guard, hashed the textual receipts and uploaded them.

## Prior research composed or challenged

Composed:

- `research/ares-maskable-interrupt-roots.md`: exact executed ares CPU gate/root matrix, which explicitly left device-specific producer reachability open;
- existing RSP execution/microcode work only as context for the fact that an RSP instruction event and an SP interrupt event are distinct evidence classes.

Challenged/rejected proof shortcuts:

- BREAK implies SP interrupt;
- HALT/BROKE implies SP interrupt;
- SP interrupt implies BREAK;
- current `MI_INTR.SP` value identifies its producer operation;
- CPU `Cause.IP2` identifies SP as the producer;
- equal before/after SP/MI values imply no operation occurred; and
- a root may be attributed to the latest/equal-looking device event without preserving the assertion, mask and CPU-gate chronology.

## Closed-world impact

A whole-ROM certificate cannot exclude the BEV-sensitive general interrupt handler merely because no PI/SI/VI/etc. producer was found. Reachable RSP BREAK with interrupt-on-break enabled or reachable SP_STATUS set-interrupt is independently sufficient to create an SP source line. If that line can coexist with an enabled MI.SP mask and the CPU interrupt gate, the already-validated general `base + 0x180` root remains reachable.

Conversely, simply finding BREAK or HALT/BROKE is not enough to require an SP-caused root. A certificate may discharge this producer only with causal evidence that every reachable producer path cannot establish a live SP assertion at an admissible CPU boundary, or that a mask/gate invariant prevents admission.

Because MI compresses sources into a shared RCP pending bit, whole-ROM root evidence should carry a contributor set or equivalent source-specific lineage through the MI join. A single pending-bit generation is insufficient provenance.

## Remaining gap

- This worker did not execute new physical N64 hardware evidence. n64-systemtest was source-audited at the exact pin, not run on hardware here.
- The SP producer side is source-validated in exact pinned ares and independently corroborated by pinned Gopher64/n64-systemtest; the CPU root side is composed from the prior unmodified-ares executed fixture rather than rebuilt in this branch.
- Exact asynchronous scheduling relative to arbitrary CPU/RSP instruction boundaries, delay slots and device synchronization remains outside this reducer.
- Save/restore, reset/NMI and frontend/debugger mutation can cut or resurrect device/register chronology and must be joined to the existing restore/lifetime evidence rather than assumed monotonic.
- This does not prove handler-byte provenance, handler immutability, RSP microcode provenance or whole-ROM executable closure by itself.
- Emulator/reference agreement is not promoted to hardware truth.

## Reproduction

With the exact references checked out under `.refs/{ares,gopher64,n64-systemtest}`:

```bash
python3 -m py_compile experiments/sp-interrupt-root-compose/model.py \
  experiments/sp-interrupt-root-compose/source_guard.py
python3 experiments/sp-interrupt-root-compose/model.py
python3 experiments/sp-interrupt-root-compose/source_guard.py
```

The branch workflow performs those commands after fetching the exact pins.

## Integration recommendation

**ADOPT** the causal proof obligation, not the research model as production architecture. A future interrupt-root certificate should preserve source-specific assertion/clear identity through MI, MI-mask operation identity, the contributor set feeding RCP pending, CPU gate identity and root-transfer identity. Do not infer SP provenance from BREAK/HALT/BROKE, `MI_INTR.SP`, `Cause.IP2`, equal values or nearest/latest events.
