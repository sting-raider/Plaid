# VR4300 SWC1 -> SP memory producer lineage

Result: **VALIDATED** for the bounded exact-pinned-ares interpreter scope described below.

This note does **not** claim that an FPR value's earlier origin is known. It validates the narrower causal link from an actually decoded `SWC1` instruction, through the FR-sensitive FPR lane selected by that instruction, to the actual completed SP DMEM/IMEM word sink. That is one missing layer beneath the six `SWC1` SP effects already identified by the producer-site census.

## 1. Exact revisions

- Plaid integration base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256` (`main` when the claim was taken).
- Research branch: `research/sp-cop1-producer-gpt56sol`.
- Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.
- Successful experiment commit: `4d5a2f683a4b38462328951abd6e4f96f792d5ba`.
- Successful GitHub Actions run: `37915388369`, job `113770187894`.

Relevant existing Plaid inputs were read-only: `research/sp-producer-sites.md`, `research/ares-cop1-store-mutation.md`, the CPU/SP backing work under `spikes/039-ares-cpu-sp-fetch/`, and the exact-pinned ares sources.

## 2. Falsifiable hypothesis

For interpreted VR4300 execution in the pinned ares revision, a scoped decoded `SWC1` can be joined to the completed `RSP::writeWord` effect at the SP memory aperture without relying on PC/value equality:

- FR=0 odd `ft` must select the high 32-bit lane of the paired even FPR;
- FR=0 even `ft` must select the low 32-bit lane of the paired even FPR;
- FR=1 must select the low 32 bits of the named FPR;
- the actual SP sink must decide DMEM versus IMEM;
- a successful equal-valued later store must mint a distinct producer generation;
- an equal-valued integer `SW` must not be relabeled as a COP1 producer;
- CU1-disabled, misaligned and TLB-failing `SWC1` executions must not fabricate an SP memory sink witness;
- an SP I/O write outside DMEM/IMEM must not be reported as an SP memory sink.

Any mismatch among decoded instruction, FR mode/FPR lane, actual sink bank/offset, payload, or ordered generation falsifies the proposed join.

## 3. Exact source path

`spikes/043-ares-sp-cop1-producer/source_guard.py` checks the exact pin before the executable test. It guards one copy of each required source marker:

1. `CPU::SWC1`: CU1 gate followed by `write<Word>(rs.u64 + imm, FT(u32))`.
2. The FR=0 odd-register path selecting `fpu.r[index & ~1].s32h`.
3. `Bus::write` routing physical `0x04000000..0x0407ffff` to `rsp.write<Size>`.
4. `RSP::writeWord` selecting IMEM when address bit `0x1000` is set, otherwise DMEM.

The guard passed in successful run `37915388369` before the emulator fixture was built.

## 4. Baseline and instrumentation

The fixture builds two exact-pinned ares executables with both CPU and RSP recompilers disabled:

- `baseline.cpp`: no SP callback shadow.
- `sensor.cpp`: reuses the already-validated `spikes/039-ares-cpu-sp-fetch/prepare.py` shadow around completed `RSP::writeWord` effects.

The observer records only completed SP word effects and does not perform guest reads, clock steps or register writes. `run.py` executes the sensor binary with the callback both disabled and enabled.

For every scenario, it requires equality of the architectural projection

`{scenario, phases, final DMEM hash, final IMEM hash, final RDRAM hash, final exception, frozen state}`

across baseline, sensor-disabled, sensor-enabled run 1 and sensor-enabled run 2. The two enabled textual outputs must also be byte-identical. Successful Actions run `37915388369` passed all of these neutrality/repeat assertions.

## 5. Fixture construction

The CPU executes actual encoded instructions through `cpu.instruction()` from uncached identity-mapped RDRAM. Stores target uncached KSEG1 aliases of SP memory so that the actual CPU translation/bus/RSP path runs.

The first four FPRs are initialized to:

```text
f0 = 0x1122334455667788
f1 = 0x99aabbccddeeff00
f2 = 0xaabbccdd55667788
f3 = 0x13579bdf2468ace0
```

The matrix contains eleven completed SP memory sinks:

- FR=0 `SWC1 f0` -> DMEM: expected `0x55667788`.
- FR=0 `SWC1 f1` -> DMEM: expected paired-even high lane `0x11223344`.
- FR=1 `SWC1 f1` -> DMEM: expected named-register low lane `0xddeeff00`.
- Corresponding FR-sensitive stores into IMEM, including FR=0 odd `f3` selecting `f2` high `0xaabbccdd`.
- Two FR=1 `SWC1` stores from `f0` and `f2` to the **same DMEM word**. Both payloads are `0x55667788`, so value/address matching cannot distinguish their producer identities; the ordered sink events must.
- An integer `SW r9` of the same `0x55667788` payload to a location also used by `SWC1`, serving as an equal-payload non-COP1 decoy.

Separate fresh-process scenarios execute:

- CU1-disabled `SWC1`;
- misaligned `SWC1`;
- unmapped-TLB `SWC1`;
- `SWC1` to SP I/O rather than the DMEM/IMEM backing aperture.

## 6. Replay verifier

`verify.py` does not accept an event merely because its value looks like an FPR value. For every completed sink it:

1. requires strictly increasing observer ordinals;
2. requires a CPU-originated completed SP memory write;
3. retrieves the actual phase/instruction context;
4. checks bank and word offset against the store's effective address;
5. decodes the opcode;
6. for `SWC1`, independently recomputes the expected `u32` payload from `(FR, ft)` and the fixed FPR snapshot;
7. for the integer `SW` decoy, checks the GPR payload but does not create a COP1 witness.

A COP1 witness is therefore keyed by the concrete completed sink generation, not by `(PC, address, value)` equivalence.

## 7. Adversarial cases

The verifier mutates the real matrix history six ways and requires all six forgeries to fail:

1. change the SP bank while leaving the payload intact;
2. change one `SWC1` sink payload;
3. relabel the equal-payload integer `SW` sink as the preceding `SWC1` phase;
4. delete one of the same-value/same-address `SWC1` generations;
5. reverse the ordinals of those same-value generations;
6. relabel an unrelated equal-payload `SWC1` sink as an earlier producer phase.

Successful run output:

```text
PASS exact pinned ares decoded SWC1 -> SP producer matrix
matrix_events=11 cop1_witnesses=10 forged_rejected=6
results_sha256=cd2e6e403fce83352e4e9d1a13f5cacc7705e45f2a7369186d1d1bfaadd4cc73
```

The matrix therefore contained ten decoded `SWC1` producer witnesses plus one integer-store decoy, and all six deliberate forged histories were rejected.

## 8. Negative/fault observations

The fresh-process negative scenarios passed these assertions in the same successful run:

- CU1 disabled: exception code 11, no SP memory sink event.
- misaligned word store: exception code 5, no SP memory sink event.
- unmapped TLB address: exception code 3, no SP memory sink event.
- SP I/O target: no exception, but no DMEM/IMEM backing event because the address routes to SP I/O rather than the memory bank sink being certified.

This distinction matters: a decoded `SWC1` attempt is not itself a storage-effect witness.

## 9. Reproduction

From a checkout containing the branch artifacts and an exact pinned ares checkout at `.refs/ares`:

```bash
python3 -m py_compile \
  spikes/043-ares-sp-cop1-producer/source_guard.py \
  spikes/043-ares-sp-cop1-producer/verify.py \
  spikes/043-ares-sp-cop1-producer/run.py
