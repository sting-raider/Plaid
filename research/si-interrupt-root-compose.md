# SI/PIF completion -> MI.SI -> CPU interrupt-root composition

Date: 2026-10-11

Result: **VALIDATED** for the bounded exact-pinned reference scope below.

## Question

What causal evidence is sufficient to connect an N64 Serial Interface operation to a
maskable CPU interrupt root without laundering provenance through final status-bit
equality?

This composes the already-validated maskable VR4300 interrupt gate/root contract with
an actual SI producer path. The important negative question is equally central: does
an observed SI interrupt / MI.SI / Cause.IP2 state prove that the producer was an SI
DMA completion?

## Exact inputs

- Plaid canonical base inspected before the claim:
  `211176e7a489fecf8331d02915ee982cd279cb62`
- Isolated research branch:
  `research/si-interrupt-root-compose-gpt56sol`
- Code-tested branch head:
  `6d0cdfac79bddff6e1aca8d24de01e4393213db7`
- Exact ares revision from `refs.lock.toml`:
  `9408cb43d4948fc3ea6e152a307a34348df3fe04`
  - `ares/n64/si/dma.cpp` blob
    `c2690ab2b0d4adaaec233871be98bea04b63d92b`
  - `ares/n64/si/io.cpp` blob
    `9fd94bb082cb8cf4a70313a62df23b903ad1d7a5`
  - `ares/n64/mi/mi.cpp` blob
    `5c2421cc7d9cc9c62b6d9445c978bb1c1d58a4c9`
  - `ares/n64/cpu/cpu.cpp` blob
    `41964d49c8983ae9a97b25625174cd4c4316c4a8`
  - `ares/n64/cpu/exceptions.cpp` blob
    `870e7d420f38fbda862cb4c7cb88481155b19251`
- Exact independent Gopher64 revision from `refs.lock.toml`:
  `e96debac941a26ba4961e5145056c0821d3a56f7`
  - `src/device/si.rs` blob
    `35460182400db0bd2cf28299e5bc5f7a69dd118d`
  - `src/device/mi.rs` blob
    `ae3cfdb3e706a50b0ecbe02754cf0380cfaab94a`

No upstream emulator source was patched for the executable matrix.

## Prior research composed

This lane composes `research/ares-maskable-interrupt-roots.md`, which established on
an exact pinned ares interpreter fixture, with independent Gopher64 source agreement,
that architectural maskable interrupt entry requires:

1. `(Cause.IP & Status.IM) != 0`;
2. `Status.IE == 1`;
3. `Status.EXL == 0`; and
4. `Status.ERL == 0`.

That prior result intentionally left device-specific producer reachability open.
This experiment fills one bounded part of that gap for SI while challenging any
proof rule that equates a final SI pending value with a unique SI-DMA cause.

## Exact source composition

### ares SI DMA request and completion

At the exact pin, writes to the SI read/write DMA registers set SI DMA state and
schedule distinct queue events `Queue::SI_DMA_Read` and `Queue::SI_DMA_Write`.
CPU queue dispatch sends those event kinds to `SI::dmaRead()` and `SI::dmaWrite()`.

Those completion routines first execute the real PIF/RDRAM transfer, then clear the
SI DMA busy/state fields, set `io.interrupt = 1`, and call
`mi.raise(MI::IRQ::SI)`.

Writing `SI_STATUS` is a distinct acknowledgement operation: it sets
`io.interrupt = 0` and calls `mi.lower(MI::IRQ::SI)`.

### ares MI and CPU gate

`MI::poll()` does not promote an SI line unconditionally. It composes
`irq.si.line & irq.si.mask` into the RCP line and passes the result to
`cpu.setInterruptPending(CPU::Interrupt::RCP, line)` (Cause.IP2 in this mapping).
The existing CPU gate then additionally requires Status.IM2, IE, !EXL and !ERL
before selecting the ordinary BEV-sensitive general vector.

### Independent Gopher64 agreement

The exact pinned Gopher64 source independently models SI DMA as a scheduled
`EVENT_TYPE_SI`. Its DMA event clears the busy state, sets the SI interrupt latch,
and raises `MI_INTR_SI`; an SI-status write clears the latch and lowers the MI
source. Its MI path similarly connects the enabled RCP interrupt state to CPU
Cause.IP2. This is independent implementation agreement, not hardware truth.

## Falsification: the SI pending state is not unique DMA provenance

Pinned ares exposes another SI producer path: a direct PIF bus write schedules
`Queue::SI_BUS_Write`, whose queue dispatch calls `SI::writeFinished()` rather than
an SI DMA completion routine. `writeFinished()` nevertheless clears SI busy state,
sets the same `io.interrupt` latch, and raises the same `MI::IRQ::SI` source.

