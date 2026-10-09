# SC/SCD storage-effect provenance in pinned ares

Status: **VALIDATED** for the bounded exact-pin interpreter fixture described below.

Recommendation: **ADOPT** the storage-sink classification rule and the fixture as regression evidence. Do **not** adopt pinned ares' reservation-lifetime behavior as an N64-wide invariant.

## Question

Can Plaid classify actual `SC` / `SCD` executable-mutation effects from completed storage sinks, instead of trusting the decoded conditional-store opcode, a success value in the architectural destination GPR, or one emulator's disputed LL/SC reservation semantics?

## Revisions

- Canonical Plaid baseline inspected before the claim: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256` (`main`).
- Successful experimental branch run: `4cc5086dcc5444d6946e8124d3b9b8fe75ed79c6` on `research/llsc-store-effects-gpt56sol`.
- Exact pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.
- Successful GitHub Actions run: `37915480398`, job `113770489471`.
- Retained artifact: `llsc-store-effects-results`, artifact ID `11609627687`.
- Artifact ZIP SHA-256: `fdf7c2889ac09afef2a0012186bda3866043a5182e878bc282db58a3a8b018e5`.
- Deterministic result JSON SHA-256 printed by the verifier: `08e7b5c6a79883663afb377514167170017ebcdca9379ffea59f7ac2b8d48569`.

## Hypothesis

For this controlled interpreter fixture:

1. a failed `SC` / `SCD` reservation produces no storage mutation event;
2. a successful uncached identity-RDRAM `SC` / `SCD` produces an immediate completed RDRAM write of exactly 4 / 8 bytes;
3. a successful cached `SC` / `SCD` mutates D-cache residency first, without immediately changing RDRAM backing, and becomes an RDRAM backing write only at an independently observed later writeback;
4. same-value successful stores still leave storage-effect evidence and therefore cannot be reconstructed by comparing old/new backing values alone.

If these hold, the bounded provenance classification can depend on sink effects even though the pinned references disagree about reservation lifetime.

## Baseline and relevant exact-pin source behavior

The pre-existing `research/llsc-provenance.md` was source-derived and deliberately left fresh physical/reference execution unresolved.

At the pinned ares revision, `CPU::write()` in `ares/n64/cpu/memory.cpp` returns `false` before a storage write when devirtualization/alignment fails. Successful cached accesses route to D-cache; successful direct/uncached accesses route to the bus. In `ares/n64/cpu/dcache.cpp`, a cache write sets the dirty byte mask for the written width regardless of whether the new payload equals the resident payload. These source facts motivated the observer placement, but the result below comes from executing decoded instructions rather than promoting those source paths directly into a Plaid invariant.

## Instrumentation

`spikes/043-ares-llsc-store-effects/` reuses Plaid's exact-pin ares builder and adds project-owned observers only at already-completed storage boundaries:

- identity-RDRAM scalar read/write callbacks, filtered to `RBusDevice::VR4300_UNCACHED`;
- identity-RDRAM burst read/write callbacks, filtered to `RBusDevice::VR4300_DCACHE`.

The shared builder requires raw/effective fetch-sensing capability whenever these RDRAM hooks are compiled. This fixture enables that build capability but installs no fetch observers, so it does not add a guest fetch access.

Fixture initialization/debugger writes and direct diagnostic backing reads temporarily disable the storage observers. They therefore cannot masquerade as guest mutation events.

## Fixture construction

The headless fixture disables CPU and RSP recompilers and executes decoded guest instructions through the pinned ares interpreter.

- data physical address: `0x00002000`;
- code physical address: `0x00006000`;
- cached data alias: `0xffffffff80002000`;
- uncached data alias: `0xffffffffa0002000`;
- cached code alias: `0xffffffff80006000`.

It runs 12 cases, six for `SC` and six for `SCD`:

1. reservation failure by executing `SC` / `SCD` without a preceding linked load;
2. aligned linked load followed by a deliberately misaligned conditional store;
3. successful uncached store changing bytes;
4. successful uncached same-value store;
5. successful cached store changing bytes;
6. successful cached same-value store.

`SC` writes `0x11223344`; `SCD` writes `0x1122334455667788`.

For successful cached cases, the harness samples backing and resident cache bytes immediately after the conditional store, then executes guest `CACHE 0x19` (hit writeback) and samples again. This separates cache-resident mutation from later backing mutation.

## Exact reproduction

From a clean checkout of this branch:

```sh
git clone https://github.com/ares-emulator/ares .refs/ares
git -C .refs/ares checkout 9408cb43d4948fc3ea6e152a307a34348df3fe04
python3 -m py_compile spikes/043-ares-llsc-store-effects/run.py
python3 spikes/043-ares-llsc-store-effects/run.py
```

The runner asserts the ares checkout is exactly the pinned revision and clean before building.

Expected terminal result from the validated run:

```text
PASS: 12 decoded SC/SCD cases preserve baseline/plain/traced state and classify sink effects
forgeries_rejected=5
results_sha256=08e7b5c6a79883663afb377514167170017ebcdca9379ffea59f7ac2b8d48569
```

## Deterministic observations

The retained trace has 10 uncached scalar events and 8 D-cache burst events across all 12 cases.

### Failed reservations

`sc_fail_uncached` and `scd_fail_uncached` both returned architectural success value `0`, left backing unchanged, and emitted **no scalar or burst storage event**.

This is the important provenance distinction: decoding an `SC` / `SCD` attempt is not evidence that storage mutated.

### Alignment faults

`sc_fault_uncached` and `scd_fault_uncached` each retained only the preceding linked-load read. Both reported AddressStore exception code `5` at `0xffffffffa0002001`, emitted no write event, and left backing unchanged.

### Successful uncached writes

Changed-value `SC` produced one 4-byte linked-load read followed by one completed 4-byte write at physical `0x2000`. Changed-value `SCD` produced the analogous 8-byte read then 8-byte write. Backing had already changed when sampled immediately after the conditional store.

Same-value uncached cases were deliberately adversarial. Their backing bytes were equal before and after, but the successful sink callback still recorded a 4-byte `SC` write or 8-byte `SCD` write. Therefore `before != after` is not a complete mutation census.

### Successful cached writes

For both changed-value and same-value cached `SC`:

- RDRAM backing remained unchanged immediately after `SC`;
- resident D-cache bytes contained `11 22 33 44`;
- D-cache dirty mask was `0x000f` before writeback;
- the trace contained a 16-byte D-cache line fill read at stage 1;
- guest `CACHE 0x19` later produced a 16-byte D-cache writeback at stage 2;
- dirty mask became zero after writeback;
- backing then contained the payload.

For both changed-value and same-value cached `SCD`, the same sequence held with resident bytes `11 22 33 44 55 66 77 88` and dirty mask `0x00ff` before writeback.

The same-value cached cases are particularly important: the initial and final backing bytes were identical, yet the cache line was dirtied and a later writeback occurred. Current-value comparison would lose that causal history entirely.

## Instrumentation neutrality and repeatability

The experiment builds and compares three modes:

1. `baseline.cpp`, compiled without the project storage sensors;
2. the sensor-capable binary with observers disabled (`plain`);
3. the sensor-capable binary with observers enabled (`traced`).

For every case, all three modes produced identical facts and identical machine digests. The digest covers all GPRs, HI/LO, PC, effective Count, LL/LLbit, exception state, BadVAddr, every D-cache line's tag/dirty/index/words, and full RDRAM.

A second traced execution was required to be byte-for-byte identical to the first. The successful run passed both checks.

## Adversarial verifier checks

The verifier cloned the successful trace and required rejection of five forged histories:

1. remove the successful same-value uncached `SC` write;
2. remove the successful same-value cached `SC` writeback;
3. insert a fake completed write into a failed-reservation `SC` case;
4. move a cached writeback from the post-store writeback stage into the store stage;
5. erase the dirty-residency evidence before the cached same-value `SC` writeback.

All five forgeries were rejected in run `37915480398`.

## Result

**VALIDATED**, within this fixture's declared scope.

A conditional-store mutation record should be driven by successful storage effects, not by the presence of an `SC` / `SCD` opcode or by its architectural success GPR alone. For cached destinations, the provenance model must preserve the cache-resident mutation separately from the later backing writeback. Same-value writes must remain first-class events.

This complements, rather than replaces, the earlier LL/SC semantic note. The old cross-reference disagreement about reservation lifetime still matters for deciding *whether* a conditional store should succeed in a semantic oracle. Once a particular execution reaches a completed storage sink, however, this experiment validates the bounded sink-level mutation classification independent of that disagreement.

## Limitations and explicit non-proofs

This result does **not** prove:

- hardware-accurate N64 LL/SC reservation lifetime;
- that pinned ares' reservation invalidation behavior is correct;
- TLB/mapped-address conditional stores or writable aliases;
- cache replacement/eviction writeback paths other than the explicit `CACHE 0x19` path used here;
- conditional stores to SP/PIF/MMIO or any non-RDRAM sink;
- interrupt, exception-return, context-switch, DMA, or cross-core reservation interactions;
- executable lifetime or fetch visibility after the write;
- that one emulator's observed success/failure is a platform-wide semantic invariant;
- completeness of Plaid's overall executable mutation census.

The useful result is narrower: **when actual execution reaches these completed RDRAM/D-cache storage effects, they provide enough evidence to distinguish no mutation, immediate uncached mutation, cache-resident mutation, and later writeback without relying on value matching.**
