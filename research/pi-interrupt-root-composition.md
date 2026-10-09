# PI DMA byte effects and interrupt-root provenance are distinct causal chains

Status: **VALIDATED for the bounded source-composition/replay scope**. This note does
not promote ares queue mechanics to N64 hardware truth.

Worker: `gpt56sol-pi-interrupt-root-compose-20261010`

## Exact inputs

- Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`
- branch: `research/pi-interrupt-root-compose-gpt56sol`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Mupen64Plus Core: `ba95bab92a76744753bfe61470823a4937850ab0`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`

This composes two already-established results rather than reopening them:

1. `research/pi-request-queue-causal-token.md`: in pinned ares an accepted PI DMA
   request calls `queueInsert()` and then performs its byte transfer immediately;
   queue insertion can silently fail, so byte effects do not imply a completion
   event exists.
2. `research/ares-maskable-interrupt-roots.md`: CPU interrupt entry requires a
   matching Cause.IP/Status.IM bit, Status.IE=1 and EXL=ERL=0, then enters the
   BEV-sensitive general vector at `base + 0x180`.

The missing seam was whether PI byte provenance, PI completion, MI pending/masking
and CPU root reachability may be collapsed into one identity. They may not.

## Exact pinned ares causal path

### 1. Accepted DMA request and byte effect

`ares/n64/pi/io.cpp` handles `PI_READ_LENGTH` / `PI_WRITE_LENGTH` by setting
`dmaBusy`, recording `originPc`, calling `CPU::queueInsert(...)`, then immediately
calling `dmaRead()` / `dmaWrite()`.

`ares/n64/cpu/cpu.cpp::queueInsert()` returns silently if the bounded queue rejects
insertion. Therefore the following history is real in the pinned implementation:

```text
accepted PI request
  -> queue insertion rejected
  -> PI byte transfer still executes
  -> no PI queue event exists
  -> no later dmaFinished() from this request
```

A PI byte effect is consequently neither a completion witness nor an interrupt
producer witness.

### 2. Queued completion creates the raw PI interrupt generation

`CPU::synchronize()` dispatches surviving `PI_DMA_Read` / `PI_DMA_Write` queue
events to `PI::dmaFinished()`. `dmaFinished()` clears busy, sets PI's local
interrupt flag, then calls `mi.raise(MI::IRQ::PI)`.

This completion event, not byte equality and not the immediate copy, is the causal
producer of the raw MI PI line in the pinned ares path.

### 3. MI masking is a separate generation

`MI::raise(PI)` sets `irq.pi.line=1` and calls `MI::poll()`. `poll()` derives the
CPU RCP pending level from `irq.<source>.line & irq.<source>.mask` and calls
`CPU::setInterruptPending(CPU::Interrupt::RCP, line)`.

`MI_INTR_MASK` writes can later clear or set the PI mask and always repoll. Thus a
PI completion while PI is masked can leave the raw PI line pending while CPU RCP
pending remains false. A later mask-set write can expose that *older completion*
to the CPU without a new DMA or new PI completion.

Same-value mask writes are operations too: a set command when the mask is already
set still executes `poll()`. A proof may not delete that operation merely because
the before/after mask bit is equal.

### 4. CPU root entry is yet another gate

`CPU::setInterruptPending()` updates Cause pending and calls `interruptPoll()`.
Actual interpreter entry is checked at `CPU::instruction()` before instruction
fetch. It requires an intersecting Cause.IP/Status.IM plus IE=1, EXL=0, ERL=0,
then calls the ordinary interrupt exception path. Prior validated root research
established the BEV-sensitive `base+0x180` targets.

Therefore the minimum bounded causal chain is:

```text
accepted PI request identity
  -> successful PI queue insertion identity
  -> dispatched PI completion identity
  -> raw MI.PI line generation
  -> MI mask/poll generation producing CPU RCP pending
  -> CPU Status gate generation at an architectural boundary
  -> interrupt root-transfer generation (base + 0x180)
```

The PI byte-transfer witnesses hang from the request identity as a *parallel byte
provenance branch*. They are not a substitute for any node in the interrupt branch.

## Acknowledgement, cancellation and restore boundaries

- PI status interrupt-clear lowers the raw MI PI line and repolls CPU pending.
  If this happens before an eligible CPU boundary, the old completion cannot by
  itself justify a later root transfer.
- PI status reset/cancel removes queued PI DMA events in pinned ares but is not the
  PI interrupt acknowledgement command. Cancellation can therefore leave the
  already-performed byte effect while eliminating its future completion.
- Pinned ares serializes PI's local interrupt flag and MI's PI line/mask as stored
  state. A restored equal bit pattern is not causal evidence for the pre-save
  completion. A future portable certificate needs explicit save/restore chronology
  or must cut producer ancestry to UNKNOWN at an unsupported restore boundary.

## Cross-reference source comparison

