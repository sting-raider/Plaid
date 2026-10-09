# CPU XORI transformed-copy provenance

Result: **VALIDATED**

Worker: `gpt56sol-cpu-xori-transform-20261009`

## 1. Exact revisions

- Plaid canonical baseline: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256` (`main` at claim time).
- Research branch: `research/cpu-xori-transform-gpt56sol`.
- Exact ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- Independent source-level sanity reference only: pinned Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`.

The exact pinned ares decoder maps primary opcode `0x0e` to `XORI(RT, RS, IMMu16)`, and its interpreted implementation is `rt.u64 = rs.u64 ^ imm`. Pinned Gopher64 independently implements `gpr[rt] = gpr[rs] ^ imm as u64`. This agreement is only a source-level sanity check and is not promoted to hardware truth.

## 2. Falsifiable hypothesis

For one tightly bounded interpreted chain,

```text
LW/LWU rt, [src]
XORI   rt, rt, imm16
SW     rt, [dst]
```

ordered instruction begin/end GPR state plus completed uncached identity-RDRAM transactions is sufficient to certify a causal transformed origin

```text
dst_word = source_word XOR zero_extend(imm16)
```

without relying on source/destination payload equality, provided all three instructions are adjacent, in one phase, and the register def-use is exact.

A zero-immediate XORI must remain a distinct transform generation even though it changes no bits. Equal-valued decoys, a XORI that reads a different register, an equal-bit non-XORI clobber, failed loads, or forged histories must not acquire the certificate.

This hypothesis says nothing about arbitrary register dataflow, decompression, relocation, cached paths, or whole-program closure.

## 3. Baseline behavior

The fixture uses the existing exact-ares oracle builder, interpreter-only CPU/RSP configuration, identity RDRAM mapping, and KSEG1 uncached addresses. The observer-free baseline executes the same fixture but does not compile the instruction/scalar callbacks.

Expected word results were:

| Phase | Source operation | Transform | Destination word |
|---|---|---:|---:|
| 1 | `LW` from `0x1000`, value `0x89abcdef` | `XORI 0x00ff` | `0x89abcd10` |
| 2 | `LWU` from `0x1000`, value `0x89abcdef` | `XORI 0xf00f` | `0x89ab3de0` |
| 3 | `LW` from `0x1000`, value `0x12345678` | `XORI 0x0000` | `0x12345678` |
| 4 | equal-valued decoy load from `0x1100`, then real `LW` from `0x1000` | `XORI 0x00ff` | `0x89abcd10` |
| 5 | real `LW t0` from `0x1000`, but XORI reads equal-valued `t1` | `XORI 0x00ff` | `0x89abcd10` |
| 6 | `LW` value `0x00001234` | `ORI t0,zero,0x1234` clobber | `0x00001234` |
| 7 | misaligned `LW` | exception before completed RDRAM read | no sink |

## 4. Instrumentation

`spikes/043-ares-cpu-xori-transform-gpt56sol/observer.hpp` records one total ordinal stream containing:

- interpreted CPU instruction begin/end boundaries;
- exact instruction word and PC;
- all 32 GPRs at each boundary;
- the active instruction context ID;
- completed scalar RDRAM transactions with address, size, direction, value, device and context.

`prepare.py` composes the instruction callback into the generated exact-ares shadow translation unit at guarded prologue/epilogue sites. The shared scalar RDRAM observer is reused unchanged. No field is added to the pinned reference objects and the reference checkout remains clean.

## 5. Fixture construction

The deterministic fixture in `driver.cpp` runs seven phases:

1. positive `LW -> XORI -> SW`;
2. positive `LWU -> XORI -> SW`;
3. zero-immediate XORI, specifically to distinguish same bits from same generation;
4. an equal-valued decoy load into `t1` immediately before the real `t0` load and valid chain;
5. a wrong-source XORI in which `t1` is manually given the same bits as the load result, so a payload/expression matcher can falsely infer provenance from the `t0` read;
6. an ORI overwrite that happens to produce the same stored bits as the earlier load;
7. a misaligned failed load with no completed backing transaction.

The replay verifier only emits a transform certificate for an exact adjacent `load, XORI, store` triple whose register identities satisfy

```text
load.rt == xori.rs == xori.rt == store.rt
```

and whose completed transactions and begin/end GPR effects agree with the decoded operations.

For a certificate it emits the word relation plus four byte relations. Since the N64 word is big-endian in memory, XORI `0x00ff` maps to byte XOR masks `[0x00, 0x00, 0x00, 0xff]`; XORI `0xf00f` maps to `[0x00, 0x00, 0xf0, 0x0f]`.

## 6. Exact commands

The branch workflow performs the following core reproduction:

