# COP1 stores into CPU-visible SP memory: ares/Gopher sink-width disagreement

Status: **PARTIAL**

Date: 2026-10-09

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Research branch: `research/cop1-sp-sink-gpt56sol`

Exact references:

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`

## Question

What actual storage sink is produced when VR4300 COP1 `SWC1` or `SDC1` targets CPU-visible SP DMEM or IMEM, and in particular does a nominal 64-bit `SDC1` produce one or two SP Word mutations?

This question matters to the executable-mutation census because opcode width is not sufficient evidence for device storage effects.

## Hypothesis

At the pinned ares revision:

- `SWC1` to SP memory produces one completed `RSP::writeWord` sink carrying the FR-sensitive 32-bit FPR payload.
- `SDC1` to SP memory produces only one completed `RSP::writeWord` sink, carrying the high 32 bits of the selected 64-bit FPR payload, because generic `Memory::RCP<T>::write<Dual>` invokes `writeWord(address, data >> 32, thread)` exactly once.
- Successful stores mutate only one concrete four-byte SP storage group.
- CU1-disabled and misaligned stores produce no SP storage sink.

The stronger platform-wide hypothesis, that an N64 `SDC1` to SP memory is intrinsically a four-byte effect, was deliberately left open for independent-reference falsification.

## Baseline source paths

Pinned ares:

- `ares/n64/cpu/interpreter-fpu.cpp`: `SWC1` calls `write<Word>(..., FT(u32))`; `SDC1` calls `write<Dual>(..., FT(u64))`.
- `ares/n64/cpu/memory.cpp`: uncached CPU stores call `bus.write<Size>`.
- `ares/n64/memory/io.hpp`: generic RCP `write<Dual>` contains one `writeWord(address, data >> 32, thread)` call and no `address + 4` write.
- `ares/n64/rsp/io.cpp`: `RSP::writeWord` commits one Word to DMEM or IMEM.

Pinned Gopher64:

- `src/device/cop1.rs`: `sdc1` performs two `device::memory::data_write` calls, at `phys_address` and `phys_address + 4`.
- `src/device/memory.rs`: physical SP memory beginning at `0x04000000` maps writes to `rsp_interface::write_mem`.
- `src/device/rsp_interface.rs`: each `write_mem` call commits one four-byte Word to `rsp.mem`.

## Instrumentation and fixture

`spikes/043-ares-cop1-sp-sink/driver.cpp` reuses the already validated SP Word observer shadow from `spikes/039-ares-cpu-sp-fetch/prepare.py`. The observer fires after the actual `RSP::writeWord` device effect and records address, bank, normalized offset, completed Word payload, and whether the caller thread is the CPU.

The fixture uses uncached CPU aliases:

- DMEM: `0xffffffffa4000000`
- IMEM: `0xffffffffa4001000`

FPR contents are fixed to deterministic values:

- `f0 = 0x1122334455667788`
- `f1 = 0x99aabbccddeeff00`
- `f2 = 0x0123456789abcdef`
- `f3 = 0xfedcba9876543210`

The matrix covers:

- `SWC1` and `SDC1`;
- DMEM and IMEM;
- FR=0 and FR=1;
- `ft=0..3` including even/odd registers;
- successful aligned offsets 0 and 8;
- CU1-disabled failure;
- misalignment failure;
- observer enabled and disabled state-neutrality pairs.

There are 128 semantic scenarios, 256 observer-enabled/disabled observations, and every process invocation is repeated identically, for 512 deterministic fixture launches.

`spikes/043-ares-cop1-sp-sink/crosscheck.py` separately guards the exact pinned ares/Gopher source topology so the disagreement cannot silently disappear behind a reference update.

## Commands

```sh
git checkout research/cop1-sp-sink-gpt56sol

git clone https://github.com/ares-emulator/ares .refs/ares
git -C .refs/ares checkout 9408cb43d4948fc3ea6e152a307a34348df3fe04

git clone https://github.com/gopher64/gopher64 .refs/gopher64
git -C .refs/gopher64 checkout e96debac941a26ba4961e5145056c0821d3a56f7

