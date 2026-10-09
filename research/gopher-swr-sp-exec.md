# Exact-pinned Gopher64 SWL/SWR stores into SP memory

Status: **VALIDATED** for the exact pinned Gopher64 reference behavior described below.

This note does **not** establish Nintendo 64 hardware truth. It establishes that the source-derived Gopher64 result for the discriminating `SWR` case is what the pinned emulator actually executes, and therefore that the existing Gopher64/ares disagreement is a real executable-reference divergence rather than only a source-reading discrepancy.

## Scope and pins

- Plaid canonical base at claim time: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- retained exact-pinned ares comparison: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- successful Plaid research-branch execution commit: `54fb762535db81247ed33051d4e368685c81098f`
- successful GitHub Actions run: `37918722104`
- successful job: `113781177176`
- uploaded evidence artifact ID: `11610253191`
- uploaded artifact SHA-256: `b19bb516adcd475cc5978633fe9e811ab2f3194389bea3ed1c3f7601924eb606`
- canonical harness-result SHA-256: `ac1c8e7fdd4b79eb78c2599599a6aa31ab08755e7120620e4f03eea3b55d74c5`

The retained ares execution is documented in `research/cpu-sp-partial-word-imem.md`. That work executed the exact pinned ares big-endian `SWL`/`SWR` cases and observed `SWR` offset 2 as `0x22330000`. Its Gopher64 comparison was source-derived only, predicting `0x22334400`. The purpose of this experiment was to execute the missing Gopher64 side.

## Falsifiable hypothesis

At exact pinned Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`, interpreted big-endian `SWR` with RT=`0x11223344` targeting CPU-visible SP memory at offset 2 performs one SP-memory callback whose transaction payload is `0x22334400` and mask is `0xffffff00`. Because the pinned SP sink writes the complete supplied transaction word, both DMEM and IMEM end with aligned word `0x22334400`.

The complete big-endian `SWL`/`SWR` offset matrix should match the source-derived Gopher64 model. If real decoded execution produced `0x22330000`, another value, multiple callbacks, a fault, or observer-dependent state, the source-derived claim would be rejected or narrowed.

## Experiment

`spikes/045-gopher-swr-sp-exec/run.py` is a research-only exact-pin patch injector. It requires a clean Gopher64 checkout at the pinned revision and applies structural guards to the relevant CPU partial-store, opcode-map, memory-map, and RSP-interface source paths before execution.

The injected `cfg(test)` module:

1. constructs Gopher64 `Device::new(false)`;
2. initializes the real memory map, RSP interface, and CPU opcode table;
3. initializes the target SP word to `a0 a1 a2 a3` and its following word to sentinel `a4 a5 a6 a7`;
4. sets RT to `0x11223344` and RS to uncached CPU-visible SP (`0xffffffffa4000000`), with either DMEM bank 0 or IMEM bank `0x1000`;
5. encodes `SWL` (major opcode 42) and `SWR` (major opcode 46) for offsets 0 through 3;
6. resolves each encoded instruction through Gopher64's real CPU decode table and calls the decoded implementation;
7. executes every case once without observation and once with a test-only SP write observer that records `(address, value, mask)` and immediately delegates to the real `rsp_interface::write_mem` sink;
8. requires the entire 8 KiB SP memory image to be byte-identical between unobserved and observed executions, not merely the target word;
9. requires the neighbor sentinel to remain unchanged and exactly one completed SP callback per case; and
10. executes the complete 16-case matrix a second time and requires all extracted evidence records to be identical.

This exercises the actual pinned Gopher64 decoder, partial-store implementation, memory translation/map dispatch, and SP-memory callback. It does not construct a whole ROM or reproduce full CPU cache/timing state.

## Reproduction

From the Plaid research branch:

```sh
git clone https://github.com/gopher64/gopher64.git /tmp/plaid-gopher64-swr-sp
git -C /tmp/plaid-gopher64-swr-sp checkout --detach e96debac941a26ba4961e5145056c0821d3a56f7
git -C /tmp/plaid-gopher64-swr-sp submodule update --init --recursive
test "$(git -C /tmp/plaid-gopher64-swr-sp rev-parse HEAD)" = "e96debac941a26ba4961e5145056c0821d3a56f7"
test -z "$(git -C /tmp/plaid-gopher64-swr-sp status --porcelain)"
GOPHER64_DIR=/tmp/plaid-gopher64-swr-sp python3 -m py_compile spikes/045-gopher-swr-sp-exec/run.py
GOPHER64_DIR=/tmp/plaid-gopher64-swr-sp python3 spikes/045-gopher-swr-sp-exec/run.py
```

The branch-only workflow `.github/workflows/research-gopher-swr-sp-exec.yml` additionally installs the native dependencies required by this Gopher64 pin and uploads the raw execution transcript.

Successful run:

- `https://github.com/sting-raider/Plaid/actions/runs/37918722104`
- artifact: `https://github.com/sting-raider/Plaid/actions/runs/37918722104/artifacts/11610253191`

