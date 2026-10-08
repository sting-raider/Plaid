# Pinned ares PIF-ROM backing witness

Date: 2026-10-08
Plaid integration base: `5a24b9ccf3064d96f2f0d50fd3df1e50ee6d4862`
Research branch: `research/pif-rom-backing-ares-gpt56sol`
Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
Executable sensor commit: `91a8502f911cbf232671ee55dfd7982aca8aa7c0`
Successful GitHub Actions run: `37848511682`
Verdict: **VALIDATED** for the bounded interpreter fetch-stage hypothesis below.

## Question recovered from the earlier PARTIAL result

`research/pif-rom-backing.md` established from source inspection and an independent
predicate model that physical address or returned value is insufficient to prove
that a CPU PIF fetch actually came from supplied PIF firmware. It explicitly left
one missing experiment: build the exact pinned ares revision, instrument the real
backing branch, and demonstrate an instrumented-vs-uninstrumented neutrality
check with adversarial counterexamples.

This follow-up performs that experiment. It does not alter Plaid production code
or the pinned upstream checkout in place. The build recipe generates disposable
instrumented ares source under `target/`.

## Falsifiable hypothesis

Within pinned ares' interpreter path, a temporary fetch context established around
the actual `CPU::fetch` backing operation can be joined uniquely to the successful
unlocked `PIF::readInt -> rom.read<Word>` branch. The resulting witness must be
absent when SI returns `busLatch`, when PIF ROM lockout returns zero, when the
access selects PIF RAM, when a cached non-RDRAM access is rejected/frozen, and
when a genuine but unrelated PIF-ROM read occurred before the fetch. Mirrored
physical PIF addresses may legitimately select the same masked ROM offset, but
the fetch event must retain the distinct physical address.

The instrumentation must not issue an extra guest read or clock and must preserve
the tested guest-visible state relative to an uninstrumented baseline.

## Exact upstream seam

The experiment is built from a clean checkout of ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`.

The relevant source contract is:

1. `CPU::instruction()` devirtualizes the current PC and then calls
   `CPU::fetch(access)` before instruction prologue/execute.
2. `CPU::fetch` performs its existing `step`, endian-adjusts the physical address,
   and either uses I-cache or `busRead<Word>(paddr)`.
3. the N64 bus maps the PIF physical interval through SI;
4. `SI::readWord` may finish an `ioBusy` access and return `io.busLatch` before PIF
   is touched;
5. `PIF::readInt` masks the delegated address with `0x7ff`, returns zero under ROM
   lockout, returns `rom.read<Word>(address)` only for the unlocked ROM branch, and
   otherwise returns PIF RAM.

The research-only generated patch brackets the existing backing expression in
`CPU::fetch` with `plaidPifFetchBoundary(begin/end, ...)`. Separately, it inserts
`plaidPifRomBackingRead(offset, word)` immediately after the existing successful
`rom.read<Word>(address)` and before returning that same word. The observer only
joins a backing read while a fetch is active. It performs no extra emulated read,
write, or clock.

## Fixture

`experiments/pif-rom-backing/ares_driver.cpp` installs a deterministic synthetic
1,984-byte PIF image. No Nintendo firmware bytes are committed. The fixture uses:

- offset `0x000`: `0x3c1abfc0`;
- offset `0x004`: zero, intentionally colliding with the lockout-zero value;
- offset `0x008`: another `0x3c1abfc0`, intentionally defeating value-to-offset
  inference;
- deterministic generated words elsewhere.

The `natural` case starts from a normally powered N64 CPU and performs the exact
`devirtualize<Read, Word>(cpu.ipu.pc) -> CPU::fetch(access)` fetch stage used by
`CPU::instruction()`. It intentionally does not decode/execute the synthetic word.
An earlier attempt to run arbitrary synthetic PIF bytes through a complete
`CPU::instruction()` caused the one-step harness process to leave before harness
closeout, so no claim is made about synthetic firmware boot correctness.

The other cases directly issue the same `CPU::fetch` stage with controlled
physical/cache inputs or perform a non-fetch PIF read.

## Executed counterexamples

The successful run executes baseline, instrumented, and an exact instrumented
repeat for all nine modes:

| Mode | Expected provenance behavior |
| --- | --- |
| `natural` | physical `0x1fc00000`, witness ROM offset `0` |
| `mirror` | physical `0x1fc00800`, witness ROM offset `0` |
| `high_mirror` | physical `0x1fcff800`, witness ROM offset `0` |
| `busy_latch` | returns the same fixture word through SI latch; **no** ROM witness |
| `lockout_zero` | returns zero under ROM lockout; **no** ROM witness |
| `pif_ram_same_value` | PIF RAM contains the same fixture word; **no** ROM witness |
| `cached_pif` | cached non-RDRAM path is rejected/frozen; **no** ROM witness |
| `stale_decoy` | first performs a genuine non-fetch ROM read, then equal-valued SI latch fetch; prior read stays unattributed and fetch gets **no** witness |
| `nonfetch_rom` | genuine PIF ROM backing read outside any CPU fetch; recorded as unattributed, with no fetch event |

Run `37848127747` was intentionally diagnostic after the orchestrator encountered a
clean-host first-run quirk. Its direct per-mode executions exposed the concrete
observations:

- baseline and instrumented `natural`, `mirror`, and `high_mirror` all returned
  `1008385984` (`0x3c1abfc0`);
- instrumented `natural` recorded physical `0x1fc00000`, ROM offset `0`, one backing
  read and zero unattributed reads;
- instrumented `mirror` retained physical `0x1fc00800` while recording ROM offset
  `0`;
- instrumented `high_mirror` retained physical `0x1fcff800` while recording ROM
  offset `0`;
- `busy_latch`, `lockout_zero`, `pif_ram_same_value`, and `cached_pif` each emitted
  a fetch with `witness: null` and zero ROM backing reads;
- `stale_decoy` recorded exactly one unattributed backing read and left the later
  equal-valued fetch witness null;
- `nonfetch_rom` recorded exactly one unattributed backing read and no fetch event.

For every paired mode, the observed guest machine checkpoint matched between the
baseline and instrumented binaries. The compared checkpoint includes PC, all GPRs,
HI/LO, effective Count, exception code/EPC, selected PIF/SI state, returned word,
and SHA-256 hashes of RDRAM, SP DMEM and PIF RAM. The instrumented repeat also
matched its first instrumented result exactly.

## Host first-run quirk and harness hardening

On a clean GitHub Actions host, the first successful ares fixture subprocess can
exit with status 0 without emitting the JSON checkpoint. Re-running the already
built baseline immediately emits the full checkpoint, after which the same host
also runs the instrumented binary normally. This is a host/setup artifact, not an
observed guest-state difference.

`experiments/pif-rom-backing/run_ares.py` therefore permits one retry only when a
successful process emitted no JSON. It also selects the final JSON line because
the intentional `cached_pif` counterexample causes ares to print its
`Bus::freezeUncached` diagnostic before the checkpoint. Two empty successful runs
remain a hard failure.

## Independent model recheck

The existing independent predicate model was re-run at 1,000,000 deterministic
cases in every CI attempt. Final successful CI reproduced the exact established
counts:

- ROM positives: `92,583`;
- negatives: `907,417`;
- mirrored positives: `92,426`.

Hashes remained:

- `experiments/pif-rom-backing/witness_model.py` SHA-256:
  `4b35066e8bfc6e2bfc9064bba38e2ecb6ec4a199ca6bf112f6fc63677eaab036`;
- model JSON SHA-256:
  `0fc0d77daa8b3c745eba67d40954a7ec7a7b253370527c55f98abf1270f09476`.

## Final executable result

Successful Actions run `37848511682` reports:

```text
result: VALIDATED
ares_revision: 9408cb43d4948fc3ea6e152a307a34348df3fe04
firmware: synthetic-original-fixture
instrumentation_machine_state_equal: true
instrumented_repeat_equal: true
results_sha256: 24a38c3aa6814f0ec3bb975f5d6fc21e84a4780e27f33323917b49412d73f81a
```

Reproduction from a checkout containing the exact pinned reference at
`.refs/ares`:

```sh
python3 -m py_compile experiments/pif-rom-backing/witness_model.py \
  experiments/pif-rom-backing/run_ares.py
