# CPU SDL/SDR storage effects in SP memory

Status: **PARTIAL**

Exact ares behavior is validated for the declared synthetic direct-SP scope below. A hardware-facing aligned `SD` control corroborates ares' one-word `Dual` SP sink, but there is no pinned hardware `SDL`/`SDR` SP-memory oracle and exact pinned Gopher64 disagrees with ares on 10/16 big-endian `SDL`/`SDR` images. Therefore the ares `SDL`/`SDR` truth table must **not** be promoted to an N64-wide invariant.

## Question

When decoded VR4300 `SDL`/`SDR` instructions target CPU-visible RSP DMEM or IMEM, what completed storage effects does exact pinned ares produce after its typed Byte/Half/Word/Dual decomposition reaches the concrete SP memory sink?

This closes a gap left by the prior normal-RDRAM `SD`/`SDL`/`SDR` experiment and the CPU `SWL`/`SWR` -> SP-memory experiment. It deliberately asks about completed storage effects, not merely decoded opcode width or nominal lane masks.

## Exact revisions

- Plaid canonical base at claim time: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- research branch: `research/cpu-sp-sdl-sdr-gpt56sol`
- exact tested workflow source commit: `448caf9930387d8f5c3a25e5cc3940c82e9260bb`
- exact CI receipt commit: `6c3871c1d4009cd33c46b4472276158091f92fc1`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`
- successful GitHub Actions run: `37918775541`

No upstream reference is added as a Plaid production dependency.

## Falsifiable hypothesis

Initial hypothesis: exact pinned ares decomposes `SDL`/`SDR` into typed writes, but CPU-visible SP memory widens those writes to concrete full-Word `RSP::writeWord` storage effects. Therefore some partial doubleword stores should overwrite bytes outside the normal RDRAM architectural partial-store subset. The initial model further assumed Byte/Half values would be truncated to their nominal width before reaching the SP Word sink.

The broad widening hypothesis survived. The Byte/Half truncation premise was **rejected by the first executable run** and corrected before the successful matrix.

## Relevant exact ares path

At the pinned revision:

1. `CPU::SDL` / `CPU::SDR` in `ares/n64/cpu/interpreter-ipu.cpp` decompose one decoded instruction into ordered `write<Byte/Half/Word/Dual>` calls.
2. `CPU::write` in `ares/n64/cpu/memory.cpp` applies reverse-endian physical-address lane mapping when required, then forwards uncached accesses to the bus.
3. `Memory::RCP::write` in `ares/n64/memory/io.hpp` normalizes Byte/Half/Word accesses into a full `writeWord` call.
4. Critically, Byte/Half data are not pre-truncated before the shift into the eventual `u32` sink. Higher source bits can therefore fill additional Word lanes.
5. `Memory::RCP::write<Dual>` performs only `writeWord(address, data >> 32, thread)`. It does **not** issue a second Word sink.
6. `RSP::writeWord` in `ares/n64/rsp/io.cpp` commits the complete 32-bit value to DMEM or IMEM. IMEM also invalidates the RSP recompiler entry.

The runner hash-guards all four exact source files so later upstream changes fail closed instead of silently inheriting these conclusions.

## Baselines

The existing `research/ares-sd-sdl-sdr-executable-mutation.md` established normal uncached RDRAM `SDL`/`SDR` byte semantics and explicitly did not cover SP memory.

The existing CPU partial-store SP work established that SP storage behavior can be wider than the nominal CPU subword store. That work covered `SWL`/`SWR`, not `SDL`/`SDR`.

This experiment composes those two findings rather than re-running either one.

## Fixture and commands

Durable spike: `spikes/044-ares-cpu-sp-sdl-sdr/`

The driver links unmodified exact pinned ares and executes real encoded VR4300 stores through `cpu.instruction()` with CPU and RSP recompilers disabled. Targets are direct uncached KSEG1 CPU-visible SP DMEM and IMEM. A 24-byte target bank window and a differently initialized non-target bank are snapshotted before and after each instruction sequence.

The matrix is:

- `SDL`: all 8 offsets, big and forced little endian, DMEM and IMEM;
- `SDR`: all 8 offsets, big and forced little endian, DMEM and IMEM;
- aligned `SD`: big/little endian, DMEM and IMEM;
- endian-correct `SDL`+`SDR` pairs at all 8 starting offsets, both endians and both banks.

Total: **100 cases**. Every case is executed twice and required to produce byte-identical JSON.

Reproduction after exact refs are checked out at `.refs/ares`, `.refs/gopher64`, and `.refs/n64-systemtest`:

```text
python3 -m py_compile spikes/044-ares-cpu-sp-sdl-sdr/*.py
python3 spikes/044-ares-cpu-sp-sdl-sdr/model.py
python3 spikes/044-ares-cpu-sp-sdl-sdr/compare_refs.py
python3 spikes/044-ares-cpu-sp-sdl-sdr/run.py
```

CI workflow: `.github/workflows/research-cpu-sp-sdl-sdr.yml`.

## First-run falsification

The first exact execution, Actions run `37918258617`, failed the initial model at big-endian `SDL` offset 1 targeting DMEM.

Observed first eight bytes:

```text
00 11 22 33 44 55 66 77
```

The initial model had pre-truncated Byte/Half subwrite data and therefore predicted different lanes in the first Word. Source reinspection showed that pinned ares forwards the full `u64` data argument through the RCP adapter and truncates only at the final `u32 writeWord` conversion. This permits higher source bits to occupy lanes outside the nominal Byte/Half width.

The model was corrected to encode that source behavior, not patched case-by-case. The subsequent full exact run passed.

## Deterministic ares observations

Successful Actions run: `37918775541`.

Result payload:

```text
7f733dea964651ca478077d58713e8788fdbbc251fdebad078fffd6084ab3497  target/ares-cpu-sp-sdl-sdr/results.json
```

Source-derived model payload:

```text
330333971329c4bd51f1f7e82eb5e005e07531a6a12d57341a071383b317400a
```

Observed matrix facts:

- **100/100** exact-pinned decoded cases passed the corrected source-derived model; each was repeated twice with byte-identical output.
- All **8/8** tested single-instruction cases whose `SDL`/`SDR` decomposition selected the ares `Dual` SP path changed exactly **4 bytes**, not 8.
- **24/24** tested single-instruction cases whose decomposition reached two distinct SP Word sinks changed both Word sinks.
- **16/16** tested single-instruction cases contained multiple typed subwrites that normalized to the same SP Word sink; chronology matters because a later full-Word sink can replace an earlier one.
- Endian-correct paired stores changed **4, 8, or 12 bytes** depending on alignment/path, not a fixed eight-byte architectural span.
- Aligned `SD` changed only the upper 32-bit SP Word in all four ares controls.
- The non-target SP bank remained unchanged in every tested case.
- No tested direct KSEG1 case raised an exception.

Representative IMEM counterexamples from payload `0x1122334455667788` and initial bytes `a0 a1 a2 a3 a4 a5 a6 a7`:

```text
big SDL offset 0 -> 11 22 33 44 a4 a5 a6 a7
big SDL offset 1 -> 00 11 22 33 44 55 66 77
big SDR offset 2 -> 66 77 88 00 a4 a5 a6 a7
big SD  offset 0 -> 11 22 33 44 a4 a5 a6 a7
```

These are concrete counterexamples to mutation models that infer SP storage effects solely from the decoded opcode's nominal width or the ordinary RDRAM lane mask.

## Independent reference comparison

Pinned Gopher64 uses a materially different implementation:

- its `SDL`/`SDR` code computes a shifted 64-bit value and issues **two** 32-bit `data_write` calls;
- its SP `write_mem(..., _mask)` ignores the supplied mask and commits the entire supplied 32-bit value.

The guarded source comparison found exact pinned Gopher64 and exact pinned ares disagree on **10/16** big-endian single `SDL`/`SDR` SP images:

```text
SDL mismatches: offsets 0, 4, 5, 6, 7
SDR mismatches: offsets 0, 1, 2, 3, 7
```

They agree on the other six tested big-endian images. This disagreement is evidence against treating either emulator's `SDL`/`SDR` SP behavior as platform truth.

Pinned n64-systemtest provides hardware-facing SP-memory tests for `SB`, `SH`, `SW`, and `SD`. Its `SD` test verifies that storing `0xABCDEF98_76543210` changes only the first 32-bit SP word to `0xABCDEF98` while leaving the next Word unchanged. That independently supports the surprising upper-32-only aligned `SD` control observed in ares.

The pinned systemtest contains **no `SDL` or `SDR` SP-memory fixture**, so it cannot resolve the ares/Gopher disagreement for partial doubleword stores.

## Source guards from successful run

```text
ares CPU interpreter-ipu.cpp  495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152
ares CPU memory.cpp           55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74
ares memory/io.hpp            54089251052dbffddf7ae77819c3a3bb494cf7269ae874a3015a23907370a69c
ares RSP io.cpp               60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860
Gopher cpu_instructions.rs    f2136f77815ecacbfe3c6a748b9070d295a2cb77561a850495806e623a6ed4c5
Gopher rsp_interface.rs       a5864c02f742bc922284d7866bbe76fe80efda63d3a3c69af7e37c50fe661053
n64-systemtest sp_memory      9096a6eefc7a8a248642ca782e25be67f51d9620d81cf2a7322e9fd5254af074
```

## Consequence for Plaid

The useful validated architectural requirement is not an ares-specific table. It is the stronger provenance/mutation rule:

1. a CPU store opcode and nominal lane mask are insufficient evidence for final executable storage effects at SP memory;
2. mutation capture must normalize through the actual destination/device sink and retain the ordered concrete Word effects;
3. for lineage, multiple subwrites belonging to one decoded producer must remain distinguishable until their final sink effects are known, because later effects can overwrite earlier ones;
4. one decoded 64-bit store can have a four-byte completed storage effect at SP, while one partial 64-bit store can affect two complete Word sinks;
5. until `SDL`/`SDR` SP behavior is resolved against hardware or a stronger oracle, closure logic must not bake one emulator's detailed truth table into a platform-wide proof.

The aligned `SD` upper-Word-only effect has both exact ares execution and hardware-facing n64-systemtest support in the tested DMEM-facing case. The exact `SDL`/`SDR` offset table remains reference-dependent.

## Limitations and explicit non-claims

- This does not establish N64-wide `SDL`/`SDR` SP behavior. Exact pinned ares and Gopher64 disagree.
- There is no hardware `SDL`/`SDR` SP-memory matrix in the pinned n64-systemtest revision.
- The n64-systemtest `SD` evidence exercises SP memory at its DMEM-facing base; it does not independently establish the IMEM control.
- Successful synthetic ares targets use direct uncached KSEG1 addresses. Cached/TLB aliases, exceptions, MMIO edge regions, and cross-bank wrap behavior are outside this experiment.
- Little-endian cases force the ares context to execute its reverse-endian path; this does not prove the full guest-driven Status.RE/TLB setup sequence.
- The experiment proves storage effects for the declared synthetic execution path, not that commercial titles use these opcodes to mutate executable SP memory.
- Repeated deterministic execution is not a closed-world reachability proof.

## Result and next experiment

**PARTIAL.** Exact pinned ares' concrete SP sink effects are reproducibly characterized and the aligned `SD` four-byte effect has independent hardware-facing support, but the platform-wide `SDL`/`SDR` semantics remain unresolved because pinned Gopher64 disagrees and the pinned hardware suite lacks those cases.

**Recommendation: INVESTIGATE.** Extend the hardware-facing n64-systemtest SP-memory suite with `SDL` and `SDR` for all eight offsets, using payloads/initial Words chosen to expose both full-Word widening and one-vs-two-Word behavior. Run the matrix on real hardware before promoting any detailed emulator-specific `SDL`/`SDR` SP truth table into Plaid closure logic.
