# CPU-mediated SP DMEM -> IMEM copy provenance

Status: **VALIDATED** for the bounded Word-copy experiment below.

Worker: `gpt56sol-cpu-sp-dmem-imem-copy-20261009`

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Branch: `research/cpu-sp-dmem-imem-copy-gpt56sol`

Exact-pin Actions run: <https://github.com/sting-raider/Plaid/actions/runs/37915831346>

## Question

Can a CPU-mediated copy from SP DMEM to executable SP IMEM be certified from
actual completed SP storage effects plus interpreted VR4300 register dataflow,
without treating equal payloads, CPU-thread identity, or final contents as
provenance?

The bounded hypothesis was:

> A Word copy is certifiable only when an actual CPU SP DMEM `readWord` is
> synchronously explained by an interpreted `LW` into register R, no later
> executed instruction writes R before the candidate store, and an interpreted
> `SW` from R synchronously causes the actual completed IMEM `writeWord` sink.
> Equal-value reads/writes, a different last writer, a non-IMEM destination, or a
> CPU-thread SP write outside an executing store instruction must not satisfy the
> certificate.

## Pinned source path

At the pinned ares revision:

- `ares/n64/cpu/interpreter-ipu.cpp` implements `LW` by calling the existing
  CPU `read<Word>` path and assigning the returned Word to the target GPR only
  on a successful read.
- The same file implements `SW` by passing the source GPR's low Word to the
  existing CPU `write<Word>` path.
- `ares/n64/rsp/io.cpp` selects DMEM versus IMEM from SP address bit 12 in
  `RSP::readWord`/`RSP::writeWord`; IMEM writes also perform the existing RSP
  recompiler invalidation before the memory sink.

The experiment shadows only the RSP header and `io.cpp` in the generated
reference build. Its callback observes the existing completed read value or
runs after the existing write effect. It does not add guest accesses, clock
steps, CPU/RSP object fields, or a second translation.

Exact source receipts from the successful run:

| Source | SHA-256 |
|---|---|
| `ares/n64/rsp/io.cpp` | `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860` |
| `ares/n64/cpu/interpreter-ipu.cpp` | `495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152` |
| `ares/n64/rsp/rsp.hpp` | `03d72d15b7cf3cf1c50615996be2dd1918b08e9af61098c599e16871e1adbe00` |

Compiler recorded by the build manifest:
`g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`.

## Fixture

`spikes/043-cpu-sp-dmem-imem-copy-gpt56sol/` executes real interpreted VR4300
instructions with both ares recompilers disabled. The CPU uses the uncached
KSEG1 SP aperture with `s0 = 0xffffffffa4000000`.

DMEM offsets `0x000` and `0x004` deliberately contain the same Word
`0x34081234`. Selected IMEM words start with a sentinel.

The phases are designed to attack value-only attribution:

1. `LW t0,0(s0)` reads DMEM `0x000`.
2. `SW t0,0x1000(s0)` writes IMEM `0x000`.
3. `LW t0,0(s0)` reloads the source.
4. `LW t1,4(s0)` reads the **same value** from a decoy DMEM address into a
   different register.
5. `SW t0,0x1004(s0)` must still derive from phase 3, not phase 4.
6. `LW t0,0(s0)` reloads the source.
7. `ORI t0,zero,0x5678` clobbers the source register.
8. `SW t0,0x1008(s0)` is a real IMEM sink but not a DMEM copy.
9. `LW t0,0(s0)` reloads the source.
10. `ADDU t0,t2,zero` rewrites `t0` with the **same value** as DMEM.
11. `SW t0,0x100c(s0)` must not be called a DMEM copy merely because the
    payload matches.
12. A direct `rsp.writeWord(..., cpu)` writes IMEM `0x020` outside an executing
    CPU instruction. This has CPU thread identity but no producer instruction.
13. `SW t0,0x20(s0)` is a real CPU SP sink to DMEM, not executable IMEM.
14. `LW t0,0(s0)` reloads the source.
15. `SW t0,0x1000(s0)` rewrites IMEM `0x000` with its current value. It must be
    a new copy/storage generation despite value equality.

The replay verifier decodes only the fixture's `LW`, `SW`, `ORI`, and `ADDU`
forms. It checks recorded architectural register effects, reconstructs the
bounded direct-KSEG1 SP address, validates the actual bank/offset sink, finds
the most recent executed writer of the `SW` source GPR, and certifies only an
`LW` whose completed SP read is the synchronous source effect.

## Reproduction

From the Plaid root with the pinned ares checkout clean at `.refs/ares`:

```bash
python3 spikes/043-cpu-sp-dmem-imem-copy-gpt56sol/run.py
```

The branch-only workflow used the same command after fetching the exact
reference SHA:

```bash
git -C .refs/ares fetch --depth=1 origin 9408cb43d4948fc3ea6e152a307a34348df3fe04
git -C .refs/ares checkout --detach FETCH_HEAD
python3 spikes/043-cpu-sp-dmem-imem-copy-gpt56sol/run.py
```

Generated receipts remain under ignored
`target/ares-cpu-sp-dmem-imem-copy-spike/`.

## Deterministic observations

The completed SP event stream was:

| Ordinal | Phase | Effect | Bank | Offset | Value |
|---:|---:|---|---:|---:|---:|
| 1 | 1 | read | DMEM | `0x000` | `0x34081234` |
| 2 | 2 | write | IMEM | `0x000` | `0x34081234` |
| 3 | 3 | read | DMEM | `0x000` | `0x34081234` |
| 4 | 4 | read | DMEM | `0x004` | `0x34081234` |
| 5 | 5 | write | IMEM | `0x004` | `0x34081234` |
| 6 | 6 | read | DMEM | `0x000` | `0x34081234` |
| 7 | 8 | write | IMEM | `0x008` | `0x00005678` |
| 8 | 9 | read | DMEM | `0x000` | `0x34081234` |
| 9 | 11 | write | IMEM | `0x00c` | `0x34081234` |
| 10 | 12 | write | IMEM | `0x020` | `0x34081234` |
| 11 | 13 | write | DMEM | `0x020` | `0x34081234` |
| 12 | 14 | read | DMEM | `0x000` | `0x34081234` |
| 13 | 15 | write | IMEM | `0x000` | `0x34081234` |

