# SP/RSP interrupt producer to CPU root composition

Date: 2026-10-10

Result: **VALIDATED** for the bounded exact-reference/source-composition scope below.

## Question

What evidence is minimally sufficient to attribute a BEV-sensitive CPU maskable-interrupt root to the N64 SP/RSP producer rather than merely observing equal HALT/BROKE, MI or Cause register values?

This starts exactly where the completed `research/ares-maskable-interrupt-roots.md` experiment stopped: that unmodified exact-pinned ares execution established the CPU admission rule and general interrupt root, while explicitly leaving device-specific producer reachability open.

## Exact inputs

- Plaid canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`
- Research branch: `research/sp-interrupt-root-compose-gpt56sol`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`
- Prior executed root contract: `research/interrupt-roots-gpt56sol-20261009` tested head `716b0dc18a8bd0427dfa7c629b1bd3d5952d0ad1`, Actions run `37915315945`.

No reference implementation was patched here and reference agreement is not promoted to hardware truth.

## Source-backed causal map

### SP has two producer classes in pinned ares

Pinned ares `RSP::BREAK()` sets `halted` and `broken`, but raises `MI::IRQ::SP` only when `status.interruptOnBreak` is set. Separately, `SP_STATUS` can directly lower or raise `MI::IRQ::SP` using its clear/set interrupt command bits.

Therefore:

- BREAK/HALT/BROKE is not sufficient for an SP interrupt;
- BREAK/HALT/BROKE is not necessary for an SP interrupt; and
- an interrupt-root certificate cannot use those status values as producer provenance.

An exact-pin repository search for `MI::IRQ::SP` found the executable SP raise/lower sites in `rsp/io.cpp` and `rsp/interpreter-ipu.cpp`; the remaining occurrence is debugger labeling.

Pinned Gopher64 independently implements the same two coarse producer classes: BREAK completion raises SP only when its interrupt-on-break status bit is set, while SP_STATUS can explicitly set/clear `MI_INTR_SP`.

### Set+clear pairs are operations even when the selected value does not change

Pinned ares applies SP_STATUS paired clear/set controls only when one command bit is set without its opposite. Pinned n64-systemtest independently tests this for both SP interrupt and interrupt-on-break state: after establishing high and low states, writing both bits together must leave the prior state unchanged. Its `SP Set/Clear Interrupt` case directly checks that SP_STATUS changes `MI_INTR.SP`.

The command operation still happened. Before/after equality is not evidence that no operation occurred.

### MI destroys unique source identity at the shared CPU pending bit

Pinned ares stores each MI source line and mask separately. `MI::poll()` ORs the masked SP/SI/AI/VI/PI/DP lines and writes one CPU RCP pending bit. Pinned Gopher64 preserves the same coarse split through `MI_INTR & MI_INTR_MASK`.

So `Cause.IP2 == 1` is not an SP provenance token. Another enabled MI source can keep IP2 high after SP is cleared, and several sources can contribute simultaneously. Whole-ROM evidence needs a source-specific contributor set or equivalent lineage through this join.

### MI mask and CPU gate are distinct generations

MI.SP can be asserted while masked and become CPU-pending later when the SP mask is enabled. The assertion operation and the later mask operation therefore cannot be collapsed into one generation.

The completed executed CPU-root experiment established the downstream gate: `(Cause.IP & Status.IM) != 0`, `IE=1`, `EXL=0`, `ERL=0`. When admitted at an architectural instruction boundary, the interrupt selects the BEV-sensitive general `base + 0x180` root.

## Minimum SP-attributed root receipt

For this bounded composition, an SP-attributed CPU interrupt root needs:

1. an SP assertion operation generation whose producer is either:
   - RSP BREAK with interrupt-on-break enabled at that event, or
   - explicit SP_STATUS set-interrupt;
2. no intervening SP clear/lower retiring that assertion;
3. current MI.SP mask/register-operation identity with SP enabled;
4. the shared RCP pending state with SP retained as an actual contributor, not reverse-inferred from IP2 equality;
5. CPU Status.IM/IE/EXL/ERL gate identity at the admitted architectural boundary; and
6. the resulting exception-root transfer identity.

If more than one MI source contributes, preserve the contributor set. Do not invent a unique producer.

Same-value repeated SP raises and same-value repeated MI mask writes are distinct operation/register generations. Final value equality cannot recover which generation was current at root admission.

## Executable adversarial reducer

`experiments/sp-interrupt-root-compose/model.py` is a small causal falsifier, not an N64 emulator. Its ten deterministic histories cover:

- BREAK with interrupt-on-break disabled;
- direct SP_STATUS raise without BREAK;
- SP assertion while masked then later unmask;
- SP BREAK assertion, explicit SP clear, then unrelated PI assertion;
- SP asserted but masked while PI alone drives shared RCP pending;
- repeated same-value SP raises;
- repeated same-value MI.SP mask writes;
- simultaneous set+clear command with prior high and low state;
- EXL gate followed by release; and
- ERL gate.

Two cases falsify the snapshot shortcut `HALT && BROKE && RCP-pending => SP-caused root`: after SP is cleared, PI can drive the root while HALT/BROKE remain set. The converse fails because direct SP_STATUS raise can create a real SP contributor without BREAK.

Canonical deterministic case JSON SHA-256:

`c9c3afdc46c2e2ae0a11107b9590c8cad2896f56cebf719c29dbfcd40fb85dcc`

## Exact-pin guards and CI

`experiments/sp-interrupt-root-compose/source_guard.py` fails closed unless all three reference worktrees are exactly at the `refs.lock.toml` revisions and the guarded producer/mask/root source contracts remain present.

Branch workflow: `.github/workflows/research-sp-interrupt-root-compose.yml`.

Final-head successful run:

- run `38046284005`
- job `114196376356`
- tested/final head `8ef4b1a057d1cf311fd630c88c58a909d135819f`
- evidence artifact `11667028462`
- artifact ZIP digest `sha256:61cdcdc62f2c8a66ac9a0ff3e85c52efdb99375efc1a654da2da064dc5b9e25c`

The job fetched exact ares/Gopher64/n64-systemtest pins, byte-compiled both Python tools, ran all ten adversarial histories, ran every source guard, hashed the textual receipts and uploaded them. The prior code-head run `38046194852` also passed, so the research logic was green before the note-only finalization.

## Prior research composed or challenged

Composed:

- `research/ares-maskable-interrupt-roots.md`: exact executed ares pending/mask/IE/EXL/ERL root matrix, explicitly leaving device producer reachability open;
- existing RSP execution/microcode work only as context for keeping RSP execution identity separate from SP interrupt-event identity.

Rejected proof shortcuts:

- BREAK implies SP interrupt;
- HALT/BROKE implies SP interrupt;
- SP interrupt implies BREAK;
- current `MI_INTR.SP` identifies its producer operation;
- CPU `Cause.IP2` identifies SP as the producer;
- equal before/after SP/MI values imply no operation occurred; and
- nearest/latest/equal-looking events are sufficient ancestry without assertion, clear, mask and CPU-gate chronology.

## Closed-world impact

A whole-ROM certificate cannot exclude the general interrupt handler merely because PI/SI/VI/etc. producers are absent. Reachable RSP BREAK with interrupt-on-break enabled or reachable SP_STATUS set-interrupt independently creates an SP line. If that line can coexist with an enabled MI.SP mask and the CPU gate, the already-validated `base + 0x180` handler remains a required executable root.

Conversely, merely finding BREAK or HALT/BROKE is not enough to require an SP-caused root. This producer can be discharged only by causal proof that reachable producer paths cannot establish a live SP assertion at an admissible CPU boundary, or by a proven mask/gate invariant.

Because MI compresses device sources into one RCP pending bit, a single pending-bit generation is insufficient provenance for a device-attributed root.

## Remaining gap

- No new physical-N64 execution was performed. n64-systemtest was source-audited at its exact pin, not run on hardware here.
- The SP producer side is exact-pinned source evidence corroborated by Gopher64/n64-systemtest; the CPU-root side is intentionally composed from the prior unmodified-ares executed fixture rather than rebuilt here.
- Exact asynchronous CPU/RSP scheduling, arbitrary delay-slot timing and device synchronization remain outside this reducer.
- Save/restore, reset/NMI and frontend/debugger mutation can cut or resurrect chronology and must be composed with existing lifetime/restore evidence.
- This does not prove handler-byte provenance, handler immutability, RSP microcode provenance or whole-ROM closure by itself.

## Reproduction

With exact pins under `.refs/{ares,gopher64,n64-systemtest}`:

```bash
python3 -m py_compile experiments/sp-interrupt-root-compose/model.py \
  experiments/sp-interrupt-root-compose/source_guard.py
python3 experiments/sp-interrupt-root-compose/model.py
python3 experiments/sp-interrupt-root-compose/source_guard.py
```

## Integration recommendation

**ADOPT** the causal proof obligation, not the research model as production architecture. A future interrupt-root certificate should preserve source-specific assertion/clear identity through MI, MI-mask operation identity, the contributor set feeding RCP pending, CPU gate identity and root-transfer identity. Do not infer SP provenance from BREAK/HALT/BROKE, `MI_INTR.SP`, `Cause.IP2`, equal values or nearest/latest events.
