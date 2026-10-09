# CPU partial-word stores into RSP IMEM

Status: **PARTIAL**

Integration recommendation: **ADOPT** the storage-sink normalization requirement described below. Do **not** adopt the exact pinned-ares `SWR` offset-2 payload as an N64-wide invariant until a hardware-facing oracle resolves the reference disagreement.

## Question

When a VR4300 `SWL` or `SWR` targets RSP IMEM, may Plaid reuse the ordinary RDRAM partial-store byte mask, or does the SP-memory device path turn the instruction's internal subwrites into ordered full 32-bit IMEM mutations?

This is a provenance/mutation-completeness question. It is not enough to recognize an `SWL`/`SWR` opcode and infer its nominal architectural byte lanes if the eventual storage sink has different write-width behavior.

## Exact revisions

- Plaid base commit: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- research branch: `research/cpu-sp-partial-word-gpt56sol`
- branch checkpoint before this note: `7ee2955e691c2e7270edbe23f52777c1d5f53682`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

The exact upstream revisions are those pinned by `refs.lock.toml` at the Plaid base commit.

## Hypothesis

The previously validated RDRAM `SWL`/`SWR` byte masks cannot be reused for SP IMEM. In pinned ares, an architectural partial store decomposes into one or more `Byte`/`Half`/`Word` writes. The RCP SP-memory adapter widens each such write to an aligned full-word operation before RSP IMEM storage. Therefore two subwrites from one instruction can overwrite one another, and the final executable word can differ from ordinary RDRAM partial-store semantics.

The falsifier was straightforward: if exact pinned ares preserved only the nominal partial lanes at the final IMEM sink, or if the hardware-facing pinned oracle established different behavior, the hypothesis would be rejected or narrowed.

## Baseline

Two prior Plaid results matter:

1. `research/ares-swl-swr-executable-mutations.md` characterizes `SWL`/`SWR` into ordinary RDRAM, where the surviving changed byte lanes match ordinary partial-store behavior. That result explicitly does not establish MMIO/device sink behavior.
2. `research/cpu-rsp-imem-subword.md` establishes that CPU `SB`/`SH` reaching SP memory can replace the complete aligned 32-bit SP-memory word, with unwritten lanes becoming zero in the tested references/hardware-facing evidence.

The missing composition was `SWL`/`SWR`: the pinned ares implementation may issue multiple typed writes for one instruction, and each typed write subsequently encounters the full-word SP-memory sink.

## Experiment

Durable fixture: `spikes/043-ares-cpu-sp-partial-word/`.

Files:

- `model.py`: direct source transcription of pinned ares `SWL`/`SWR` decomposition, little-endian address reversal, and RCP `Byte`/`Half`/`Word` widening into a full-word SP sink.
- `driver.cpp`: unpatched pinned-ares headless fixture. It disables the CPU and RSP recompilers, initializes sixteen IMEM bytes to `a0..af`, calls the real CPU `SWL`/`SWR` semantic methods, and lets the normal CPU address/memory/bus/RCP/RSP path perform the store.
- `run.py`: builds the exact pinned ares tree, guards the relevant source files by SHA-256, executes each case twice, compares exact execution with the source-derived model, and emits a deterministic result artifact.
- `compare_refs.py`: source-derived comparison against exact pinned Gopher64 plus a guard/search of exact pinned n64-systemtest for a hardware-facing SP-memory `SWL`/`SWR` oracle.
- `.github/workflows/research-cpu-sp-partial-word.yml`: exact-pin branch-only reproducer.

No emulator instrumentation patch is involved. The tested ares tree is the exact pin. The fixture calls the instruction semantic methods directly rather than feeding encoded instructions through the decoder, so the decoder itself is outside this experiment; the memory/device path is not bypassed.

### Reproduction

With `.refs/ares`, `.refs/gopher64`, and `.refs/n64-systemtest` checked out at the revisions above:

```sh
python3 spikes/043-ares-cpu-sp-partial-word/model.py
python3 spikes/043-ares-cpu-sp-partial-word/compare_refs.py
python3 spikes/043-ares-cpu-sp-partial-word/run.py
```