python3 spikes/043-ares-cop1-sp-sink/crosscheck.py
python3 spikes/043-ares-cop1-sp-sink/run.py
```

The branch workflow `.github/workflows/research-cop1-sp-sink.yml` performs the same exact-pin checkout, source cross-check, ares build, and executable matrix in GitHub Actions.

## Deterministic observations

GitHub Actions run `37915480878`, job `113770490517`, on commit `d8a6e8293b4af62e74a069b5b2cf78703c519aa0` completed successfully.

Exact output:

```text
PASS: exact-pin source disagreement is structurally guarded
crosscheck_sha256=f75384547cea234573b8cd8f628776968bedbaccd80fc1691f449487189fde50
PASS: 256 enabled/disabled exact-pin COP1-to-SP observations; every process repeated
results_sha256=2ba6c3066e6fa484c344125f5725ce5e32bb437a60766ab5273eb082aa248019
```

For every successful pinned-ares case:

1. `SWC1` produced exactly one completed SP Word sink at the requested DMEM/IMEM bank and aligned offset. Its sink payload matched the already validated FR-sensitive `FT(u32)` model from spike 035.
2. `SDC1` also produced exactly one completed SP Word sink. Its sink payload matched the high 32 bits of the already validated FR-sensitive `FT(u64)` model.
3. Only one four-byte storage group changed. The following SP Word and following four raw storage bytes remained unchanged.
4. The other SP bank remained unchanged.
5. Observer-enabled and observer-disabled architectural/storage state matched when observer-only fields were removed.
6. Repeated processes produced byte-identical JSON output.

For every failure case:

- CU1 disabled produced exception code 11 with coprocessor error 1, with no SP sink and no SP storage change.
- Misalignment produced exception code 5, with no SP sink and no SP storage change.

An explicit `SDC1`, FR=1, `ft=1`, DMEM probe recorded one sink with value `0x99aabbcc`; the next SP Word/storage group remained untouched.

## Adversarial verifier corrections

The first executable attempt rejected a naive assumption that direct DMEM Byte helper reads expose guest byte order. The actual first `SWC1` sink was already correct (`0x55667788`), while the helper Byte snapshot exposed host/storage lane ordering. The verifier was changed to retain raw bytes only as concrete footprint evidence rather than treating their presentation order as provenance.

A second attempt rejected a similarly naive assumption that direct helper `write<Word>` / `read<Word>` numeric round-tripping is the correct oracle for the completed device payload. The final verifier therefore separates:

- completed sink payload, taken from the actual post-device-effect observer; and
- concrete storage footprint, established by changed storage groups/raw bytes.

This distinction is intentional: helper readback value presentation is not byte provenance.

## Independent-reference counterexample

Pinned Gopher64 disagrees structurally with pinned ares for `SDC1` to SP memory.

The guarded source result is:

```json
{"ares_rcp_dual_second_word":false,"ares_rcp_dual_writeword_calls":1,"ares_revision":"9408cb43d4948fc3ea6e152a307a34348df3fe04","gopher_revision":"e96debac941a26ba4961e5145056c0821d3a56f7","gopher_rsp_sink_width_bytes":4,"gopher_sdc1_data_write_calls":2,"gopher_sdc1_second_address":true,"gopher_sp_map_to_rsp_write_mem":true}
```

Its SHA-256 is `f75384547cea234573b8cd8f628776968bedbaccd80fc1691f449487189fde50`.

Thus the exact-pinned ares four-byte `SDC1`-to-SP behavior is **validated as an ares implementation behavior**, but it cannot be promoted into an N64-wide invariant. Gopher64's pinned implementation instead models two four-byte effects.

## Result

**PARTIAL**

The narrow ares hypothesis is validated: in the exact pinned ares interpreter, CPU COP1 `SDC1` to SP DMEM/IMEM reaches exactly one completed SP Word sink and one four-byte storage group. `SWC1` behaves as a single Word sink as expected. Failure cases produce no SP sink.

The platform-semantic question remains unresolved because an independent pinned reference disagrees on `SDC1` sink width.

## Implication for Plaid

Plaid must not derive SP mutation width merely from the decoded `SDC1` opcode, and it must not treat pinned ares' one-Word RCP callback behavior as a hardware truth or closure invariant.

For traces produced by this pinned ares revision, the truthful observed mutation event is one SP Word. For a platform-wide mutation census, however, `SDC1`-to-SP semantics require an independent executable or hardware/system-test adjudication before a four-byte or eight-byte rule is adopted.

The safe integration lesson is negative but useful: preserve the concrete sink event emitted by each reference, preserve reference identity, and leave the platform obligation unresolved when references disagree.

## Limitations / what this does not prove

- It does **not** establish real N64 hardware `SDC1`-to-SP semantics.
- Gopher64 was source-cross-checked at its exact pin but was not independently executed with this SP fixture in this session.
- No hardware or `n64-systemtest` ROM specifically adjudicating COP1 `SDC1` into SP DMEM/IMEM was executed.
- The executable ares matrix covers interpreter mode only, not its CPU recompiler.
- The fixture targets uncached CPU-visible SP memory. RDRAM/cache/TLB COP1 storage semantics are separate questions and are covered elsewhere in Plaid research.
- Direct helper readback/endian presentation was deliberately not promoted into provenance and remains out of scope here.
- This experiment does not establish exhaustive executable reachability or whole-ROM mutation completeness.

## Integration recommendation

**INVESTIGATE**

Adopt the negative rule that ares' single-Word `SDC1` SP effect is reference-specific evidence, not a platform invariant. Resolve actual N64 semantics with a minimal hardware/system-test fixture and, ideally, executable differential comparison against at least one independent emulator before using `SDC1` sink width in a closed-world mutation certificate.
