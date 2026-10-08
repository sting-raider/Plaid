# Translated/degraded scalar RDRAM backing provenance

Status: **VALIDATED** for the bounded pinned-ares scalar `Word` ordinary-RDRAM read path described below.

## Scope and hypothesis

This experiment asked whether a successful non-identity scalar RDRAM read in pinned ares can expose trustworthy byte-origin evidence without conflating the requested physical address, the actual mapped backing bytes, and the value delivered after current-control-input (CCI) degradation.

Plaid branch base/merge-base at closeout: `a36e14b99601d790c794a67f18ef2ffaa90e9acd` on `codex/executable-discovery`.

Reference revision: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.

Validated proposition, for this exact path and fixture scope:

> A successful non-identity scalar `Word` ordinary-RDRAM read can emit a two-stage witness containing the request address, translated backing address/chip, raw backing value, CCI state, and final delivered value. The raw-byte origin is the completed `Memory::Writable::read<Word>` at the translated backing address. The delivered value is a separate post-read transformation result. Missing mappings or paths that never execute that ordinary backing read must not fabricate this witness.

## Exact pinned-source path

At the ares pin, `ares/n64/rdram/rdram.hpp` performs the non-identity ordinary scalar read as:

1. `translate(address)`;
2. on failure, acknowledge RI error for hardware requestors and return zero;
3. derive `chipIndex = mapped / 2_MiB`;
4. execute `Memory::Writable::read<Size>(mapped)`;
5. return `degrade(mapped, raw_value, chipIndex)`.

`ares/n64/rdram/rdram.cpp` supplies the two critical transformations:

- `RDRAM::Writable::translate(u32 address)` selects an enabled/present chip whose `deviceID >> 1` matches the request page and returns `chip_index * 2_MiB + page_offset`.
- `RDRAM::Writable::degrade(...)` returns the raw value when `cci >= ccHigh`, returns zero when `cci <= ccLow`, and otherwise probabilistically clears set bits.

The EBus path is materially different: non-identity `ebusRead` translates and then reads `self.hidden.nibble(mapped & ~3)`. It does not perform the ordinary `Memory::Writable::read` whose provenance is validated here.

## Instrumentation

Durable spike: `spikes/033-ares-rdram-translated-backing/`.

The runner reuses the existing `spikes/003-ares-oracle/run.py` recipe but patches a copy of that Python builder **in memory**. It does not modify the canonical builder or upstream checkout. Source guards require the exact pinned scalar-read, translate, degrade, and EBus signatures.

The generated shadow `rdram.hpp` changes only the successful non-identity ordinary scalar read sequence:

- evaluate the existing translation once;
- snapshot translated address/chip;
- perform the existing backing read once;
- snapshot `cci`, `ccLow`, and `ccHigh`;
- execute the existing `degrade()` once;
- invoke an optional callback only after degradation;
- return the already-computed delivered value.

The callback records:

- request physical address;
- translated backing physical address;
- width;
- RBus requestor/device;
- backing chip index;
- raw backing value;
- delivered post-CCI value;
- `cci`, `ccLow`, `ccHigh`.

No extra guest read, backing read, `degrade()` call, clock step, or random draw is introduced.

## Adversarial fixture

The direct-component fixture disables recompilers and uses deterministic entropy. Two present chips are deliberately crossed:

- chip 0: `deviceID = 2`, so request page `0x200000` maps to backing page `0x000000`;
- chip 1: `deviceID = 0`, so request page `0x000000` maps to backing page `0x200000`.

Backing words include:

- `0x000000 = 0x11223344`;
- `0x000004 = 0xdeadbeef` as a request-address decoy;
- `0x200000 = 0xf0f0aa55`;
- `0x200004 = 0xdeadbeef` as the true mapped source for request `0x000004`;
- `0x200008`, `0x20000c`, and `0x200010 = 0xffffffff` for degradation cases.

The executed matrix covers reliable remaps in both directions, equal-valued decoy data, zero-threshold degradation, two consecutive partial stochastic degradations, missing mapping, inactive RI, an identity-map ordinary read, and an EBus HiddenRAM read.

## Exact execution evidence

GitHub Actions run: `37850699431`

Tested spike/workflow head: `64053e2f50f8baf9bcf10155478130c03c5fa07d`.