```sh
mkdir -p .refs
git clone --filter=blob:none https://github.com/ares-emulator/ares.git .refs/ares
git -C .refs/ares checkout 9408cb43d4948fc3ea6e152a307a34348df3fe04
test "$(git -C .refs/ares rev-parse HEAD)" = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
git -C .refs/ares diff --quiet HEAD
python3 -m py_compile \
  spikes/043-ares-cpu-xori-transform-gpt56sol/run.py \
  spikes/043-ares-cpu-xori-transform-gpt56sol/prepare.py
python3 spikes/043-ares-cpu-xori-transform-gpt56sol/run.py
```

First completed exact-pin Actions run: `37918087716`, job `113779079189`.

## 7. Deterministic observations

Run `37918087716` completed successfully on Ubuntu 24.04. The executable experiment printed:

```text
PASS four forged transaction/instruction histories rejected
RESULT_SHA256=763be0ae69e5400a059f3c9dd5f79094592af0ccfda33eb5c50c381c759ddaef
PASS exact interpreted LW/LWU->XORI->SW transformed provenance; zero-transform generation retained and adversarial equal-value chains fail closed
```

The uploaded artifact zip had SHA-256 `fd76f16a401f483b2b74be77df83e09c15ca107513cbaf13db6c27d765367e2e`, artifact ID `11610588095`.

The strict verifier certified exactly phases 1-4, with source `0x1000` for the valid phase-4 chain despite the equal-valued decoy at `0x1100`. It did not certify phases 5-7.

The deliberately naive expression matcher is useful as a counterexample:

- in phase 4 it cannot distinguish the equal-valued `0x1000` and `0x1100` reads by payload expression alone;
- in phase 5 it can match the later stored value to the earlier `0x1000` load after XOR `0x00ff`, even though the actual XORI reads `t1`, not the loaded `t0` generation.

Thus matching transformed values is still not provenance.

## 8. Instrumentation-neutrality checks

The runner compares four executions:

1. observer-free baseline binary;
2. observer-capable binary with callbacks disabled;
3. observer-capable binary with callbacks enabled;
4. a repeated enabled capture.

It requires baseline/disabled/enabled fixture facts and final state to match exactly, and requires the two enabled JSON captures to be byte-for-byte identical. Run `37918087716` passed all checks.

## 9. Adversarial/counterexample cases

The captured history is mutated offline four ways and must fail replay validation:

1. source read address changed from `0x1000` to `0x1100` while retaining the payload;
2. XORI source-register field forged from `t0` to `t1` while retaining observed post-state and sink;
3. SW source-register field forged from `t0` to `t1` while retaining the completed sink;
4. a fabricated successful RDRAM read inserted into the failed misaligned-load context.

All four forged histories were rejected.

The live fixture also contains the equal-valued decoy, wrong-source XORI, ORI clobber and failed-load negatives described above.

## 10. Result

**VALIDATED.**

For this exact interpreted, adjacent, uncached identity-RDRAM pattern, Plaid can represent a one-step XOR-immediate transformation causally. The safe primitive is not "find an earlier value that algebraically explains the sink." It is "retain the exact load generation, mint a new explicit XORI generation from that exact register generation, and require the SW to consume the transform generation."

The zero-immediate case matters: unchanged bits do not mean unchanged provenance identity. The transform node remains causally meaningful even when its output equals its input.

## 11. Limitations

- Only `LW` and `LWU` sources, one `XORI`, and one `SW` sink are covered.
- Only adjacent three-instruction chains are certified; no cross-block, join, loop, call/return, scheduling or arbitrary def-use analysis is attempted.
- Only uncached identity-RDRAM transactions are exercised.
- Cached source residency, cached destinations, eviction/writeback, aliases, TLB translation, partial/64-bit/COP1/conditional stores and exceptions beyond the failed-load negative are outside scope.
- The byte expression is simple because XORI only affects the low 16 register bits. This is not a general byte-lineage algebra.
- The independent Gopher64 inspection is corroboration of instruction semantics only, not a behavioral differential run and not hardware proof.

## 12. What this explicitly does NOT prove

This does not prove transformed-copy completeness, decompression provenance, relocation provenance, executable-mutation completeness, arbitrary CPU dataflow closure, whole-ROM closure, or hardware-wide cache/exception semantics. It does not justify promoting source/destination value matches, even algebraically transformed matches, into provenance.

## 13. Integration recommendation

**ADOPT** the bounded evidence rule and generation model: future provenance data structures should be able to express explicit transformation nodes whose input is a specific prior generation, including identity-valued transformations such as XORI zero. Do not generalize this spike's adjacency recognizer into a general dataflow engine; broader def-use and cached/translated cases require separate evidence.