## Deterministic observations

For every row below, DMEM and IMEM produced the same final aligned word, exactly one SP write callback, and unchanged following bytes `a4a5a6a7`.

| Opcode | Offset | Observed callback mask | Gopher64 DMEM final word | Gopher64 IMEM final word |
| --- | ---: | ---: | ---: | ---: |
| `SWL` | 0 | `ffffffff` | `11223344` | `11223344` |
| `SWL` | 1 | `00ffffff` | `00112233` | `00112233` |
| `SWL` | 2 | `0000ffff` | `00001122` | `00001122` |
| `SWL` | 3 | `000000ff` | `00000011` | `00000011` |
| `SWR` | 0 | `ff000000` | `44000000` | `44000000` |
| `SWR` | 1 | `ffff0000` | `33440000` | `33440000` |
| `SWR` | 2 | `ffffff00` | **`22334400`** | **`22334400`** |
| `SWR` | 3 | `ffffffff` | `11223344` | `11223344` |

The discriminating raw events were:

```text
PLAID_PROBE scenario=swr_dmem_off2 final=22334400 neighbor=a4a5a6a7 writes=1 event=04000000:22334400:ffffff00 neutrality=equal
PLAID_PROBE scenario=swr_imem_off2 final=22334400 neighbor=a4a5a6a7 writes=1 event=04001000:22334400:ffffff00 neutrality=equal
```

The entire matrix was run twice. Both runs produced identical evidence records. The harness then printed:

```text
PASS: exact pinned Gopher64 executed SWL/SWR through the real SP memory map
cases=16/16 repeat=identical observer_neutrality=equal
gopher_swr_big_off2=22334400 ares_swr_big_off2=22330000
RESULT_SHA256=ac1c8e7fdd4b79eb78c2599599a6aa31ab08755e7120620e4f03eea3b55d74c5
```

## Instrumentation-neutrality check

The observer replaced only the SP memory-map write callback. For each observed write it appended the callback tuple and immediately delegated to the exact real SP sink. Each case was also executed without that observer. The harness compared the complete `rsp.mem` image and required equality before accepting the result.

All 16 baseline/observer pairs passed this full-state equality check, and all following-word sentinels remained `a4a5a6a7`.

## Reference differential

The exact pinned references now disagree under executable experiments for big-endian `SWR` offset 2 into SP memory:

- pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`: `0x22330000`
- pinned Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`: `0x22334400`

Therefore the prior Gopher64 source-derived value was not an analysis artifact. The emulator disagreement is behavioral.

This evidence specifically reinforces Plaid's rule that a decoded opcode, caller-side mask, or matching value is not itself a storage-effect proof. Mutation/provenance evidence should retain the completed sink effect and its causal path rather than promoting one reference's partial-store composition into a platform invariant.

## Setup failures preserved during the experiment

Three pre-semantic failures occurred before the successful run:

1. initializing Gopher64 submodules before moving the parent checkout to the pinned revision left a submodule at the wrong gitlink; the clean-tree guard rejected the reference checkout;
2. placing the Gopher64 checkout physically inside Plaid's Cargo workspace caused Cargo to reject the nested package/workspace relationship; the reference checkout was moved to `/tmp` and the runner was parameterized with `GOPHER64_DIR`; and
3. the clean external build reached `ring` but lacked `llvm-ar`; the workflow added the Ubuntu `llvm` package required by the reference build.

No SWL/SWR expected value, callback-count assertion, neutrality assertion, or discriminating-case assertion was changed to obtain the successful semantic result.

## Result

**VALIDATED**, with narrow scope: exact pinned Gopher64 executes the source-derived big-endian SWL/SWR-to-SP matrix, including `SWR` offset 2 → `0x22334400` in both DMEM and IMEM, with one observed SP-memory callback carrying value `0x22334400` and mask `0xffffff00`.

The already executed pinned ares result remains `0x22330000`, so a genuine independent-reference disagreement remains.

## Limitations and what this does not prove

This result does **not** prove:

- Nintendo 64 hardware behavior for the discriminating `SWR` case;
- that either Gopher64 or ares should be promoted to a platform-wide invariant;
- full-ROM instruction/cache/timing behavior, because the fixture invokes the decoded instruction on an initialized emulator device rather than booting a ROM;
- all endian modes or every partial-store family;
- byte provenance for arbitrary CPU/RSP/DMA compositions; or
- that a caller mask alone identifies the concrete SP storage bytes.

The pinned `n64-systemtest` material inspected by the earlier partial-word work does not provide a direct SP-memory `SWL`/`SWR` oracle for this discriminating case. Hardware truth therefore remains unresolved.

## Recommendation

**INVESTIGATE** the platform-semantic disagreement with a hardware-facing or otherwise independent oracle before choosing either result as an N64 invariant. In Plaid itself, retain this as exact-reference oracle evidence and continue modeling mutation history from completed storage effects rather than opcode/mask inference.