The verifier emitted exactly three copy certificates:

| Load phase / read ordinal | Store phase / write ordinal | Source | Destination | Value |
|---|---|---|---|---|
| 1 / 1 | 2 / 2 | DMEM `0x000`, `t0` | IMEM `0x000` | `0x34081234` |
| 3 / 3 | 5 / 5 | DMEM `0x000`, `t0` | IMEM `0x004` | `0x34081234` |
| 14 / 12 | 15 / 13 | DMEM `0x000`, `t0` | IMEM `0x000` | `0x34081234` |

Phase 4's equal-valued DMEM read did not replace phase 3 as the source because it
wrote `t1`, not `t0`. Phase 15 created a distinct certificate/storage generation
from phase 2 although destination and payload were equal.

The verifier explicitly rejected:

- phase 8: the last `t0` writer was `ORI`, not `LW`;
- phase 11: the last `t0` writer was same-value `ADDU`, not `LW`;
- phase 13: the actual sink was DMEM, not IMEM;
- phase 12: the actual IMEM sink occurred outside any recorded executed
  instruction, despite `originCpu=true`.

## Instrumentation neutrality and repeatability

The runner built and compared four executions:

1. unmodified-reference baseline;
2. callback-capable binary with observer disabled;
3. callback-capable binary with observer enabled;
4. a second enabled run.

The successful run asserted:

- complete recorded state equality across all four modes;
- exact executed-step ledger equality across all four modes;
- no observer events in baseline or observer-disabled mode;
- byte-identical event streams across the two enabled runs.

Selected final state hashes:

| State | SHA-256 |
|---|---|
| RDRAM | `b4360541bd7bc4afda97c91c8e4c356a1e5210682ab506775d58c6ddaa178b7c` |
| RDRAM hidden | `686fcb3ce03ef5c289091f2bc1031102b5778ea02ab2894f58fa198d49fb92ca` |
| SP DMEM | `cf330ee8d00a248aab752e9ccdc90577b76e01377ec1afcc8d291627a2ca22c4` |
| SP IMEM | `81ab7b398cdcdecd585cd5ea4464ed395bbc9f7ce086a0bd3444472e895b8782` |

Run receipts:

- event stream:
  `77dc1576e86dae9d718015ef27c7af4fdf159dff3689ecc4a8e7db18329c4176`
- certificate set:
  `96d68b5abb7b9745c9bde1527cbf2b467e0f73ba688be4f36b87af899e329798`
- complete `results.json`:
  `45f3126878657b9c084572a7e943a024ca05dad6c5c47a3cfa1e0cc7ab18a39c`
- Actions artifact:
  `sha256:87eeb85809cd4e743368eafaea64acdbf5b61326eb3e4c66f040f5a5afd58708`

## Adversarial replay

Eight mutated histories were required to fail:

1. move the phase-3 causal read onto equal-value decoy phase 4;
2. rewrite phase 4's instruction as `LW t0` without the matching recorded
   register effects;
3. rewrite phase 10's same-value `ADDU` as a source `LW`;
4. forge phase 11's IMEM sink bank;
5. hide the phase-12 out-of-instruction sink inside phase 11;
6. duplicate a storage ordinal;
7. alter phase 14's completed source-read value while keeping the recorded load
   result unchanged;
8. move the phase-15 same-value rewrite sink.

All eight were rejected in the exact-pin run.

## Result

**VALIDATED** for this bounded interpreter/Word/direct-KSEG1 scope.

The experiment demonstrates that CPU-mediated SP DMEM -> SP IMEM copy provenance
can be represented as a causal chain of:

`completed DMEM read effect -> executed LW register definition -> preserved GPR
definition -> executed SW use -> completed IMEM write effect`.

The equal-value adversaries matter. Value equality is useful as a consistency
check only after the causal chain is established; it is not sufficient to pick
the source generation. Likewise, `&thread == &cpu` on an SP sink identifies the
calling thread but does not identify an executing producer instruction.

## Limitations / explicitly not proved

This result does **not** prove:

- ultimate origin of the bytes already resident in DMEM;
- RSP scalar/vector-store -> CPU-load composition;
- byte, halfword, unaligned (`LWL/LWR/SWL/SWR`), 64-bit, conditional, or COP1
  CPU-copy forms;
- cached source/destination behavior, D-cache residency/writeback, or stale
  I-cache behavior;
- TLB mappings, KSEG aliases other than this direct KSEG1 fixture, exceptions,
  interrupts, calls, joins, loops, or general cross-block dataflow;
- SP DMA / reverse-DMA provenance or RSP executable installation lifetime;
- that an IMEM write is later executed by RSP;
- mutation completeness, executable-lifetime closure, whole-ROM closure, or
  native-complete status;
- hardware truth beyond the exact pinned ares behavior measured here.

No closure/native flags should change from this experiment alone.

## Integration recommendation

**ADOPT** the causal shape, not the fixture-specific decoder.

For future provenance composition, retain explicit read/sink generations and
instruction/register dataflow identity. A CPU-thread SP sink without an
instruction context remains unattributed. Same-value reads and rewrites must
remain distinct generations.

The branch-local workflow is only a reproducibility host and need not be merged
into canonical production. The standalone spike and this note are the durable
evidence.
