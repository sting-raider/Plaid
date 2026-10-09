# VR4300 guest software-interrupt production composes into the general interrupt root

**Result: VALIDATED (bounded producer/root composition).**

Research branch: `research/sw-interrupt-producer-gpt56sol`  
Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`  
Primary exact-reference run: GitHub Actions `37999012749`  

## Question

Plaid already has executable evidence for the maskable interrupt gate and the
BEV-sensitive general `+0x180` vector, but that work intentionally left producer
reachability open. This experiment asks whether *guest software itself* is an
interrupt producer through CP0 Cause, and whether a guest Cause write can also
forge or clear the hardware-owned pending bits.

This distinction is required for closed-world reasoning. Proving every external
MI/timer producer unreachable does not exclude the general interrupt root if a
reachable MIPS instruction can synthesize an eligible software interrupt.

## Hardware contract

The VR4300 User's Manual `U10504EJ7V0UMJ1` (7th edition) provides unusually
strong architectural evidence:

- §6.3.6, Cause Register (manual p.171): all Cause bits except IP1/IP0 are
  read-only; IP1/IP0 generate software interrupts.
- §6.4.18, Interrupt Exception (manual p.199): the eight interrupt conditions
  include two software interrupts; each is masked by the matching Status.IM bit,
  and all are gated by IE/EXL/ERL. The common exception vector is used.
- The same section says SW1/SW0 are serviced by clearing the corresponding Cause
  bit.
- Figure 6-14 (manual p.201) gives the BEV-dependent common vector as
  `0xffffffff80000000 + 0x180` or `0xffffffffbfc00200 + 0x180`.

One documentation inconsistency is deliberately preserved rather than normalized
away: §6.3.6 says IP7 is read-only, while §6.4.18/§14.4 says a timer request may be
cleared by clearing Cause.IP7 or by changing Compare. The three exact emulator
sources below implement guest Cause writes as IP0/IP1-only. This experiment does
**not** promote that ambiguous timer-acknowledgement wording into a new IP7 write
rule; timer acknowledgement remains a separate question if Plaid needs that
specific operation in a proof.

## Exact pinned source agreement

The branch source guard binds both revisions and source blob identities:

| Reference | Exact revision | Relevant blob | Guest Cause write |
|---|---|---|---|
| ares | `9408cb43d4948fc3ea6e152a307a34348df3fe04` | `c3d119bf4931c4616ae297a4c18b561490207e11` | assigns pending bits 0/1 from Cause data bits 8/9, then `interruptPoll()` |
| Gopher64 | `e96debac941a26ba4961e5145056c0821d3a56f7` | `75e48a396b37c1f50d03363a7417e5530cce7923` | Cause register write mask is exactly `0x300`, followed by pending-interrupt check |
| Mupen64Plus Core | `ba95bab92a76744753bfe61470823a4937850ab0` | `c3a4acfb4a003d6f6259af3c22464966b7eff15c` | clears/replaces only `CP0_CAUSE_IP0 | CP0_CAUSE_IP1` |

This is independent source agreement with the register description, not hardware
execution. `n64-systemtest` at its pinned revision was searched for a direct Cause
software-interrupt write-mask case; no matching dedicated test was found, so none
is claimed.

## Executable experiment

`experiments/ares-sw-interrupt-producer/driver.cpp` builds against unmodified exact
pinned ares using the existing Plaid ares-oracle build helper. Both CPU/RSP
recompilers are disabled. At uncached KSEG1 `0xffffffffa0000000`, the guest code is:

```text
MTC0  $t0,$13
ADDIU $s0,$zero,0x1234
NOP
```

The first `CPU::instruction()` must retire the real guest `MTC0 Cause`. The second
boundary either takes the interrupt before fetching `ADDIU`, or retires `ADDIU`.
Entry is discriminated by PC, `$s0`, EPC, Cause.ExcCode/BD and EXL, not merely by
pending-bit equality.

Twenty-one adversarial cases run twice each in fresh systems and compare
byte-identically. They cover IP0/IP1 independently and together, BEV 0/1, attempted
hardware-IP writes, mixed payloads, software clears, same-value writes, preserved
IP2/IP7, software-bit replacement beside IP2, zero/disjoint masks, IE=0, EXL=1 and
ERL=1.

### Dynamic result

Actions run `37999012749` passed all steps.

- guest cases: **21** total, **12 taken**, **9 suppressed**;
- each case repeated byte-identically;
- result SHA-256:
  `589eb9d5795106753e5de3f055dd14977702bb136c68793e3c4dc464ebaa3bda`.

Observed causal discriminators:

1. Writing raw Cause `0x100`, `0x200`, or `0x300` via guest MTC0 produced pending
   IP0, IP1, or both. With a matching IM and IE=1/EXL=ERL=0, MTC0 itself retired at
   `start+4`; the *next instruction boundary* entered the validated general vector
   before `ADDIU` retired. EPC was `start+4` and `$s0` remained zero.
2. With BEV=0 the target was `0xffffffff80000180`; with BEV=1 it was
   `0xffffffffbfc00380`.
3. Raw Cause `0xfc00` with no initial pending bits did **not** create IP2..IP7;
   `ADDIU` retired even with IM2..IM7 enabled.
4. A preexisting IP2 survived a guest Cause write of zero; after IM2 was enabled,
   the next boundary entered the interrupt vector. A preexisting IP7 likewise
   survived a hostile raw `0xfc00` Cause write in this exact reference.
5. Starting from IP0+IP2 and writing IP1 replaced only the software portion,
   yielding IP1+IP2 (`0x06`).
6. Guest writes of zero cleared IP0/IP1 before later mask enable, suppressing entry.
7. Zero/disjoint masks, IE=0, EXL=1 and ERL=1 all retained the new software pending
   state but suppressed entry.
8. Same-value writes were executed and retained as explicit operations in the
   fixture even though a before/after value diff cannot reveal them.

## Exhaustive adversarial model

`model.py` independently exhausts:

- all 256 initial IP values × all 65,536 low-16-bit Cause payloads =
  **16,777,216 ownership cases**;
- all IP × IM × IE × EXL × ERL gate combinations = **524,288 gate cases**.

The ownership invariant is:

```text
new_ip = (old_ip & 0xfc) | ((cause_value >> 8) & 0x03)
```

It encountered **4,194,304 same-value writes**. Those are counted as operations;
value equality is never used to infer that no write occurred.

Model report SHA-256:
`8dead0768d59baa6c53e868de9c37ccfeed379fd2320b6fed9fba8ef8aa0e999`.

## What is now defensible

For the declared VR4300 model and exact references, a reachable guest MTC0/DMTC0 to
CP0 Cause is an independent producer/clearer of **software pending IP0/IP1**. It
cannot be soundly collapsed into external-device interrupt provenance. An eligible
software pending bit composes directly with the already-validated interrupt gate and
makes the BEV-selected general `+0x180` root reachable at the next architectural
instruction boundary in the tested ares execution.

Guest Cause writes must also preserve the distinct provenance of IP2..IP7 rather
than attributing those bits to the Cause write just because they coexist in one
register value.

## Closed-world impact

A whole-ROM proof may exclude the maskable general interrupt root only if it can
also discharge software-interrupt production. At minimum, the proof needs one of:

1. include the general interrupt root and prove its handler/lifetime/provenance;
2. prove all reachable Cause writes cannot leave IP0/IP1 eligible under any reachable
   Status gate state;
3. prove a stronger invariant that permanently masks/disables those software
   interrupts for the declared scope.

"No external interrupt device can fire" is insufficient.

For provenance/history, a Cause write is an operation event even when the resulting
IP bits equal their prior values. A solver that reconstructs producer history from
only before/after register equality would lose same-value write provenance.

## Remaining gap

This closes only the software-pending producer/clear path plus its composition with
the existing general interrupt root. It does not close:

- external MI/timer producer reachability or the manual's ambiguous IP7 clear wording;
- arbitrary pipeline/delay-slot timing beyond the tested ordinary MTC0 boundary;
- handler-byte provenance, cache-visible handler state, mapping/lifetime closure;
- asynchronous event chronology across save/restore/reset;
- whole-ROM discovery of all reachable CP0 writes and Status gate mutations.

Those obligations remain OPEN.

## Reproduction

```bash
python3 experiments/ares-sw-interrupt-producer/source_guard.py
python3 experiments/ares-sw-interrupt-producer/model.py
python3 experiments/ares-sw-interrupt-producer/run.py
sha256sum target/ares-sw-interrupt-producer/model.json \
  target/ares-sw-interrupt-producer/results.json
```

The branch-only workflow `.github/workflows/research-sw-interrupt-producer.yml`
fetches the exact pins, checks the source blobs, executes the exhaustive model,
builds/runs the guest fixture, hashes the JSON reports and uploads them.

## Integration recommendation

Do not copy the research harness into production. Integrate the semantic invariant
instead when the whole-ROM root/CP0 evidence model is ready:

- treat reachable Cause writes as explicit CP0 operation/provenance events;
- assign only IP0/IP1 writer ownership to guest Cause writes;
- keep IP2..IP7 producer ownership separate;
- propagate software-pending eligibility through Status.IM/IE/EXL/ERL and BEV into
  the general interrupt root obligation;
- retain operation generations even for same-value writes;
- keep the certificate OPEN when Cause-write reachability or gate chronology is
  unknown.
