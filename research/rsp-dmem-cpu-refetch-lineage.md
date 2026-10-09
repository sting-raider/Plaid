# RSP DMEM -> CPU SP refetch byte lineage

Status: **VALIDATED**

Worker: `gpt56sol-rsp-dmem-cpu-refetch-20261009`

Lease: GitHub issue #4 claim comment `6078553395`, started `2026-10-09T09:50:17Z`.

## Question

Can measured decoded RSP DMEM storage effects be causally composed with later actual uncached CPU SP instruction-fetch reads while preserving byte-level writer generations across same-value RSP stores, partial/vector stores, CPU overwrite boundaries, and unknown out-of-context mutations, without using matching PC/value as origin proof?

## Revisions

- Plaid canonical base inspected before the experiment: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256` (`main`).
- Passing research-code commit: `86b51ec21707a28dff4a630946569bbeecb0b7ec`.
- Exact pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- Durable spike: `spikes/043-ares-rsp-dmem-cpu-refetch/`.

## Hypothesis

Within the controlled pinned-ares interpreter scope, a later uncached CPU fetch from SP DMEM can inherit byte origins only from the latest ordered measured storage effects covering its four backing bytes. Same-value writes must advance writer identity. Partial stores must replace only touched bytes. An intervening identified CPU SP write must replace affected byte lineage. A DMEM sink outside a decoded RSP instruction context must not be promoted to RSP origin and must remain unknown unless another measured higher-level event identifies it.

## Baseline and instrumentation

The spike composes two already validated source-shadow sensors:

- `spikes/039-ares-cpu-sp-fetch`: completed SP word reads/writes and CPU instruction-fetch boundaries;
- `spikes/042-ares-rsp-dmem-history`: scoped decoded RSP instruction contexts and primitive DMEM sinks.

The shared event stream uses one monotonically increasing ordinal. The observer does not perform guest reads, clock steps, serialization, or introduce reference-object provenance fields.

The experiment builds:

1. an original baseline without the composition sensor;
2. the instrumented build with callbacks disabled;
3. the instrumented build with callbacks enabled;
4. a repeated enabled run.

The explicit fixture state (`initial_bytes`, final DMEM words, CPU `t0`) is equal across baseline/disabled/enabled/repeat. The sensor build's machine digest is equal across disabled/enabled/repeat, and the two enabled traces are byte-identical. This is a scoped instrumentation-neutrality check, not proof that every emulator state bit is covered by the digest.

## Fixture

Initial DMEM word 0 is `0x340800aa`; word 4 is `0x34081111`. CPU fetches use the uncached SP aperture. The fixture then performs:

1. initial CPU fetch of word 0;
2. decoded RSP `SW` of `0x34081111` to word 0;
3. CPU refetch;
4. same-value decoded RSP `SW` to word 0;
5. CPU refetch;
6. same-value CPU `SW` to word 0 through the SP aperture;
7. CPU refetch;
8. equal-valued decoded RSP `SW` to neighboring word 4;
9. CPU refetch of word 0;
10. decoded scalar RSP `SB` writing byte 3 (`0x22`);
11. CPU refetch;
12. decoded vector RSP `SBV` writing byte 2 (`0x77`);
13. CPU refetch;
14. direct out-of-instruction-context same-value DMEM byte write to byte 3;
15. CPU refetch with unchanged payload;
16. decoded same-value RSP `SB` to byte 3;
17. final CPU refetch.

Final word 0 is `0x34087722`; word 4 remains `0x34081111`; CPU `t0` is `0x7722`.

## Falsified intermediate assumption: RSP `SW` is not one sink

The first exact runs rejected the verifier's assumption that one decoded RSP `SW` produces one low-level storage event. At the pinned ares revision, RSP `SW` calls `dmem.writeUnaligned<Word>`, which decomposes the store into primitive byte writes. The actual sensor therefore reports four ordered Byte sinks for each `SW`.

That finding changes the correct provenance abstraction: writer generations are attached to measured primitive storage effects, not decoded opcode names. The final verifier expects 15 scoped RSP primitive sinks across the fixture:

- four byte sinks for phase 2 `SW`;
- four for phase 4 same-value `SW`;
- four for phase 8 neighboring `SW`;
- one scalar `SB` sink;
- one vector `SBV` sink;
- one final same-value scalar `SB` sink.

## CPU-write and foreign-sink boundary

A CPU SP word write reaches the shared low-level RSP DMEM storage object, so the primitive DMEM callback fires even though no decoded RSP instruction context is active. Treating every DMEM callback as an RSP producer would therefore be wrong.

The final sensor marks such events `foreign_sink`. For the controlled CPU `SW`, the replay requires the foreign low-level Word sink to precede and match the later completed CPU `sp_write`, after which the CPU `sp_write` becomes the writer identity for all four bytes. The deliberately unscoped same-value byte write in phase 14 has no such higher-level identification, so it cuts byte 3 lineage to `unknown:<ordinal>` even though the byte value does not change.

## Deterministic observations

Passing exact-pin run `37915637117`, job `113771004974`, on research commit `86b51ec21707a28dff4a630946569bbeecb0b7ec` produced:

- `baseline_equal: true`;
- `repeat_equal: true`;
- primitive scoped RSP sink count: `15`;
- CPU write ordinal: `33`;
- foreign/unknown sink ordinals: `32`, `68`;
- result SHA-256: `3bdbf149b3b382fb9fb38c8381a0fee32d4e1045f804f12bebb2ba1066091957`;
- artifact ID: `11609228305`.

Observed byte-writer vectors at CPU fetches:

- phase 1: `initial, initial, initial, initial`;
- phase 3: four distinct primitive phase-2 RSP `SW` byte generations;
- phase 5: four distinct new primitive phase-4 RSP `SW` byte generations despite identical payload;
- phase 7: one completed CPU writer across all four bytes;
- phase 9: same CPU writer vector, proving the equal-valued neighboring RSP store did not steal origin;
- phase 11: `CPU, CPU, CPU, scalar-RSP-SB`;
- phase 13: `CPU, CPU, vector-RSP-SBV, scalar-RSP-SB`;
- phase 15: `CPU, CPU, vector-RSP-SBV, UNKNOWN` after the same-value foreign byte sink;
- phase 17: `CPU, CPU, vector-RSP-SBV, new-same-value-RSP-SB`.

The exact observed labels for the final four split cases were:

```text
phase 11: cpu:33, cpu:33, cpu:33, rsp:50:51
phase 13: cpu:33, cpu:33, rsp:59:60, rsp:50:51
phase 15: cpu:33, cpu:33, rsp:59:60, unknown:68
phase 17: cpu:33, cpu:33, rsp:59:60, rsp:73:74
```

## Adversarial verification

The generation-aware replay rejected all ten forged histories:

1. delete one same-value RSP byte generation;
2. move an equal-valued neighboring RSP sink onto a fetched byte;
3. erase an RSP instruction context from a sink;
4. falsify CPU writer identity;
5. break foreign-sink / completed-CPU-write pairing;
6. move the scalar partial RSP sink to the wrong byte;
7. move the vector partial RSP sink to the wrong byte;
8. move the same-value foreign/unknown sink off the fetched byte;
9. forge a CPU backing-read value;
10. duplicate an event ordinal.

A deliberately weaker value-only predicate incorrectly accepted three provenance forgeries because payload bytes remained plausible:

- deleted same-value RSP byte generation;
- equal-valued neighboring RSP sink stealing a fetched byte;
- same-value foreign sink moved away from the fetched byte.

This is direct evidence that matching values are insufficient for causal byte provenance.

## Reproduction

With the exact ares revision checked out at `.refs/ares`:

```sh
python3 spikes/043-ares-rsp-dmem-cpu-refetch/run.py
```

The research workflow also executes this exact-pin command in GitHub Actions and retains `results.json` plus diagnostic output.

## Result

**VALIDATED** for this bounded controlled reference scope.

The useful integration rule is:

- model executable-byte history from ordered measured storage effects at byte granularity;
- preserve new writer generations even for same-value writes;
- let partial stores replace only touched bytes;
- only attach decoded RSP producer identity while an actual scoped RSP instruction context is active;
- allow a later independently measured writer event, such as the completed CPU SP write, to replace byte identity when its join is verified;
- otherwise degrade an unmatched/out-of-context mutation to unknown rather than inferring origin from value or address coincidence.

## Limitations / explicitly not proved

This experiment does not prove:

- a complete N64 mutation census;
- that ares primitive write decomposition is N64 hardware atomicity;
- producer dataflow behind the values held in RSP registers;
- all scalar/vector RSP store encodings, alignments, or wrap cases in this composition fixture;
- SP DMA provenance or RSP DMEM -> IMEM transfer provenance;
- cached CPU copy/decompression/relocation provenance;
- executable lifetime start/end or instruction-cache behavior;
- interrupt, exception, TLB, alias, save/restore, or reset completeness;
- whole-ROM reachability or closed-world proof.

The result is a validated causal composition contract for these measured effects, not a platform-wide closure certificate.

## Recommendation

**ADOPT** the byte-level ordered writer-generation composition rule and fail-closed treatment of unidentified DMEM sinks as bounded provenance evidence. The primary integrator should review how to represent this contract in production data structures; the research instrumentation itself is not proposed as a wholesale production merge.