The executable matrix therefore includes a deliberate equal-state decoy:

- one history performs a real SI DMA read completion;
- the other performs a direct PIF bus-write completion;
- immediately before the CPU boundary, both histories have equal observed values
  for SI interrupt, MI.SI line, MI.SI mask and CPU Cause.IP2;
- both can legitimately enter the same CPU interrupt vector;
- their producer identities are different.

Therefore final SI/MI/Cause values authenticate **root availability**, subject to the
masks/gate, but do **not** authenticate the claim “this root was caused by SI DMA”.
Producer event identity must survive the composition.

## Executable fixture

`experiments/si-interrupt-root-compose/driver.cpp` boots the exact unmodified pinned
ares N64 core headlessly with CPU and RSP recompilers disabled and identity RDRAM.
It plants:

```text
ADDIU $s0,$zero,0x1234
```

at uncached KSEG1 PC `0xffffffffa0000000` and uses one CPU instruction boundary as a
causal discriminator:

- interrupt taken first: `$s0 == 0`, EPC receives the planted PC, EXL becomes one,
  and PC becomes the general interrupt vector;
- interrupt suppressed: the planted instruction retires, `$s0 == 0x1234`, and PC
  advances by four.

All RCP interrupt sources are explicitly lowered before each case. SI DMA transfers
use RDRAM buffer `0x1000`, deliberately disjoint from the planted CPU code.

The runner executes every case twice and requires byte-identical JSON.

## Matrix

The 13 exact-pinned cases cover:

- SI DMA read completion with BEV=0;
- SI DMA read completion with BEV=1;
- SI DMA write completion;
- DMA request without completion;
- SI completion with MI.SI mask disabled;
- SI completion with CPU Status.IM2 disabled;
- SI completion with IE disabled;
- SI completion with EXL set;
- SI completion with ERL set;
- completion followed by SI_STATUS acknowledgement before the CPU boundary;
- acknowledgement with no preceding completion;
- completion -> acknowledgement -> a second completion;
- direct PIF bus-write completion as an equal-final-state non-DMA producer decoy.

Observed results matched the composed causal rule in all 13 cases.

When a live SI producer, MI.SI mask, Status.IM2, IE and !EXL/!ERL all composed, CPU
entry occurred before the planted instruction. The BEV vectors were exactly:

- BEV=0: `0xffffffff80000180`
- BEV=1: `0xffffffffbfc00380`

A request without completion did not assert the SI interrupt. MI-mask-off left the
SI and MI source latched but kept Cause.IP2 low. CPU-IM-off, IE-off, EXL and ERL
controls retained the upstream SI/MI pending state but suppressed architectural
entry. SI_STATUS acknowledgement cleared the live pending source before the CPU
boundary. A second completion after acknowledgement reasserted the source and was a
new live generation.

Architectural CPU entry did not itself acknowledge the SI source: in taken cases the
SI/MI pending state remained asserted after the entry boundary.

## Generation-aware adversarial replay

`experiments/si-interrupt-root-compose/model.py` encodes the minimum causal
composition separately from the emulator fixture. It keeps distinct:

- SI completion generation;
- SI producer kind (`dma` versus direct `bus` completion);
- SI acknowledgement/clear generation;
- MI-mask write generation;
- live SI pending state;
- RCP pending state; and
- CPU gate state.

A root certificate may bind to an SI producer only when the claimed producer kind
and completion generation are still live at the CPU boundary. The replay actively
rejects:

- a deleted completion;
- a direct bus completion relabelled as DMA;
- a stale completion generation after ACK and recompletion;
- a claimed root after acknowledgement;
- a claimed root with MI.SI masked; and
- a claimed root with CPU Status.IM2 masked.

It also records repeated same-value MI-mask writes as distinct operation generations;
value equality is not permission to erase history.

Final model result:

```text
MODEL_SHA256=16ae3b129402fa97fe4b2c0376e845d761aa1b90691394682751794c69bc3b72
PASS: 11 causal controls and 6 forged histories
```

## Dynamic evidence

Final fail-closed GitHub Actions run:

- run: `38098592427`
- job: `114349611177`
- code-tested head: `6d0cdfac79bddff6e1aca8d24de01e4393213db7`
- result payload SHA-256:
  `c1fb6f6f15b5bd45f260591bb97a48c7a2aa8917b8a3c497f6adc1f95472b78e`
- model log SHA-256:
  `873ad7b3f663f76790e4399dcb90bc7a74d743b1860dceb287431fce2ff7c65f`
- executable-run log SHA-256:
  `a2a10a1279a8b0a5c950c284549c2cf007008e294b2058a7153ad66f88493a39`
