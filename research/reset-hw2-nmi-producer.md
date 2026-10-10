# Reset-button HW2 -> NMI producer identity is not a pending-value identity

Status: **PARTIAL**

Date: 2026-10-10

Plaid canonical base inspected before claim: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/reset-hw2-nmi-producer-gpt56sol`

Exact pinned references:

- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

## Question

Previous Plaid research established several useful but deliberately separate facts:

- external NMI/reset entry uses the reset root rather than an ordinary exception vector;
- an architectural transfer to that root does not prove that a root instruction was fetched;
- executable-root byte provenance must come from the actual fetch/source chain;
- a persistent emulator `nmiPending` level is not a unique NMI event token;
- NMI is edge-triggered in the VR4300 vendor contract, while reference emulators disagree on some reset/NMI details.

Those results explicitly left the reset-button **producer/latch chronology** open. This experiment asks a narrower question: what event identity survives if Plaid tries to compose a reset request, pre-NMI HW2 delivery, later NMI delivery, save/restore, and the already-known NMI root?

The answer is that neither a boolean pending level nor an equal `(event_type, count)` pair is a trustworthy causal identity. Worse, the exact pinned references disagree on whether repeated reset requests accumulate or coalesce, so Plaid must preserve that disagreement rather than invent a universal 1:1 reset-request-to-NMI rule.

## Falsifiable hypothesis

A reset/NMI certificate that keys producer identity only by numeric pending state or by `(type,count)` can collapse distinct operations or replay one operation twice.

Concrete falsifiers were:

1. exact pinned Mupen rejects duplicate same-type interrupt events rather than retaining them;
2. exact pinned Gopher retains multiple pending NMI instances rather than overwriting one slot;
3. Mupen savestate serialization preserves enough identity to reattach an external producer token without an explicit epoch/token sidecar;
4. selected events can be delivered repeatedly without being consumed first.

Any of those would have narrowed or rejected the proposed proof obligation.

## Exact pinned source evidence

The successful workflow checked out the exact revisions and guarded the following Git blob identities:

| Reference | File | Git blob SHA |
| --- | --- | --- |
| Mupen64Plus | `src/device/device.c` | `2c415fb6aaa31e280b43393c97fc401a988effad` |
| Mupen64Plus | `src/device/r4300/interrupt.c` | `9c81a184c92a2a58eed50265cf816031790fb99b` |
| Mupen64Plus | `src/device/pif/pif.c` | `f2262039ffe9342c42dc890859c931d4ee76808b` |
| Gopher64 | `src/device/events.rs` | `b4769a4495375cf7e3baf3b77e41ef42e0de683e` |
| Gopher64 | `src/ui/video.rs` | `62ad5b303f5d77d9511c5f4f3bfb073cc38c4217` |
| Gopher64 | `src/device/exceptions.rs` | `629750763f1029347a381fc3f87f1a007e5e25cc` |

Guard report canonical payload SHA-256:

`4e975061e69d31838e193ae160e80fb5b1e01d50c9d1a38122303dab0547901d`

The source-guard JSON file itself has SHA-256:

`eb628e221171d2bd404a6f7dfac2e529941b3ec18ff22b14e92ee9c977e2d081`

### Mupen64Plus: reset creates two queued operations

`soft_reset_device()` explicitly does:

```text
HW2_INT at Count + 0
NMI_INT at Count + 50,000,000
```

The delay is a pinned-Mupen implementation detail, not promoted here to a hardware timing rule.

More importantly, `add_interrupt_event_count()` checks whether an event of the same type already exists only to emit a warning. It still allocates and inserts a new queue node. Therefore repeated reset requests may create multiple HW2 nodes and multiple NMI nodes, including nodes with equal event type and equal count.

The dispatcher removes the selected queue node before invoking either the HW2 or NMI handler. Thus queue-node delivery is one-shot in this implementation.

`hw2_int_handler()` raises `CP0_CAUSE_IP4`, making the pre-NMI HW2 phase an ordinary maskable-interrupt source rather than the NMI root itself.

### Mupen64Plus: queue save/restore loses external producer ancestry

`save_eventqueue_infos()` serializes each pending queue node as only:

```text
(type, count)
```

`load_eventqueue_infos()` clears the queue and reconstructs nodes by calling `add_interrupt_event_count(type,count)`.

That preserves the emulator's pending schedule but does **not** preserve any external Plaid producer token, reset-request generation, insertion token, or provenance edge unless Plaid explicitly serializes such identity itself. A post-restore equal `(type,count)` row cannot soundly borrow a pre-save observer-side causal identity merely because the values match.

### Gopher64: repeated reset overwrites/coalesces one NMI slot

Gopher64's event store is a fixed array indexed by event type. `create_event(name, when)` replaces `events[name]` rather than allocating a second instance.

The UI reset callback:

1. immediately sets `CP0_CAUSE_IP4`; and
2. writes one `EVENT_TYPE_NMI` slot for `device.cpu.clock_rate` later.

A second reset request before that NMI fires therefore overwrites/coalesces the one pending NMI slot instead of accumulating another NMI operation as pinned Mupen does. `trigger_event()` disables the selected slot before invoking its handler, again providing one-shot delivery for the retained slot.

Gopher's reset handler clears IP4, records ErrorEPC, selects `0xBFC00000`, and resets associated state, but those root semantics were already covered by earlier research and are not re-claimed here.

## Reference disagreement

The exact pinned references disagree materially on repeated-reset producer semantics:

- **Mupen64Plus:** repeated reset can accumulate distinct queue nodes, even with identical `(type,count)` values.
- **Gopher64:** one NMI slot per event type means a later reset replaces/coalesces the earlier pending NMI event.

Therefore neither behavior is promoted to N64 hardware truth. In particular, Plaid must not claim that every reset request necessarily has exactly one independently deliverable later NMI generation, nor that repeated requests necessarily coalesce.

The portable proof obligation is weaker and safer: if a certificate wants to identify a specific HW2/NMI delivery causally, it needs evidence stronger than the current value of a pending bit or an equal type/count pair.

## Executable adversarial model

Artifacts:

- `experiments/reset-hw2-nmi-producer/source_guard.py`
- `experiments/reset-hw2-nmi-producer/model.py`
- `experiments/reset-hw2-nmi-producer/README.md`
- branch-only `.github/workflows/research-reset-hw2-nmi-producer.yml`

The model does not simulate a complete N64. It executable-checks the proof relation implied by the guarded reference semantics and deliberately attacks identity laundering.

### Fixed adversaries

At synthetic Count 100, two Mupen-style reset requests produce four distinct modeled operations:

```text
HW2 count=100       token=1 request=1
HW2 count=100       token=3 request=2
NMI count=50000100  token=2 request=1
NMI count=50000100  token=4 request=2
```

The equal type/count values are therefore insufficient to identify the operation. The verifier rejects:

- replaying an already consumed event;
- attributing the second equal-valued HW2 event to the first reset request;
- attaching a pre-save request ancestry to a reconstructed post-restore row whose external producer identity was not serialized.

The Gopher-style adversary issues two reset requests while one NMI slot is pending. The model records the first pending token being replaced by the second and delivers only the retained second request, matching the guarded fixed-slot semantics.

### Deterministic fuzz

Seed: `0x4857324e` (`1213674062`)

Trials: `10,000`

Total synthetic reset requests: `30,111`

Observed adversarial counts:

- Mupen ambiguous equal `(type,count)` keys: `16,130`
- restored Mupen rows with intentionally UNKNOWN external request ancestry: `30,306`
- Gopher reset requests coalesced/overwritten by a later request: `20,111`

The model was run twice in the same CI job; stdout and JSON were required to be byte-identical.

Canonical model payload SHA-256:

`b6c83636a61bb77dbed04030a70fd085f111a569c43d23c5707ea04a57b0d6b2`

Generated evidence hashes:

- `model.stdout`: `911b27f5ac06eaedc43aa88e0bac7e17ba19b228c0ae281242e1a4c194fdf8ef`
- `results.json`: `8b49a3c4f3114aa487e583bb5826d495db485261e741ef761a95b269c278a2f7`
- `source-guard.json`: `eb628e221171d2bd404a6f7dfac2e529941b3ec18ff22b14e92ee9c977e2d081`
- `source-guard.stdout`: `fcdba87f0607bfd3f04222a6d56bd124692de90dfc5210fb886cdf28680e4ec7`

Successful exact-pin Actions evidence:

- run `38052920267`
- job `114215533024`
- tested commit `aebba03b6145758407dcbc71e2ed6717a9f93a6e`
- artifact `11670141849`
- artifact ZIP SHA-256 `5eb5aa0dd38514c42b871d574d19cb1406a9948248e0f5cdd240570e96c5b0c2`

The first workflow attempt (`38052822805`) failed only because `tee` targeted the evidence directory before that directory had been created. The exact reference checkout, syntax compilation, and source guard itself succeeded in that run and produced the same source-guard payload hash. The workflow was corrected by creating the directory before `tee`; no experiment semantics changed.

## What prior research this composes or challenges

This composes:

- `research/nmi-root-contract.md`: fixed reset/NMI root plus the explicit result that a persistent `nmiPending` level is not a unique NMI event token;
- `research/nmi-root-fetch-provenance.md`: architectural NMI root transfer, root fetch occurrence, and root byte provenance are separate facts;
- interrupt/NMI ordering research: the VR4300 vendor contract treats NMI recognition as edge-triggered and must not be replaced by a persistent emulator level;
- reset/cache lifetime research: reset/NMI/cache/backing lifetimes are distinct, and restore is chronology selection rather than an ordinary monotonic forward transition.

It challenges the tempting higher-order composition:

```text
reset requested
+ same pending value/event type/count
+ known NMI root
=> same unique causal NMI generation
```

That implication is false for the bounded evidence here. Equal values can denote distinct Mupen queue nodes, while a later Gopher request can replace an earlier pending NMI entirely.

## Closed-world impact

For a whole-ROM reset/NMI executable-root certificate, Plaid should keep at least these identities distinct:

1. reset-button/request generation, if the declared execution scope admits reset;
2. pre-NMI HW2/IP4 assertion/delivery identity;
3. NMI producer/edge generation;
4. NMI architectural root-transfer identity;
5. root fetch/execution occurrence;
6. root executable-byte source/generation.

Not every implementation will expose all six directly, and some may prove multiple relations with one stronger causal event. But deleting the distinctions and replacing them with a boolean or equal numeric state is unsound.

Specific proof consequences:

- `(event_type,count)` must not be treated as globally unique event identity;
- equal pending values must not merge producer generations;
- one consumed delivery must not be replayed as a second causal delivery;
- after save/restore, observer-side producer identity must either be serialized consistently or invalidated/epoch-separated; matching restored values do not resurrect pre-save provenance;
- a missing producer/edge relation stays UNKNOWN rather than being inferred from the later NMI root;
- Mupen's accumulation policy and Gopher's overwrite policy must remain reference-specific until stronger hardware evidence resolves repeated-reset behavior.

This does **not** close `WholeRom`; it narrows what a future root/lifetime certificate is required not to collapse.

## Result

**PARTIAL.**

Validated:

- exact pinned Mupen can retain multiple same-type, same-count reset-related queue nodes;
- exact pinned Mupen queue save/restore persists type/count but not an external producer token;
- exact pinned Gopher uses one replaceable NMI event slot and direct IP4 assertion;
- both pinned delivery paths consume/disable the selected event before its handler;
- deterministic adversarial execution demonstrates why value equality, replay, and restore-based ancestry reuse are unsound.

Not validated as hardware-wide facts:

- Mupen's 50,000,000-count delay;
- Gopher's one-clock-rate delay;
- whether physical hardware accumulates, suppresses, stretches, or coalesces repeated reset-button requests;
- an exact hardware mapping from reset-button electrical transition through HW2 to one NMI edge.

## Remaining gap

Physical reset-button producer semantics remain unresolved. Useful next evidence would be a hardware/system-test fixture capable of issuing or externally controlling repeated reset transitions with timestamps around Cause.IP4, NMI entry, ErrorEPC, and handler execution. Save/restore is emulator-only chronology and still requires an explicit Plaid tracing policy regardless of hardware behavior.

This experiment also does not revisit simultaneous maskable IRQ/NMI priority, NMI root fetch provenance, PIF source behavior, reset/cache lifetime, or executable-byte closure; those are separate already-owned lanes.

## Integration recommendation

**ADOPT THE PROOF OBLIGATION; DO NOT ADOPT EITHER REFERENCE'S REPEATED-RESET POLICY AS HARDWARE TRUTH.**

A future root-certificate/event model should carry a stable producer/delivery generation or equivalent causal identity, consume deliveries once, and serialize that identity across restore or create a new chronology epoch. It must not infer identity from a boolean pending state, event type/count equality, PC equality, or payload equality.

Keep HW2 delivery, NMI edge/transfer, root fetch, and root byte provenance independently dischargeable. Preserve Mupen/Gopher disagreement until stronger hardware evidence adjudicates repeated reset behavior.

No production Plaid files are changed by this research branch; canonical integration remains with the primary integrator.
