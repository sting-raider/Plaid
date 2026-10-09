# CPU `SC` -> SP DMEM/IMEM storage effects in pinned ares

Status: **VALIDATED** for the bounded exact-pin interpreter experiment below.

Recommendation: **ADOPT** the sink-level mutation rule and keep LL/SC platform semantics as a separate oracle obligation.

## Question

When an interpreted VR4300 `SC` targets CPU-visible SP DMEM or IMEM, can Plaid distinguish a real conditional-store mutation from a failed reservation or fault by observing the completed SP storage sink, including a successful same-value store that leaves the bytes unchanged?

This experiment is deliberately Word-only. `SCD`, SDL/SDR, COP1 stores, DMA, RSP-origin writes, and hardware-wide LL/SC semantics are outside this lane.

## Revisions and durable artifacts

- Canonical Plaid baseline at claim time: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256` (`main`).
- Research branch: `research/cpu-sc-sp-sink-gpt56sol`.
- Executable-evidence head: `98bb4b9c252d2d52bd611ae2d58863bbafc8c033`.
- Exact pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- Exact pinned Gopher64 source comparison: `e96debac941a26ba4961e5145056c0821d3a56f7`.
- Spike: `spikes/045-ares-cpu-sc-sp-sink/`.
- Branch-only workflow: `.github/workflows/research-cpu-sc-sp-sink.yml`.
- Successful evidence run: GitHub Actions `37918954587`, job `113781949316`.
- Retained artifact: `cpu-sc-sp-sink-results`, artifact ID `11611168723`, ZIP SHA-256 `ad2e641522ae71c6ae99adede2b303568aa6548967183372f6493724cb081057`.
- Deterministic trace SHA-256: `311ece0fd647d9c4bfc6cb1e5a9558c938bf3ef5d51810ae4ca752a81a9b5bcb`.
- Deterministic result JSON SHA-256: `454ea55a300bee86480f55d6152cdd2970495e60121eb0b93e3d8a8ff0f4e6d2`.

## Hypothesis

For this controlled interpreter fixture:

1. `SC` with no live linked-load reservation produces no SP storage sink and returns failure;
2. an aligned `SC` after a real `LL` to the SP target completes one CPU-origin SP Word sink in the selected DMEM/IMEM bank;
3. a successful same-value `SC` remains a fresh writer generation despite `before == after`;
4. a misaligned `SC` after a real `LL` faults before any SP sink;
5. an equal-address/equal-value CPU write outside decoded `SC` execution must not inherit `SC` provenance merely because its payload matches.

The hypothesis is about completed storage effects in exact pinned ares, not about N64-wide reservation lifetime semantics.

## Exact source behavior guarded by the runner

At the pinned ares revision, interpreted `LL` performs a normal Word read and, after success, records `scc.ll = access.paddr >> 4` and sets `scc.llbit = 1`. Interpreted `SC` gates the write on `scc.llbit`; when set it assigns the boolean result of `write<Word>(...)` into `rt`, otherwise it writes zero to `rt`.

The CPU memory path performs alignment/translation before the write. An invalid/misaligned access returns `false`; a successful uncached KSEG1 SP access reaches the bus. The RCP adapter's Word write invokes exactly one device `writeWord`. `RSP::writeWord` then chooses DMEM or IMEM by address bit `0x1000`; the IMEM case also invalidates the RSP recompiler address before writing the Word.

The independent pinned Gopher64 source also gates `SC` on `llbit`, translates a write address, and issues a full-mask `data_write` on the successful path. It explicitly clears `llbit` before that write. This is useful corroboration that conditional success and the eventual sink are distinct concerns, but it also demonstrates why reservation-state details must not be promoted from one emulator into a platform invariant. Gopher64 was not executed in this experiment.

Source SHA-256 guards from the successful run:

- ares `interpreter-ipu.cpp`: `495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152`
- ares RCP `io.hpp`: `54089251052dbffddf7ae77819c3a3bb494cf7269ae874a3015a23907370a69c`
- ares RSP `io.cpp`: `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860`
- Gopher64 `cpu_instructions.rs`: `f2136f77815ecacbfe3c6a748b9070d295a2cb77561a850495806e623a6ed4c5`

## Fixture and instrumentation

Both CPU and RSP recompilers are disabled. Guest instructions execute through the pinned ares interpreter. Code is placed at physical `0x6000` and fetched through uncached KSEG1 `0xffffffffa0006000`.

The two SP targets are:

- DMEM: `0xffffffffa4000000`
- IMEM: `0xffffffffa4001000`

Each target begins with Word `0x11223344`. Four cases are executed per bank:

1. `SC` with `llbit = 0` and no preceding linked load;
2. aligned `LL`, then misaligned `SC +1`;
3. aligned `LL`, `XORI rt,rt,0x00ff`, then aligned `SC`, producing `0x112233bb`;
4. aligned `LL`, then aligned `SC` without changing the loaded value, producing a successful same-value write of `0x11223344`.

After the eight decoded cases, the fixture performs an equal-valued direct CPU Word write to IMEM outside decoded-instruction context. That write is intentionally adversarial: address and payload equality are not sufficient to call it an `SC` writer.

The project-owned SP observer is installed only at the already-completed CPU-origin `RSP::writeWord` boundary exposed by the existing research builder. It does not perform an extra guest access. The baseline executable is built without this sensor; the instrumented executable is run twice with it enabled.

## Reproduction

With exact pins checked out under `.refs/ares` and `.refs/gopher64`:

```sh
python3 -m py_compile spikes/045-ares-cpu-sc-sp-sink/*.py
python3 spikes/045-ares-cpu-sc-sp-sink/run.py
```

Expected terminal summary from the validated run:

```text
{"events": 5, "failed_sc_without_sink": 2, "faulting_sc_without_sink": 2, "forged_histories_rejected": ["drop_same_value_success", "fabricate_failed_sink", "steal_equal_value_decoy", "erase_sc_opcode", "erase_reservation_context"], "neutrality": true, "out_of_context_equal_value_decoys": 1, "repeat_deterministic": true, "same_value_successes_missed_by_diff": 2, "successful_sc_sinks": 4}
TRACE_SHA256=311ece0fd647d9c4bfc6cb1e5a9558c938bf3ef5d51810ae4ca752a81a9b5bcb
RESULT_SHA256=454ea55a300bee86480f55d6152cdd2970495e60121eb0b93e3d8a8ff0f4e6d2
PASS: successful SC reaches one measured SP Word sink; failed/faulting SC does not, and same-value success remains a writer generation
```

## Deterministic observations

The enabled trace contains five completed CPU-origin SP Word sinks total:

- one changed-value successful `SC` to DMEM;
- one same-value successful `SC` to DMEM;
- one changed-value successful `SC` to IMEM;
- one same-value successful `SC` to IMEM;
- one equal-valued direct CPU IMEM write outside decoded `SC` context.

There is no sink for either no-reservation `SC`, and no sink for either misaligned `SC`. The two no-reservation cases return `rt = 0` without an exception. The two misaligned cases report AddressStore exception code `5`, leave the original SP Word intact, and likewise produce no SP write event.

All four aligned post-`LL` conditional stores return `rt = 1` and have exactly one completed Word sink in the expected bank at offset zero. Changed-value cases commit `0x112233bb`. Same-value cases commit `0x11223344`, so initial and final bytes are equal even though a real storage operation occurred.

That yields a concrete counterexample to a value-diff mutation census: **two successful conditional-store writer generations are invisible if mutation is defined as `before != after`.** It also yields a counterexample to value/address provenance matching: the final out-of-context direct CPU write has the same IMEM address and `0x11223344` payload as the successful same-value IMEM `SC`, but has no decoded `SC` execution context and must remain a different writer kind.

## Neutrality and repeatability

The runner compares an uninstrumented baseline executable against the instrumented executable. All eight architectural case facts and the direct-write success fact are identical. Two enabled instrumented executions are required to produce byte-identical stdout; the validated run passed and produced trace SHA-256 `311ece0fd647d9c4bfc6cb1e5a9558c938bf3ef5d51810ae4ca752a81a9b5bcb`.

The observer therefore did not change the bounded architectural outcomes being tested.

## Adversarial replay

The fail-closed verifier mutates the captured history and requires rejection of five forged variants:

1. remove a successful same-value `SC` sink;
2. fabricate a sink for a failed-reservation `SC`;
3. relabel the equal-valued out-of-context direct write so it steals `SC` attribution;
4. replace the recorded `SC` opcode context with ordinary `SW`;
5. erase the live-reservation context on a successful sink.

All five were rejected in Actions run `37918954587`.

## Result

**VALIDATED**, within this fixture's declared scope.

For CPU-visible SP Word mutations, the useful evidence boundary is the completed device sink joined to the actual decoded conditional-store execution context. An `SC` opcode is only an attempt. `rt = 1` is a semantic outcome but is not, by itself, byte-origin evidence. Conversely, unchanged destination bytes do not mean no writer occurred: a successful same-value `SC` must advance the storage-generation history.

A mutation census should therefore mint an `SC`-origin writer generation only when a completed SP sink is causally joined to the corresponding successful decoded `SC`. Failed/faulting attempts mint no SP storage generation. Equal payloads from another CPU write must remain distinct unless causal context proves identity.

## Limitations and explicit non-proofs

This result does **not** prove:

- hardware-accurate N64 LL/SC reservation creation, invalidation, address matching, or lifetime;
- that pinned ares' `llbit` behavior is correct when interrupts, exceptions, `ERET`, context changes, DMA, or other writes intervene;
- `SCD` or any 64-bit conditional SP effect;
- SDL/SDR, byte/halfword partial-store widening, COP1 stores, or other mutation opcodes;
- TLB-mapped or reverse-endian aliases to SP memory;
- RSP-origin or DMA-origin SP mutations;
- hardware timing/atomicity or queue behavior;
- executable lifetime, instruction-cache visibility, RSP execution identity, or fetch provenance after an IMEM mutation;
- reachability or whole-ROM executable closure;
- behavioral agreement with Gopher64, since Gopher64 was inspected only at the exact pinned source revision;
- physical hardware truth from emulator behavior.

The validated statement is intentionally narrower: **in this exact pinned ares interpreter scope, successful aligned Word `SC` operations to CPU-visible DMEM/IMEM produce one completed SP Word sink, failed/faulting attempts do not, and same-value successful stores are real writer generations that byte-diff accounting misses.**
