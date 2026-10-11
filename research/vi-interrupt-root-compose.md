# VI interrupt producer -> MI -> CPU executable-root composition

Status: **VALIDATED (bounded reference-semantic composition; hardware-exact VI phase remains OPEN)**

Worker: `gpt56sol-vi-interrupt-root-compose-20261011`

Canonical Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/vi-interrupt-root-compose-gpt56sol`

Exact reference revisions from `refs.lock.toml`:

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

No upstream reference source was patched.

## Question

Can a VI-caused CPU interrupt root be certified from a causal producer history rather than inferred from equal final MI/Cause values?

The bounded hypothesis was that Plaid eventually needs a source-specific proof chain of the form:

```
VI producer event generation
  -> live MI.VI source generation
  -> VI source mask
  -> CPU RCP/IP2 pending
  -> CPU IM2 + IE + !EXL + !ERL
  -> BEV-selected general exception vector
```

with a VI acknowledgement cutting the live producer generation, and with final register equality explicitly insufficient to authenticate that provenance.

## Exact pinned ares source contract

At `9408cb43...`:

- `ares/n64/vi/vi.hpp`: VI is active when `io.colorDepth != 0`.
- `ares/n64/vi/vi.cpp`: `VI::main()` advances `io.vcounter` and raises `MI::IRQ::VI` on its modeled coincidence condition. Progressive and interlaced cases have distinct half-line/field logic.
- `ares/n64/vi/io.cpp`:
  - `VI_V_INTR` programs `io.coincidence`.
  - any write to `VI_V_CURRENT_LINE` calls `mi.lower(MI::IRQ::VI)`; the written payload is not used to decide whether the interrupt is cleared.
- `ares/n64/mi/mi.cpp`: the RCP CPU line is the OR of source `line & mask` pairs, including `irq.vi.line & irq.vi.mask`, then is forwarded with `cpu.setInterruptPending(CPU::Interrupt::RCP, line)`.
- the already-validated CPU maskable-interrupt gate requires a pending bit intersecting Status.IM plus IE and `!EXL && !ERL`, and the general-vector path uses offset `0x0180` from the BEV-selected base.

`experiments/vi-interrupt-root-compose/source_guard.py` pins both the exact revisions and the ares blobs used by this argument so source drift fails closed.

## Independent Gopher64 comparison and preserved disagreement

At `e96debac...`, Gopher64 independently agrees on the source latch/acknowledgement boundary:

- its scheduled `EVENT_TYPE_VI` path calls `set_rcp_interrupt(... MI_INTR_VI)`;
- a `VI_CURRENT_REG` write calls `clear_rcp_interrupt(... MI_INTR_VI)` regardless of payload;
- `MI_INTR_VI` is source bit 3 and the MI mask ultimately controls CPU `COP0_CAUSE_IP2`.

However, the exact interrupt **phase model is not the same as ares**. ares expresses the VI raise through live `vcounter/coincidence` scanline/half-line logic, while this Gopher64 revision schedules a vertical interrupt event and uses VI timing registers differently around screen scheduling.

Therefore this note does **not** claim that either emulator's exact VI interrupt phase is hardware truth. The independently supported shared contract is narrower: VI is a distinct MI source, it latches into the RCP interrupt path, and a VI CURRENT write acknowledges/clears that source.

## Hardware/system-test check

The exact pinned n64-systemtest tree was inspected for a VI interrupt oracle. It contains `src/graphics/vi.rs`, including VI register definitions and ordinary video initialization (`VIntr` is written as `2`), but its `src/tests` tree has no `vi` test directory and the registered test list contains no VI interrupt timing test at this revision.

That means the ares/Gopher64 interrupt-phase disagreement remains a real open evidence gap rather than something this lane can paper over.

## Executable experiment

Artifacts:

- `experiments/vi-interrupt-root-compose/driver.cpp`
- `experiments/vi-interrupt-root-compose/run.py`
- `experiments/vi-interrupt-root-compose/model.py`
- `experiments/vi-interrupt-root-compose/source_guard.py`
- `.github/workflows/research-vi-interrupt-root-compose.yml`

The C++ fixture builds against exact pinned ares and invokes the real `VI::main()` path to obtain an actual ares VI coincidence-produced MI.VI assertion. It then composes that source through the MI mask and the existing CPU interrupt gate. Each matrix case is executed twice and must produce byte-identical JSON.

Fourteen exact-pinned cases passed:

1. actual VI producer, BEV=0;
2. actual VI producer, BEV=1;
3. VI configuration only, no producer event;
4. VI producer with MI.VI mask disabled;
5. VI producer with CPU IM2 disabled;
6. VI producer with IE disabled;
7. VI producer with EXL set;
8. VI producer with ERL set;
9. VI producer then VI CURRENT acknowledgement with payload `0`;
10. VI producer then VI CURRENT acknowledgement with payload `0xdeadbeef`;
11. acknowledgement with no producer;
12. producer -> acknowledgement -> fresh producer;
13. direct `mi.raise(MI::IRQ::VI)` decoy with no VI timing producer;
14. AI interrupt decoy that reaches the same CPU RCP/IP2 gate.

### Positive root

With the real VI producer and all gates enabled:

- MI.VI becomes asserted;
- CPU RCP/IP2 becomes pending;
- CPU enters the general exception vector before the sentinel instruction executes;
- BEV=0 reaches `0xffffffff80000180`;
- BEV=1 reaches `0xffffffffbfc00380`;
- EPC captures the original PC;
- Cause.ExcCode is interrupt (`0`), BD is cleared for this fixture, and EXL becomes set.

### Negative gates

A VI source assertion alone is insufficient:

- with MI.VI mask disabled, MI.VI can be latched while CPU IP2 remains deasserted;
- with CPU IM2 disabled, IP2 can be pending but the instruction executes normally;
- IE=0, EXL=1, or ERL=1 likewise suppresses interrupt entry.

This composes the VI producer with the previously validated generic CPU maskable-interrupt gate rather than re-proving that gate from final register snapshots.

## Acknowledgement is an operation boundary, not a value fact

After an actual VI producer, both of these writes clear the live source before CPU delivery:

```
VI_CURRENT <- 0x00000000
VI_CURRENT <- 0xdeadbeef
```

The pre-CPU architectural snapshots are identical after both acknowledgements. The payload difference is irrelevant to the clear operation.

Conversely, `V_INTR` programming by itself does not raise the source in the executable fixture.

A proof model must therefore retain the acknowledgement **operation generation** even when register values or final snapshots do not expose that an operation happened. Same values do not imply same history.

## Adversarial provenance attacks

### Equal MI/Cause state with a forged producer

The strongest decoy directly calls `mi.raise(MI::IRQ::VI)` without executing a VI timing producer.

Immediately before CPU delivery, the real VI-producer case and the decoy have the same relevant state:

```
MI_INTR = 0x08
MI_MASK = 0x08
Cause.IP = 0x04
```

Both take the same CPU interrupt root.

But only the real case has a VI producer event. This is an executable counterexample to any rule that authenticates VI provenance from final MI/Cause equality.

### Same CPU IP2 from another RCP source

An AI-source decoy yields CPU RCP/IP2 pending and takes the same general exception root while MI.VI is not asserted. CPU IP2 therefore proves only that some enabled RCP source exists; it does not identify VI.

### Generation replay/forgery model

`model.py` separately tracks:

- VI producer generations;
- VI acknowledgement generations;
- `V_INTR` programming generations;
- source-mask write generations.

It passed 13 causal controls and rejected 7 forged histories, including:

- deleted producer event;
- direct MI.VI state relabelled as a timing producer;
- AI root relabelled as VI;
- stale producer generation reused after acknowledgement plus retrigger;
- a root claimed after acknowledgement;
- a root claimed with VI mask disabled;
- a root claimed with CPU IM2 disabled.

Repeated equal `V_INTR` programming writes are retained as distinct operations but do not manufacture a producer generation.

## Evidence receipts

GitHub Actions run: `38104242787`

Job: `114366242041`

Head under test: `6552d1f91c300fb8cbe5d9a62b2d3da861c13a70`

Conclusion: **success**

Causal replay:

```
MODEL_SHA256=defebe8a5dc8c05a240da402bba9c807f29b2a4b4da258be1cb31687b36f15d9
PASS: 13 causal controls and 7 forged histories
```

Exact ares matrix:

```
RESULT_SHA256=3d2b52b77afaa6e100245a4a71830563463248bb0dbc99a8b3fdc36b5aa94827
PASS: 14 exact-pinned VI/MI/CPU composition cases repeat byte-identically
```

Durable evidence hashes:

```
3d2b52b77afaa6e100245a4a71830563463248bb0dbc99a8b3fdc36b5aa94827  target/vi-interrupt-root-compose/results.json
7b9cc70becd49c6613f454ed0230bcf252f1c3d9c4ff8283d45a7dcd435282ca  target-vi-model.log
581cec73f5e2c04fe6d97e5a7a11c9d157ee06a4e9f8cd028eec32154e30adc4  target-vi-run.log
```

Uploaded evidence artifact:

- name: `vi-interrupt-root-compose-evidence`
- artifact id: `11689260687`
- zip SHA-256: `fabd25f26f12e0c8164f56669ddac258ae470d354e6e9caf0a67a5b4471a1b94`

## Closure invariant supplied by this lane

For a bounded VI-caused CPU executable root, a defensible certificate must not stop at CPU Cause.IP2 or even MI.VI equality. It needs source-specific causal evidence equivalent to:

1. a VI producer generation exists;
2. that generation caused the live MI.VI source assertion;
3. no later VI acknowledgement generation invalidated it before delivery;
4. MI.VI source masking permits propagation;
5. CPU IM2 and IE permit delivery while EXL and ERL do not suppress it;
6. the resulting root is the BEV-selected general exception vector;
7. the handler bytes/lifetime reached by that root are independently proven by the normal executable provenance machinery.

If any of those proof obligations is absent, VI-specific root attribution remains OPEN.

## Composition with prior Plaid research

This lane composes rather than replaces:

- the completed exact-ares maskable CPU interrupt-root work, which established the generic CPU IE/IM/EXL/ERL and BEV-sensitive vector gate;
- neighboring PI/SP/SI source-composition work, used only as precedent for source-specific producer generations;
- ADR-0009 style deletion/fabrication resistance: removing the producer, inserting an acknowledgement, or relabelling equal state must not preserve a source-specific certificate;
- the whole-ROM requirement that exception/interrupt roots be complete before CLOSED can be claimed.

## Closed-world impact

This removes one bounded uncertainty: in Plaid's evidence model, VI root provenance cannot safely be represented as a final MI/Cause snapshot. It requires a source-specific VI producer generation and an acknowledgement/lifetime boundary before composing with the generic CPU root gate.

The result also gives future instrumentation a concrete falsification target: a certificate implementation that accepts the direct-MI.VI equal-state decoy or the AI same-IP2 decoy is unsound.

This does **not** close whole-ROM execution-root completeness. No flag should waive the missing integration or hardware-phase evidence.

## Remaining gaps

1. Hardware/system-test evidence for the exact VI interrupt phase, especially interlaced half-line/field edge cases and timing-register reprogramming races. The pinned emulators disagree in modeling detail and pinned n64-systemtest does not currently supply this oracle.
2. Production instrumentation that emits stable VI producer, acknowledgement, and source-mask generations into Plaid evidence rather than only this research fixture.
3. Composition with save/restore/reset chronology for a pending VI source.
4. Multi-source RCP ordering and acknowledgement histories when several MI sources are simultaneously live. This lane proves source ambiguity with decoys but does not exhaust all concurrency histories.
5. Whole-ROM enumeration of every interrupt producer plus handler byte provenance/lifetimes.

## Integration recommendation

Do not merge a production semantic shortcut from this branch. Preserve the research fixture/model and use them as a regression oracle when a unified interrupt-root certificate is introduced.

That production certificate should record primitive source operations, not reconstruct them from equal values:

- VI producer event generation;
- VI acknowledgement (`VI_CURRENT` write) generation;
- MI.VI source-line generation;
- MI.VI mask-operation generation;
- CPU delivery gate/context generation;
- resulting executable-root identity.

Until hardware evidence resolves the exact phase disagreement, keep exact VI timing semantics outside the closed-world claim. The shared source/ack/mask/root composition is validated; precise hardware trigger phase remains OPEN.

## Reproduction

With exact refs available under `.refs/` as used elsewhere in Plaid research:

```sh
python3 experiments/vi-interrupt-root-compose/source_guard.py
python3 experiments/vi-interrupt-root-compose/model.py
python3 experiments/vi-interrupt-root-compose/run.py
```

Or run `.github/workflows/research-vi-interrupt-root-compose.yml` on the research branch.
