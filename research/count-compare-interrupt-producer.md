# VR4300 Count/Compare interrupt producer composition

Status: **PARTIAL**

Claim: issue #4 worker `gpt56sol-count-compare-interrupt-producer-20261010`.

Canonical integration base: `211176e7a489fecf8331d02915ee982cd279cb62`.

Exact reference pins from `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Question

Can a reachable guest Count/Compare configuration independently produce IP7 strongly enough that Plaid must retain the already-validated BEV-sensitive `base+0x180` interrupt root, and what causal state must a closure proof retain to reason about timer acknowledgement and rescheduling?

## Primary architectural evidence

The NEC VR4300/VR4305/VR4310 User's Manual, sections 6.3.3, 6.3.4 and 14.4, states that Count is a read/write free-running timer incrementing at half PClock, Compare is stable, equality between Count and Compare sets timer interrupt IP7, and writing Compare clears the timer interrupt request. Section 14.4 also identifies IM7 plus IE/EXL/ERL as the timer interrupt mask/gate.

Manual: <https://hack64.net/docs/VR43XX.pdf> (User's Manual U10504EJ7V0UM00, sections 6.3.3/6.3.4 around pp. 164-165 and section 14.4 around p. 354).

This primary specification supports the coarse architectural producer contract. It does **not** by itself settle cycle-exact visibility around an `MTC0 Count` that writes an equality value or every pipeline hazard relevant to an emulator event scheduler.

## Exact-reference source audit

Exact pinned ares implements the producer in `CPU::stepCount`: it computes modular remaining distance from internal shifted Count to Compare, latches `Interrupt::Timer`/IP7 when a positive advance crosses that distance, and leaves pending latched until acknowledgement. `MTC0 Count` flushes elapsed Count and replaces Count. `MTC0 Compare` flushes Count, replaces Compare, and explicitly clears Timer pending.

Exact pinned Gopher64 implements Compare as an explicit scheduled event. A Compare write schedules that event and clears IP7; `compare_event` sets IP7 and reschedules. Its Count write calls `translate_events(old_count,new_count)`, which shifts **every** enabled event, including Compare, by `new_count-old_count`. That preserves the old relative Compare-event deadline across a Count rewrite.

Exact pinned Mupen64Plus also uses a scheduled Compare event, but its Count-write `translate_event_queue` explicitly removes `COMPARE_INT`, translates the other events, writes the new Count base, then recreates `COMPARE_INT` at the current Compare register value. Thus Mupen makes the future Compare deadline depend on rewritten Count, subject to its own `count_per_op` event-order shim.

The Gopher Count-write scheduling policy therefore disagrees with ares and Mupen. More importantly, preserving an old relative deadline is difficult to reconcile with the VR4300 architectural description that Count itself is writable/free-running while Compare remains stable and equality is the producer condition. Treat that Gopher behavior as a preserved reference disagreement, not as hardware truth. Cycle-exact MTC0 timing still needs a hardware/system-test arbiter before encoding a stronger production timing rule.

Pinned n64-systemtest names Cause bit 15 as `interrupt_compare`, but no dedicated Count/Compare timing test was found at this revision.

## Executed exact-ares matrix

`experiments/count-compare-interrupt/driver.cpp` is built against the exact pinned ares tree using Plaid's existing `spikes/003-ares-oracle/run.py`. Both CPU and RSP recompilers are disabled. `run.py` executes every case twice and requires byte-identical JSON plus case-specific assertions.

The 16-case matrix validated:

- Count progression crossing Compare latches IP7.
- With BEV=0, IE=1, IM7=1, EXL=ERL=0, the timer producer enters `0xffffffff80000180` before the ordinary instruction retires.
- With BEV=1 under the same gate, it enters `0xffffffffbfc00380`.
- Before the deadline, IP7 is not pending.
- IM7=0, IE=0, EXL=1, or ERL=1 blocks interrupt entry while IP7 remains pending.
- A Compare write clears a latched timer request.
- A **same-value Compare rewrite** also clears it while the visible Compare value is unchanged.
- A Count write does not acknowledge an already-latched timer request in pinned ares.
- A real guest `MTC0 Compare` same-value acknowledgement clears pending while masked; enabling IM7 afterward lets the next ordinary instruction retire.
- A real guest `MTC0 Count` does not acknowledge an already-latched request; enabling IM7 afterward causes the next instruction boundary to enter the general interrupt vector with EPC at that next instruction.
- Pinned ares detects ordinary modular wrap crossing (`0xfffffffe -> 1`).
- Pinned ares does not immediately reassert merely because a Compare write leaves Count and Compare equal; after one visible Count tick the values have diverged and pending remains clear.
- Pinned ares changes future deadline when Count is rewritten forward/backward, as expected from its implicit comparator model. This exact rescheduling behavior is not promoted to a universal hardware invariant because of the reference disagreement and missing dedicated hardware/system-test case.

The matrix also records and asserts the actual BEV/IE/EXL/ERL/IM gate presented to the final instruction-boundary check. An earlier checkpoint had misleading local gate telemetry for several cases; the behavior assertions were unaffected, and the final runner adds explicit gate-telemetry assertions so that defect cannot silently recur.

## Causal/provenance consequence

A value-only `(Count, Compare)` snapshot is insufficient for closed-world reasoning. In the adversarial model, two histories can end with identical Count and Compare values while differing in both timer pending state and Compare-write generation because a same-value Compare write is an acknowledgement operation.

Therefore a timer proof needs ordered operation identity, at minimum enough to distinguish:

- Count value/generation;
- Compare value/generation;
- timer pending state/generation;
- a Compare-write acknowledgement event, even when old and new Compare values are equal;
- interrupt-gate chronology (IM7, IE, EXL, ERL, BEV) at architectural boundaries.

Do not infer acknowledgement from value change, and do not collapse same-value Compare writes.

## Closed-world impact

The Count/Compare timer is an internal executable-root producer. A whole-ROM closure certificate cannot exclude the maskable general interrupt root merely because external RCP interrupt sources are absent. If guest-reachable state can allow Count to meet Compare while IM7/IE are enabled and EXL/ERL permit entry, the already-validated BEV-sensitive `base+0x180` root remains reachable.

Conversely, excluding this producer requires a proof over timer state and gate chronology, not a flag or a final-register snapshot. A proof that observes a same-value Compare acknowledgement must preserve that operation as a generation-changing event.

## Remaining gap

The coarse architectural rule is well specified, but cycle-exact Count-write/equality timing is not closed here. In particular, there is no pinned n64-systemtest case adjudicating Count rewrites and equality-at-write against hardware, and the exact emulator references disagree on Count-write event rescheduling. Save/restore/reset chronology of timer generations is also outside this bounded worker.

Plaid should therefore adopt the producer/root obligation and operation-generation requirements while keeping exact Count-rewrite scheduling semantics OPEN until a hardware-backed system test resolves them.

## Reproduction and evidence

Branch: `research/count-compare-interrupt-producer-gpt56sol`

Workflow: `.github/workflows/research-count-compare-interrupt.yml`

Clean exact-pin CI on head `02d0db510de328dce5f0d5016ec188b1dd394210`:

- Actions run `37999763523`: success
- job `114054697005`: success
- source guard SHA-256 `249c840f1baac98737268072c638e2a1e756234fd9949807097a14c09c3c1d50`
- causal model payload SHA-256 `08ad1badd95ba998cf2573187a937520b4b6e678a455669adc4d09f93ca15b4c`
- model output SHA-256 `5e63dfbf94297ee7964f23fb9b64c1cf2fac496961ec7065fcc650a5803e20ce`
- exact-ares results SHA-256 `ee28a2c899b8c5b4db000d143b6216d7524bb5eb92ea8e9aa1f932937fcf22c9`
- uploaded artifact ID `11647629606`
- artifact ZIP SHA-256 `3ab6f788ffc879cfa2aee755914ba4600d726ace51e283fdac1b2f2a248e77c2`

Reproduce from an exact-ref checkout:

```sh
python3 -m py_compile experiments/count-compare-interrupt/{source_guard.py,model.py,run.py}
python3 experiments/count-compare-interrupt/source_guard.py
python3 experiments/count-compare-interrupt/model.py
python3 experiments/count-compare-interrupt/run.py
sha256sum target/count-compare-interrupt/{source_guard.json,model.out,results.json}
```

No Plaid production files or pinned reference implementations were modified.