- artifact ID: `11686983140`
- uploaded artifact ZIP digest:
  `sha256:a6245aceefc9665aaa7878913219a3e9d0674e00cd13f9611010d098e8bfe2e2`

The final workflow uses `set -o pipefail` for piped verifier commands so a failing
Python verifier cannot be hidden by a successful `tee` process.

## Diagnostic failure that was intentionally not accepted as evidence

Initial run `38098446139` found a fixture error: the first harness placed both the
CPU sentinel instruction and the SI DMA destination at RDRAM address zero. A real SI
read completion correctly overwrote the planted instruction, so a suppressed
interrupt advanced PC while `$s0` remained zero. That was fixture self-interference,
not evidence about interrupt gating.

That run also exposed a workflow bug in the research scaffold: `python ... | tee`
without `pipefail` made the matrix step appear successful despite the Python
assertion failure. The later hash step failed because no result payload existed.

Both issues were fixed before accepting evidence: SI DMA moved to disjoint RDRAM
`0x1000`, and all piped verifier steps were made fail-closed. Run `38098446139` is
therefore diagnostic-only and must not be cited as semantic validation.

## Sound certificate rule for this bounded path

A future whole-ROM certificate attributing a CPU interrupt root specifically to SI
DMA should retain, at minimum, ordered evidence for:

1. the SI request identity and operation kind;
2. the matching SI completion event generation and producer kind;
3. any intervening SI_STATUS acknowledgement/clear generation;
4. the live MI.SI source and MI-mask generation;
5. the CPU Cause.IP2 / Status.IM2 state and IE/EXL/ERL gate at the relevant boundary;
6. the resulting exception-root transfer.

If the producer kind or completion generation is UNKNOWN, the provenance claim must
remain UNKNOWN even if SI interrupt, MI.SI and Cause.IP2 happen to have the expected
values. If an acknowledgement cuts a generation, a later completion is a new
generation rather than a resurrection of the old one.

## Exact reproduction

With `.refs/ares` and `.refs/gopher64` checked out to the exact revisions above:

```bash
python3 experiments/si-interrupt-root-compose/source_guard.py
python3 -m py_compile \
  experiments/si-interrupt-root-compose/model.py \
  experiments/si-interrupt-root-compose/run.py
python3 experiments/si-interrupt-root-compose/model.py
python3 experiments/si-interrupt-root-compose/run.py
sha256sum target/si-interrupt-root-compose/results.json
```

The branch-only workflow
`.github/workflows/research-si-interrupt-root-compose.yml` performs the exact pin
fetch, source/blob guards, adversarial replay, executable matrix, hashes and artifact
upload.

## Closed-world impact

**VALIDATED, bounded:** an SI DMA completion can be composed causally through the
SI interrupt latch, MI.SI mask, CPU RCP/IP2 mask and CPU interrupt gate to the
BEV-sensitive general CPU interrupt root. An SI request/busy state alone cannot do
so, an acknowledgement can cut the live generation before entry, and a later
completion creates a distinct generation.

More importantly, the same final SI/MI/IP2 values can be produced by a non-DMA SI
bus completion. A closure solver must therefore preserve producer identity rather
than infer DMA provenance from final interrupt values.

This reduces one device-specific root uncertainty but does not close WholeRom.

## Limitations / remaining gap

- No physical N64 hardware was run. ares is the executed oracle and Gopher64 is an
  independent exact-pinned source cross-check, not hardware truth.
- The fixture issues real SI request setup and invokes the exact pinned completion
  methods directly rather than waiting the scheduled queue delay. Exact queue event
  -> completion-method dispatch is source-guarded, but arbitrary timing races are
  not exhausted.
- The direct PIF bus-write producer was included specifically to falsify unique-DMA
  inference, but this is not claimed to be a complete census of every SI/PIF event
  source under every peripheral configuration.
- Delay-slot arrival timing, simultaneous device producers, save/restore chronology,
  reset/NMI interactions and arbitrary interleavings remain outside this bounded
  experiment.
- This does not establish provenance or immutability of the handler bytes reached at
  the general vector for an arbitrary ROM.
- Dynamic observations are not exhaustive whole-ROM reachability and are not a
  closed-world proof by themselves.

## Integration recommendation

**ADOPT the evidence-model invariant, not final-value inference.** Represent SI
producer/completion identity and acknowledgement as explicit ordered generations,
then compose the live generation with MI and CPU gate evidence. Do not infer
“SI DMA caused this interrupt root” solely from SI_STATUS, MI_INTR or Cause.IP2
values, even when all three agree. Keep the obligation OPEN when producer identity
or chronology is missing.

No production Plaid code was changed and nothing was merged into `main`; the primary
integrator can selectively adopt the invariant and fixtures.