python3 spikes/043-ares-sp-cop1-producer/source_guard.py
python3 spikes/043-ares-sp-cop1-producer/run.py
```

The CI workflow `.github/workflows/research-sp-cop1-producer.yml` checks out the exact ares pin and runs those commands. Run `37915388369` is the reproducible successful execution.

## 10. Failed harness checkpoint retained

The first two Actions runs (`37915049640` and diagnostic rerun `37915197552`) failed **before emulator execution** because the fixture's local `struct Event` collided with an imported ares/nall symbol. Diagnostic run `37915197552` exposed the compiler error. Commit `4d5a2f683a4b38462328951abd6e4f96f792d5ba` renamed only that local harness type to `SpSinkEvent`; the experiment, expectations, instrumentation and upstream pin were otherwise unchanged. The next run passed.

These failed runs are not counted as emulator evidence, but are retained so the successful result is not presented as a frictionless first attempt.

## 11. Result

**VALIDATED**, with bounded scope.

For exact pinned ares interpreted CPU execution, a decoded `SWC1` can be causally normalized to a concrete SP DMEM/IMEM word producer generation by joining the instruction context to the actual completed `RSP::writeWord` sink and using the instruction-time FR/FPR selection. The same-value cases show why payload equality cannot substitute for ordered sink identity. Faulting attempts and non-memory SP I/O accesses correctly fail to create that memory-producer witness.

This closes one specific gap in the existing SP producer census: the six observed `SWC1` SP effects cannot be treated as ordinary integer stores, but their immediate CPU-side producer can be represented as `SWC1 source PC + instruction generation + FR-sensitive FPR lane -> completed SP sink generation`.

## 12. Limitations

- This does not recover the **earlier origin of the FPR bytes**. `LWC1`, integer-to-FPR moves, FPU arithmetic/conversions and other FPR writers still require their own ordered source history before the provenance can be extended further upstream.
- This is not a whole-ROM writer census and does not prove that the existing six boot-prefix SWC1 observations are exhaustive.
- This validates pinned ares behavior, not N64 hardware by emulator fiat.
- SDC1 is outside this SP-memory fixture. Existing COP1 mutation research covers its FR-sensitive payload behavior for RDRAM, but 64-bit writes to the RCP/SP aperture have different bus support constraints and are not promoted here.
- Cached SP access is not part of this positive scope; the existing backing work already treats invalid/cached RCP paths separately.
- This does not establish later executable lifetime, RSP fetch, CPU refetch, DMA egress, overlay identity or closure.
- The fixture snapshots known FPR state; it does not yet carry per-byte generations within an FPR across earlier instructions.

## 13. Architectural consequence

When extending executable-byte provenance for CPU-originated SP mutations, the mutation census must not classify a completed SP word solely as an integer-register producer. For `SWC1`, provenance needs an instruction-scoped COP1 source descriptor containing at least `ft`, FR mode and the resolved 32-bit FPR lane, then must be discharged only by the corresponding completed physical SP bank/offset sink generation. Same-value writes still create new generations. If the FPR's upstream history is unavailable, the immediate `SWC1 -> SP sink` edge can be retained while the earlier origin remains explicitly unknown rather than guessed from matching values.