Job: `translated-backing-provenance` (`113562595679`), Ubuntu 24.04. The workflow fetched and verified exact ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`, syntax-checked the runner, built the baseline and instrumented reference, executed the matrix, and hashed generated result payloads.

Observed successful translated witnesses:

| request | mapped backing | chip | raw | CCI | delivered |
| --- | --- | ---: | ---: | ---: | ---: |
| `0x000000` | `0x200000` | 1 | `0xf0f0aa55` | 63 | `0xf0f0aa55` |
| `0x200000` | `0x000000` | 0 | `0x11223344` | 63 | `0x11223344` |
| `0x000004` | `0x200004` | 1 | `0xdeadbeef` | 63 | `0xdeadbeef` |
| `0x000008` | `0x200008` | 1 | `0xffffffff` | 8 | `0x00000000` |
| `0x00000c` | `0x20000c` | 1 | `0xffffffff` | 12 | `0xd3d8e033` |
| `0x000010` | `0x200010` | 1 | `0xffffffff` | 12 | `0x648097e1` |

No translated ordinary-backing event was emitted for the missing mapping, inactive RI, identity-map read, or EBus HiddenRAM read.

Final state/result checkpoints from the strengthened run:

- event count: `6`;
- RAM SHA-256: `1a3878a61b07285a6e64dd47dc33aaeb22e4ac16420fd638294ad9786787d11a`;
- HiddenRAM SHA-256: `4dab50b5f347f35e3ce16a7b11b946f5ac1886edc038e572a1ddce25ebe1f962`;
- raw traced-result stream SHA-256 recorded by the runner: `2b12e5a0f8f382b28186efb52a4bceb31486a96c8716165c87e99489bad93b4d`;
- generated `results.json` SHA-256: `faaf34692a4be28700d3a680f8a066f5bddecc6bc3ec7331b2dd14cad7211050`;
- generated `manifest.json` SHA-256: `a3e262b427df526d41ee0065efcf3fb37c7729b84b5b9c63632b0092b4619418`;
- driver SHA-256: `ccc8b3b57656c6313ec5396d4daaddb16a87b9bc10497ed97170b169e7420f93`;
- observer SHA-256: `733028a6dec57d1beffb062ce8f8a2b89c8f78f42128d0d32b113ea8cb74485d`;
- canonical builder SHA-256: `2002c082335ba553ce20c87736b7b2d7018cbe59e2c84011532a45f72be43fdb`;
- in-memory patched builder SHA-256: `0e0fb4582ff745bdf5864b170ad0a0de037223f4f8c61ff227db40c7a287a165`.

The baseline build, observer-disabled instrumented build, observer-enabled build, and repeated observer-enabled build produced identical emulated results and final state. Repeated traced JSON was byte-identical. The two consecutive partial degradations also matched baseline exactly (`0xd3d8e033`, then `0x648097e1`), making an observer-induced extra random draw observable and rejecting that neutrality failure mode for this fixture.

## What the experiment disproved

Three tempting shortcuts are unsound even inside this bounded ares model:

1. **Request physical address is not byte origin.** Crossed chip mappings made request `0x000000` read backing `0x200000`, and request `0x200000` read backing `0x000000`.
2. **Returned-value equality does not identify byte origin.** Both request-address backing `0x000004` and true mapped backing `0x200004` contained `0xdeadbeef`; only the completed translated backing transaction identifies the actual source.
3. **Delivered value is not necessarily the backing bytes.** With raw backing `0xffffffff`, CCI produced zero at the low threshold and distinct partially degraded words inside the threshold interval.

Therefore a provenance implementation must not reconstruct this evidence later from current RAM, request address, chip tags, or value equality.

## Independent reference comparison

Pinned Gopher64 revision `e96debac941a26ba4961e5145056c0821d3a56f7`, `src/device/rdram.rs`, models ordinary RDRAM reads as direct masked accesses into `device.rdram.mem` and does not reproduce ares' per-chip remap/CCI-degradation path.

That comparison is useful mainly as a scope guard: this result validates an evidence boundary in the pinned ares model. It is **not** evidence that the detailed ares chip/CCI algorithm is an N64-wide or cross-emulator invariant, and it is not a hardware-accuracy proof for CCI behavior.

## Witness contract recommended for Plaid

For future instrumentation that elects to support this ares non-identity ordinary scalar path, preserve two distinct stages:

1. **Raw byte-origin stage:** request/routing context plus translated backing address, chip, width/requestor, and the bytes/value returned by the actual completed backing read.
2. **Delivered-value stage:** the exact post-backing transformation context and final value delivered to the consumer.

The request address is routing evidence, not origin. The translated backing address/chip plus completed raw read is the raw-byte origin witness. CCI parameters plus delivered value explain why the consumer may observe something else.

If translation fails, or if the path reads another storage domain such as EBus HiddenRAM, this witness class must remain absent rather than guessing.

## Limitations and remaining gap

This result does **not** establish:

- a complete CPU instruction-fetch provenance chain for translated/degraded RDRAM;
- a cache-fill/fetch chronology join;
- all scalar widths or all requestor classes;
- `readBurst`/`writeBurst` translated behavior;
- translated writes;
- EBus HiddenRAM provenance;
- hardware-accurate CCI semantics;
- a cross-emulator N64 invariant;
- TLB, cache, or alias closure by itself.

The direct-component fixture proves the RDRAM transaction boundary and observer neutrality for `Word` reads. A future unified observer still has to join this event to the initiating CPU/cache operation with a stable chronology/ordinal, and Plaid must decide whether degraded executable-byte delivery is representable in the declared executable-image identity or should conservatively remain unsupported. Other widths, burst paths, writes, and HiddenRAM need separate evidence before being generalized.

## Recommendation

**ADOPT** the two-stage fail-closed witness contract for future translated/degraded RDRAM provenance work. Do not transplant the spike verbatim into production and do not weaken existing identity-only proofs by treating request address or delivered-value equality as origin. The primary integrator should reproduce the bounded result, then decide whether translated/degraded executable delivery belongs in the supported closed-world scope or remains an explicit unsupported boundary.

## Primary integration reproduction (2026-10-09)

Retained original fixture from `c88977d`. Local WSL execution reproduces all six
translated reads, including consecutive stochastic values `0xd3d8e033` and
`0x648097e1`, exact raw trace SHA-256
`2b12e5a0f8f382b28186efb52a4bceb31486a96c8716165c87e99489bad93b4d`
and result SHA-256
`faaf34692a4be28700d3a680f8a066f5bddecc6bc3ec7331b2dd14cad7211050`.
Baseline/disabled/enabled reported state and repeated trace agree. Builder
recipe hashes differ because current shared instrumentation has advanced;
original source/result receipts remain identical. The runner preserves prior
ignored output/build caches. Raw backing and delivered transforms remain
separate evidence; full fetch composition and other widths/paths stay open.
