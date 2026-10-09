# Maskable VR4300 interrupt roots and gating in pinned ares

Date: 2026-10-09

Result: **VALIDATED** for the bounded pinned-reference scope below.

## Question

When a maskable VR4300 interrupt is pending, what exact state makes it an executable
root in the pinned ares interpreter, and which first handler PC is selected? The
question is intentionally narrower than device-specific interrupt reachability or
timing. A pending bit by itself must not silently become a proof that an interrupt
handler is reachable.

## Exact inputs

- Plaid canonical base inspected and used by the fixture:
  `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- Isolated research branch: `research/interrupt-roots-gpt56sol-20261009`
- Exact ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
  - `ares/n64/cpu/cpu.cpp` Git blob `41964d49c8983ae9a97b25625174cd4c4316c4a8`
  - `ares/n64/cpu/exceptions.cpp` Git blob `870e7d420f38fbda862cb4c7cb88481155b19251`
- Exact independent Gopher64 source revision:
  `e96debac941a26ba4961e5145056c0821d3a56f7`
  - `src/device/exceptions.rs` Git blob
    `629750763f1029347a381fc3f87f1a007e5e25cc`

No upstream emulator implementation source was patched for this experiment.

## Falsifiable hypothesis

At an ares interpreter instruction boundary, architectural maskable interrupt entry
occurs iff all of the following are true:

1. `(Cause.IP & Status.IM) != 0`;
2. `Status.IE == 1`;
3. `Status.EXL == 0`; and
4. `Status.ERL == 0`.

If the gate is true, entry must select the ordinary general vector `base + 0x180`,
where BEV chooses base `0xffffffff80000000` or `0xffffffffbfc00200`; the guest
instruction at the interrupted PC must not execute; EPC must receive that PC; EXL
must become one; and Cause.ExcCode must be interrupt/zero. If any gate component is
false, the next ordinary guest instruction must execute instead and the sentinel
exception state must remain untouched.

Any tested violation rejects the hypothesis.

## Upstream source map

Pinned ares `CPU::instruction()` checks
`Cause.interruptPending & Status.interruptMask` before instruction fetch. It takes
`Exception::interrupt()` only when IE is set and both EXL and ERL are clear.
`Exception::interrupt()` calls the common exception trigger with code zero. The
common trigger defaults to vector offset `0x180`; BEV changes only the vector base.
`CPU::setInterruptPending()` merely updates the pending bit and polls scheduling;
the architectural entry decision is still made by the instruction-boundary gate.

Pinned Gopher64 independently applies the same logical gate: IE must be enabled,
EXL/ERL clear, and a Status-mask/Cause-pending bit must intersect. Its interrupt
entry clears ExcCode and calls its general exception path with offset `0x180`, with
BEV choosing the same two bases. This is independent source agreement, not hardware
truth.

## Fixture construction

`experiments/ares-interrupt-roots-gpt56sol/driver.cpp` boots the unmodified exact
pinned ares core headlessly with both recompilers disabled and identity RDRAM. It
places this ordinary instruction at uncached KSEG1 PC
`0xffffffffa0000000`:

```text
ADDIU $s0,$zero,0x1234
```

The harness presets EPC, Cause.ExcCode and Cause.BD to sentinels, installs the
requested Status gate state, then raises requested Cause.IP bits through ares'
actual `CPU::setInterruptPending()` API. One `CPU::instruction()` boundary is
executed.

This creates a causal discriminator:

- if interrupt entry occurs first, `$s0` remains zero and PC becomes the handler
  vector;
- if entry is suppressed, the planted instruction executes, `$s0` becomes
  `0x1234`, and PC advances to `0xffffffffa0000004`.

No inference depends only on the final pending bit value.

## Matrix and adversaries

`run.py` executes every case twice and requires byte-identical JSON. The 32 cases
cover both BEV states and:

- each of the eight Cause.IP bits individually with its matching Status.IM bit;
- multiple pending bits with at least one enabled match;
- a pending bit with only a different mask bit enabled;
- disjoint multi-bit pending/mask sets;
- IE clear with a matched pending/mask bit;
- EXL set with a matched pending/mask bit;
- ERL set with a matched pending/mask bit;
- no pending bits with all mask bits enabled; and
- all pending bits with a zero interrupt mask.

These controls try to falsify any weaker rule such as “pending means take an
interrupt”, “mask alone is enough”, or “EXL/ERL do not matter”.

## Baseline behavior

The no-pending, masked, disjoint-mask, IE-off, EXL and ERL controls all execute the
planted `ADDIU`. They preserve the sentinel EPC (`0x123456789abcdef0`), sentinel
Cause.ExcCode (`13`) and sentinel BD (`1`) rather than manufacturing an interrupt
entry.

## Dynamic observations

GitHub Actions run `37915064121`, job `113769115202`, on Ubuntu 24.04 completed
successfully from code-tested branch head
`53cde1cb44d273f254de818e4903a6b23d463682`.

Observed summary:

```text
PASS: 32 exact-reference cases (18 taken, 14 suppressed) obey the
mask/IE/EXL/ERL interrupt-root truth table and repeat byte-identically
RESULT_SHA256 2775206efc797f614c07c36a783909c5468b55d609d93c34764c097499777eaf
```

All 16 single-bit matched cases (8 IP bits x 2 BEV states) and both multi-match
cases took the interrupt before the planted instruction: `$s0 == 0`, Cause.ExcCode
became zero, EPC became `0xffffffffa0000000`, BD became zero and EXL became one.
The selected PCs were exactly:

- BEV=0: `0xffffffff80000180`
- BEV=1: `0xffffffffbfc00380`

All 14 suppressed adversaries executed the planted instruction instead:
`$s0 == 0x1234` and PC became `0xffffffffa0000004`, with the sentinel exception
state preserved as appropriate.

The requested pending bits remained pending across entry in this bounded fixture;
entry itself is not evidence that a producer has cleared its source.

The uploaded result artifact is ID `11608727692`; its ZIP digest reported by
Actions is
`sha256:d91ec77a6d536fc8a0be5fecb6ba5e34c050905efef6cb9c0c80dcaa46b7cae7`.
The contained `results.json` SHA-256 is
`2775206efc797f614c07c36a783909c5468b55d609d93c34764c097499777eaf`.

## Instrumentation neutrality and repeatability

There is no ares instrumentation patch in this experiment. The harness sets public
emulator state and calls the normal pending-bit and interpreter entry paths; the
CPU/exception implementation files are the exact pinned upstream files. A source
guard fails closed if the expected ares or Gopher64 gate/root contracts drift.
Every dynamic case is started in a fresh headless system instance and executed
twice; both executions must produce byte-identical JSON before the verifier accepts
the case.

## Exact reproduction

With `.refs/ares` and `.refs/gopher64` checked out at the revisions above:

```bash
python3 experiments/ares-interrupt-roots-gpt56sol/source_guard.py
python3 -m py_compile experiments/ares-interrupt-roots-gpt56sol/run.py
python3 experiments/ares-interrupt-roots-gpt56sol/run.py
sha256sum target/ares-interrupt-roots/results.json
```

The branch-only workflow `.github/workflows/research-interrupt-roots.yml` performs
the exact reference fetches, guards, build, run, hash and artifact upload.

## Result

**VALIDATED**, narrowly: in the tested pinned ares interpreter scope, maskable
interrupt executable entry is governed by the full pending/mask/IE/EXL/ERL gate,
and every admitted pending bit selects the ordinary BEV-sensitive general vector
at `base + 0x180`. A Cause.IP bit, MI/device interrupt status, or other producer
signal must not by itself be promoted to handler reachability.

For a future whole-ROM certificate this should be represented as a conditional
root rule. A verifier that wants to exclude the interrupt handler must prove, for
the declared scope, that no reachable state can satisfy the architectural gate for
any relevant interrupt producer. Otherwise the general interrupt vector remains a
reachable executable root obligation. Conservative unconditional inclusion is safe
but less precise.

## Limitations / what this explicitly does not prove

- No physical N64 hardware was run. ares is the executed oracle; Gopher64 is an
  independent exact-pinned source cross-check.
- The fixture injects Cause.IP through ares' pending-bit API. It does not prove the
  reachability, queue lifecycle, acknowledgement behavior or timing of PI, SI, SP,
  VI, AI, DP, cartridge, timer, RDB or software interrupt producers.
- It does not prove the exact cycle at which an asynchronous device event becomes
  visible relative to an arbitrary instruction or delay slot.
- It does not exercise an interrupt arriving while a branch delay slot is pending,
  nor establish all EPC/BD corner semantics for asynchronous timing.
- It does not cover NMI, reset, cache-error vectors, watchdog behavior, save-state
  restore, boot/PIF/CIC roots, or TLB/refill exceptions.
- It does not provide handler-byte provenance or prove that handler bytes are
  immutable/executable for a particular ROM.
- Repeated dynamic observations are not exhaustive whole-ROM reachability and are
  not a closed-world proof.

## Integration recommendation

**ADOPT** the bounded gate/root semantics and encode interrupt reachability as an
explicit whole-ROM certificate obligation. Keep device-specific producer/timing
reachability and handler-byte provenance open; do not infer either from a pending
bit or emulator consensus.