python3 experiments/pif-rom-backing/witness_model.py --fuzz 1000000
python3 experiments/pif-rom-backing/run_ares.py
```

An optional local 1,984-byte NTSC PIF ROM may be passed with `--firmware`; the
runner rejects it unless its SHA-256 is
`fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd`.
The bytes are never copied into committed output.

## What this validates

For this pinned ares interpreter scope, the proposed witness location is strong
enough to distinguish an actual successful PIF-ROM backing read from SI latch,
lockout, PIF RAM, cache rejection, equal-value, mirrored-address and stale-read
decoys. A fetch event can therefore carry both its actual physical address and the
masked PIF-ROM byte offset without inferring origin from value or address alone.

This upgrades the earlier missing **actual-ares instrumentation/neutrality** step
from `research/pif-rom-backing.md` for the bounded fetch-stage experiment.

## Remaining gaps / non-claims

This result does **not** prove:

- authenticity or correctness of any supplied PIF firmware image;
- a complete natural PIF boot capture with the known real firmware;
- full `CPU::instruction()` execution of the synthetic fixture;
- recompiler/JIT equivalence; the tested scope intentionally uses the interpreter;
- PIF firmware immutability or complete PIF lifetime semantics;
- exception/TLB/interrupt closure;
- that every executable root in PIF/RAM/SP has a witness;
- a production Plaid trace/ProgramMap schema, importer, or closed-world proof;
- native completeness.

The optional known real firmware path should be rerun locally if a licensed/local
copy is available, and the primary integrator still needs to decide how PIF source
identity (device namespace + declared input digest + offset) fits the unified
ordered provenance event model.

## Recommendation

**PRIMARY-INTEGRATOR-REVIEW.** Adopt the semantic witness contract if it composes
cleanly with the current ordered provenance work: originate PIF firmware provenance
only at the successful backing read inside an active fetch context, retain the
fetch physical address separately from the masked ROM offset, and treat unrelated
backing reads as unattributed rather than retroactively joining by address/value.
Do not merge this research branch wholesale; transplant or reimplement only the
small observer/event semantics after reproducing the evidence.

Primary reproduction, 2026-10-09: all nine baseline/instrumented/repeated modes
pass on WSL Ubuntu x64 G++ 15.2, reproducing the exact synthetic result digest
`24a38c3aa6814f0ec3bb975f5d6fc21e84a4780e27f33323917b49412d73f81a`.
The optional known local NTSC firmware path also passes all nine modes, including
the powered CPU's fetch stage, with unchanged reported checkpoints and repeats.
Its result digest is
`39fe95927fd1d69b13f35343c948c634bcfb42816515284820d5f6006395b31d`.
The supplied image digest remains
`fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd`;
firmware and all generated results stay ignored. The adapter supports the current
optional builder signature and translates Windows paths through WSL. This closes
the actual fetch-stage/neutrality and optional-image test gaps, not complete boot,
firmware authenticity, lifetime or production schema/closure obligations.