Exact pinned Mupen64Plus and Gopher64 independently preserve the coarse separation:
PI DMA performs/schedules a transfer, an end-of-DMA event raises PI interrupt state,
MI keeps raw PI pending separate from `MI_INTR_MASK`, interrupt-clear lowers it,
and CPU interrupt logic additionally applies CPU status gating before the ordinary
`+0x180` path.

Do **not** infer hardware queue saturation or exact scheduling from this agreement.
Ares's 512-entry queue and silent insertion failure are implementation facts used
to falsify an unsafe Plaid evidence shortcut. Mupen/Gopher use different event
machinery. The portable invariant is only that byte-transfer identity, device
completion/pending identity, MI mask identity and CPU interrupt-entry identity are
separate causal facts.

There is also a status-register nuance worth preserving rather than smoothing over:
pinned ares PI status reset clears busy/error but not its local interrupt flag,
whereas pinned Mupen/Gopher reset their PI status register to zero without directly
clearing the MI PI raw line. This worker does not declare either detail hardware
truth; root provenance should follow the independently represented MI producer line
and acknowledgement chronology instead of guessing from one PI status snapshot.

## Executable adversaries

`experiments/pi-interrupt-root-compose-gpt56sol/model.py` implements only the above
bounded evidence transitions and actively tries to falsify collapsed reducers.
Deterministic cases cover:

1. queue insertion failure with a real byte copy but no completion/root;
2. cancellation after copy but before completion;
3. completion while MI PI is masked, then later mask-set producing CPU pending;
4. pending MI source with CPU IE disabled, then later CPU enable;
5. interrupt clear before an eligible CPU boundary;
6. an equal-payload later queue-failed copy decoy where the interrupt root still
   belongs to the earlier queued completion; and
7. same-value MI mask repoll preserving the old raw producer while minting a new
   operation/poll generation.

It then runs 64 deterministic seeds x 5,000 random operations (320,000 operations)
with requests, insertion success/failure, completion, cancellation, interrupt clear,
MI mask operations, CPU gate changes and boundaries. Every accepted root is required
to identify an actual prior queued completion generation. The run must also discover
queue-failed copies, copy-without-completion histories, same-value mask operations
and roots whose source is not the latest PI copy.

A local equivalent replay produced:

```text
queue_failed_copies = 6154
histories_with_copy_without_completion = 64 / 64
roots_whose_source_is_not_latest_copy = 56
same_value_mask_operations = 40095
model canonical RESULT_SHA256 = 90187885016ce98b2f8fbcf4104b419c9a2450c182a9d2cd82093b61a9eb0ab2
```

The branch workflow re-runs the committed model and exact source guards against all
three pinned repositories and uploads the receipts.

## Falsified closure shortcuts

The evidence rejects all of these rules:

- `PI copy happened => PI interrupt handler is reachable`;
- `PI completion happened => CPU interrupt root is immediately reachable`;
- `current PI_STATUS interrupt bit => provenance of the root`;
- `current MI.PI line/mask snapshot => provenance of the root`;
- `latest PI copy => producer of a pending PI interrupt`;
- `equal payload/address/length => same request/completion generation`;
- `same-value MI mask write did nothing`.

## Closed-world impact

A whole-ROM certificate that wants to exclude the general interrupt vector cannot
simply prove that PI never writes executable bytes, and a byte-provenance certificate
cannot infer interrupt reachability from a PI copy. Conversely, a PI completion can
make the interrupt root reachable even when the copied bytes are unrelated to code.

For PI specifically, a defensible certificate must either include/prove the general
interrupt handler root or prove that every reachable PI producer chronology is
prevented from satisfying the composed chain. UNKNOWN queue/completion,
acknowledgement, MI mask/pending, save/restore or CPU gate chronology keeps the root
obligation OPEN.

This is a producer/root-reachability obligation, not executable-byte provenance for
the handler itself. Handler bytes, cache-visible state and lifetime remain separate.

## Remaining gaps

- No physical hardware execution was performed.
- This worker did not build a full ares system fixture; the executable replay is a
  source-guarded causal extraction composed with prior full-core interrupt-root and
  PI queue experiments.
- Exact asynchronous cycle/delay-slot timing is not established here.
- Save/restore causal identity is explicitly left OPEN even though exact serialized
  fields were inspected.
- Other MI producers (SP/SI/AI/VI/DP), NMI interactions and timer/software producers
  remain their own contracts; this lane only composes PI.
- The handler's executable byte provenance/lifetime is not proved by root reachability.

## Integration recommendation

**ADOPT the evidence contract, not the standalone model and not ares queue policy.**
A future production trace/certificate should keep at least these identities distinct:

- accepted PI request generation and actual byte effects;
- queue insertion outcome and queued completion generation;
- raw MI PI pending generation and explicit acknowledgement/lower generation;
- MI mask/poll generation that drives CPU RCP pending;
- CPU Status/gate generation at the architectural boundary; and
- root-transfer generation.

Never repair a missing link with equal bytes, current register values or the latest
PI request. If a save/restore or missing event breaks the chain, remain UNKNOWN/OPEN.