The canonical executed reproduction for this research is GitHub Actions run `37915972499` on source commit `b82bddc98633d2ca7f94f2b38505c27bbd9cb3cb`. The workflow completed successfully. Exact-results artifact ID: `11608789005`.

An earlier run, `37915344830`, failed before building/running ares because Python 3.12 `dataclasses` rejected a dynamically imported model module that had not been inserted into `sys.modules`. The standalone model had already passed. Commit `208e2b0daeecb62321ce8936dab6685d632064c9` fixed that harness-only defect; no semantic assertion was weakened.

## Exact ares observations

Input register value: `0x11223344`.

Each listed word below is the final aligned IMEM word after one store. Each exact case was executed twice and required byte-for-byte identical output.

| Endian | Instruction | guest offset class | final aligned IMEM word |
| --- | --- | ---: | ---: |
| big | SWL | 0 | `11223344` |
| big | SWL | 1 | `00112233` |
| big | SWL | 2 | `00001122` |
| big | SWL | 3 | `00000011` |
| big | SWR | 0 | `44000000` |
| big | SWR | 1 | `33440000` |
| big | SWR | 2 | `22330000` |
| big | SWR | 3 | `11223344` |
| little | SWL | 0 | `00000011` on the endian-reversed aligned physical word |
| little | SWL | 1 | `00001122` on the endian-reversed aligned physical word |
| little | SWL | 2 | `00112233` on the endian-reversed aligned physical word |
| little | SWL | 3 | `11223344` on the endian-reversed aligned physical word |
| little | SWR | 0 | `11223344` on the endian-reversed aligned physical word |
| little | SWR | 1 | `22334400` on the endian-reversed aligned physical word |
| little | SWR | 2 | `33440000` on the endian-reversed aligned physical word |
| little | SWR | 3 | `44000000` on the endian-reversed aligned physical word |

The 0..3 matrix was repeated on a second aligned guest word (offsets 4..7), for 32 single-instruction cases total.

Exact run summary:

```text
PASS: 40 repeated exact-pinned-ares SWL/SWR/SP-IMEM cases
single_full_word_sink_cases=32/32
two_subwrite_same_word_cases=8/8
pair_collateral_cases=6/8
results_sha256=855189757dcbe990e12e6cbf9fe5abe73bd20528fffd55c44afa8ef3c124c335
```

All 32 single-store cases replaced exactly one complete aligned four-byte IMEM word. The eight source paths that decompose one instruction into two writes were confirmed by the model to have both subwrites target the same aligned storage word with distinct full-word sink values. Final-state execution matched the ordered model in all cases.

The strongest counterexample is big-endian `SWR` at offset 2 in pinned ares. The CPU semantic method performs an ordered byte subwrite and halfword subwrite. Both are widened by the RCP adapter into full-word SP-memory writes. The later widened halfword effect replaces the earlier widened byte effect, leaving `0x22330000`, not the ordinary partial-store image one would infer from the opcode alone.

A conventional aligned `SWL`/`SWR` pair was also tested for four offsets in each endian mode. Six of eight pair cases modified more than the intended four-byte guest span because the component operations replaced complete SP words. Only the naturally aligned pair in each endian mode avoided collateral changed bytes.

### Source guards for exact ares run

```text
interpreter-ipu.cpp  495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152
cpu/memory.cpp       55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74
memory/io.hpp        54089251052dbffddf7ae77819c3a3bb494cf7269ae874a3015a23907370a69c
rsp/io.cpp           60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860
msb/writable.hpp     29d6d71b9b92e095f34bd1809c5d3f8afb74cb16857e1f597854165d70d9df06
```

## Independent reference comparison

Pinned Gopher64 independently models the same important device-side hazard: its SP-memory writer ignores the incoming write mask and commits a complete 32-bit word. Its CPU `SWL`/`SWR` implementation, however, represents each instruction as one masked word transaction rather than the same typed subwrite sequence used by pinned ares.

For big-endian `0x11223344`, the source-derived final SP word agrees in seven of eight offset/instruction cases and disagrees in exactly one:

| case | pinned ares | pinned Gopher64 |
| --- | ---: | ---: |
| SWL off0 | `11223344` | `11223344` |
| SWL off1 | `00112233` | `00112233` |
| SWL off2 | `00001122` | `00001122` |
| SWL off3 | `00000011` | `00000011` |
| SWR off0 | `44000000` | `44000000` |
| SWR off1 | `33440000` | `33440000` |
| **SWR off2** | **`22330000`** | **`22334400`** |
| SWR off3 | `11223344` | `11223344` |

The comparison is deterministic and source-guarded:

```text
PASS: pinned source comparison isolates one exact payload disagreement
mismatch=SWR/big/off2 ares=22330000 gopher=22334400
systemtest_spmem_swl_swr_oracle=absent
gopher_cpu_sha256=f2136f77815ecacbfe3c6a748b9070d295a2cb77561a850495806e623a6ed4c5
gopher_rsp_sha256=a5864c02f742bc922284d7866bbe76fe80efda63d3a3c69af7e37c50fe661053
systemtest_spmem_sha256=9096a6eefc7a8a248642ca782e25be67f51d9620d81cf2a7322e9fd5254af074
```

This Gopher64 comparison is source-derived; Gopher64 was not compiled and executed in this fixture.

Pinned n64-systemtest contains hardware-facing SP-memory coverage for the general `SB`/`SH` full-word overwrite quirk, but the pinned SP-memory test file contains no `SWL` or `SWR` case. Therefore it cannot decide the `SWR off2` disagreement.

## Result

**PARTIAL.**

The experiment validates, for exact pinned ares, that `SWL`/`SWR` targeting SP IMEM must not be interpreted using only ordinary RDRAM byte-lane semantics. It also independently confirms from pinned Gopher64 source that the SP-memory sink discards normal write-mask preservation and can produce a complete-word mutation.

However, exact platform payload semantics are not closed: ares and Gopher64 disagree for big-endian `SWR` offset 2, and the pinned hardware-facing systemtest has no oracle for that instruction/path. One emulator's answer must not become an N64-wide invariant merely because its fixture is executable and green.

## Implication for Plaid

**ADOPT this invariant at the provenance/mutation layer:** mutation evidence must be normalized at the actual completed storage sink, with ordered causal subeffects preserved. Do not synthesize executable-byte mutation solely from the originating opcode's nominal width/mask.

For this class specifically:

- an `SWL`/`SWR` observation is not itself a final byte-lane mutation witness;
- one architectural instruction may generate multiple storage effects;
- a quirky device aperture may widen each effect to a complete aligned word;
- later subeffects from the same instruction may replace bytes written by earlier subeffects;
- coalescing by PC/address/value without ordered sink identity can destroy causal history;
- ordinary RDRAM masks must not be blindly transferred to SP DMEM/IMEM;
- exact SP payload semantics should remain reference-qualified until hardware resolves disagreements.

This conclusion is useful even though the exact `SWR off2` payload is unresolved: Plaid's safe model must represent the device/storage effect rather than assume nominal opcode masks.

## Limitations and explicit non-claims

This result does **not** prove:

- that pinned ares's exact `SWR off2 = 0x22330000` result matches N64 hardware;
- a platform-wide `SWL`/`SWR` SP-memory invariant;
- decoder correctness, because the ares fixture directly calls the instruction semantic methods;
- TLB/cached-path behavior, because the fixture uses the direct uncached SP aperture;
- exact intermediate sink chronology via independent instrumentation. Chronology is transcribed from exact pinned source and checked against final-state execution, not separately logged at every internal bus callback;
- little-endian cross-emulator consensus. Little-endian execution was validated only against pinned ares in this experiment;
- `SDL`/`SDR`, COP1 stores, cache writeback, DMA, or RSP-originated stores;
- arbitrary title behavior or exhaustive reachability.

## Next falsifier

The highest-value follow-up is a tiny hardware-facing n64-systemtest fixture that writes `SWL`/`SWR` across all four SP-memory offset classes, with big-endian `SWR` offset 2 as the discriminating case. Expected competing values are `0x22330000` from the pinned-ares ordered typed-subwrite model and `0x22334400` from the pinned-Gopher single masked-word model. The test should cover both DMEM and IMEM if hardware access permits and must report the observed complete aligned word rather than infer behavior from opcode semantics.
