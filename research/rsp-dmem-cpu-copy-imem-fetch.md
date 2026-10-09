# RSP DMEM -> CPU copy -> IMEM -> RSP fetch provenance composition

Date: 2026-10-10

Status: **VALIDATED (bounded composition proof)**

Worker: `gpt56sol-rsp-dmem-cpu-copy-imem-fetch-20261010`

Claim: issue #4 comment `6090420656`.

Canonical base inspected before work: `211176e7a489fecf8331d02915ee982cd279cb62`.

Research branch: `research/rsp-dmem-cpu-copy-imem-fetch-gpt56sol`.

## Question

Three Plaid research lanes had already established useful pieces independently:

1. decoded RSP DMEM stores can be represented as ordered byte-level writer generations, including same-value and partial/vector writes;
2. an interpreted CPU `LW` -> preserved GPR definition -> `SW` chain can certify an actual SP DMEM -> IMEM Word copy without using value equality as source identity;
3. completed IMEM writes can create resident generations whose latest bytes explain later RSP interpreter fetches.

The missing composition question was whether those contracts preserve **ultimate executable-byte provenance** when a mixed-origin DMEM Word crosses the CPU-copy seam. The bounded CPU-copy certificate records a source-read ordinal, destination-write ordinal and Word payload, but not the source read's per-byte writer ancestry.

## Exact inputs

The experiment source-guards these exact prior artifacts before running:

- `research/rsp-dmem-cpu-refetch-gpt56sol` commit `cda3b458dc1ac77c639a1afc02a05daac642e861`
  - `research/rsp-dmem-cpu-refetch-lineage.md` Git blob `212a7e10812e24406df4c68409216ae9b1c826f7`
  - `spikes/043-ares-rsp-dmem-cpu-refetch/run.py` Git blob `a0cff6263697ead0abfbf3bbaddcc45b1f783b4e`
  - recorded result SHA-256 `3bdbf149b3b382fb9fb38c8381a0fee32d4e1045f804f12bebb2ba1066091957`
- `research/cpu-sp-dmem-imem-copy-gpt56sol` commit `5c13859e536bf42fcfae9e56b9104f5ff6292590`
  - `research/cpu-sp-dmem-imem-copy.md` Git blob `d894a31d3110c76217415a2956533c17b65315ab`
  - `spikes/043-cpu-sp-dmem-imem-copy-gpt56sol/run.py` Git blob `f7fdad02b938c973a6c3b23b161d7e2c6f5022fb`
  - recorded result SHA-256 `45f3126878657b9c084572a7e943a024ca05dad6c5c47a3cfa1e0cc7ab18a39c`
- canonical `research/rsp-imem-provenance.md` at `211176e7a489fecf8331d02915ee982cd279cb62`, Git blob `5a04b1f147899db6f865b99495d6ad84c122d0cd`.
- `refs.lock.toml` pins ares exactly at `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

This branch does **not** claim a new ares or hardware behavior. It composes previously validated exact-pin contracts and actively attacks the join between them.

## Executable model

`experiments/rsp-dmem-cpu-copy-imem-fetch/model.py` replays one ordered 26-event history. It keeps separate state for:

- DMEM byte value;
- DMEM byte writer identity;
- CPU GPR definition identity and optional memory ancestry;
- IMEM byte value;
- IMEM resident storage generation;
- IMEM ultimate byte ancestry;
- RSP fetched payload and the resident/origin vectors visible at that fetch.

The useful positive path is:

1. a completed CPU Word write seeds DMEM;
2. decoded scalar/vector RSP byte writes replace only DMEM bytes 3 and 2;
3. a second scalar RSP write rewrites byte 3 with the **same value**, creating a new writer generation;
4. CPU `LW t0` reads the resulting mixed-origin Word `0x34087722`;
5. an equal-valued decoy `LW t1` from another DMEM Word occurs afterward;
6. CPU `SW t0` writes the Word into IMEM;
7. RSP fetches the IMEM Word;
8. an unidentified same-value IMEM byte mutation replaces byte 3;
9. RSP fetches the numerically unchanged Word again;
10. a later same-value RSP DMEM rewrite refreshes byte 2;
11. CPU reloads `t0`, then a same-value arithmetic GPR rewrite severs the memory ancestry before an IMEM store;
12. another real reload and store restores a certifiable copy chain.

## Result

**VALIDATED** for this bounded composition model.

The first certified CPU Word copy creates one IMEM resident generation across all four destination bytes, while preserving this upstream origin vector:

```text
cpu-dmem:cpu-seed-A:1
cpu-dmem:cpu-seed-A:1
rsp:5:084:6
rsp:8:088:9
```

Thus one storage generation and one Word payload do **not** imply one ultimate source identity. The destination Word contains three distinct upstream writer identities.

The later same-value IMEM byte mutation leaves the fetched Word equal to `0x34087722` but changes the final byte's state to:

```text
resident generation: foreign-imem:15
ultimate origin:     unknown-imem:15
```

The other three bytes preserve their prior ancestry. Before/after payload equality therefore cannot preserve or resurrect the old copy provenance.

A same-value RSP rewrite of DMEM byte 2 later creates a distinct newer RSP writer generation. A same-value GPR arithmetic rewrite after a valid `LW` makes the subsequent IMEM store content-valid but provenance-uncertified; the model writes UNKNOWN upstream ancestry rather than pretending the earlier read survived the register definition change.

## Whole-Word projection collision

The strongest counterexample is not a malformed history. Two valid histories differ only in the producer identity that supplied the first two source bytes, while all bytes and CPU copy events remain numerically equal.

They have identical projected bounded Word-copy facts:

- source read ordinal;
- destination write ordinal;
- destination address;
- Word value;
- `certified=true`.

They also have the same RSP fetch payload and the same IMEM resident generation. Yet their strict per-byte upstream ancestry differs for bytes 0 and 1.

Therefore the current bounded Word-copy projection is sufficient to say **this Word copy happened**, but is not sufficient by itself to answer **which upstream writer generations ultimately produced every executable byte**.

This is an information-loss counterexample, not merely a recommendation for nicer metadata.

## Adversarial cases

Strict replay rejected all ten deliberate forgeries:

1. flatten the mixed four-byte source vector to one `word-read:<ordinal>` identity;
2. swap byte-2 and byte-3 ancestry;
3. reuse the stale earlier same-value RSP writer for byte 3;
4. substitute the equal-valued decoy `t1` read as the copy source;
5. ignore the same-value GPR clobber and claim the earlier `LW` still defines `t0`;
6. erase the same-value post-copy IMEM mutation from the later fetch history;
7. replace the source `LW` with a same-value register constant and repair provenance from payload equality;
8. relabel a scoped RSP sink as a foreign same-value mutation;
9. duplicate a chronology ordinal;
10. move a same-value RSP refresh to the wrong byte.

The model also constructs two valid histories that deliberately collide under the flat Word-copy projection while retaining different byte ancestry. That falsifies any proposal to reconstruct the missing ancestry later from `(read ordinal, write ordinal, value)` alone.

## Reproduction and receipts

Files:

- `experiments/rsp-dmem-cpu-copy-imem-fetch/model.py`
- `experiments/rsp-dmem-cpu-copy-imem-fetch/source_guard.py`
- `experiments/rsp-dmem-cpu-copy-imem-fetch/README.md`
- `.github/workflows/research-rsp-dmem-cpu-copy-imem-fetch.yml`

Run:

```bash
python3 experiments/rsp-dmem-cpu-copy-imem-fetch/source_guard.py
python3 experiments/rsp-dmem-cpu-copy-imem-fetch/model.py
```

Clean exact-input CI checkpoint:

- branch head: `88f7df1fb03df2c721f2d28c5f0dbea88b6d18ab`
- Actions run: `38000656357`
- job: `114057636848`
- runner: Ubuntu 24.04.5, image `20261004.327.1`
- result SHA-256: `af306594330d7ec3124bb9030e8ba1f0407573a11a3c24f4dd971dbd57b6de4c`
- artifact ID: `11648946472`
- uploaded artifact ZIP SHA-256: `b2a722db32e5788062a0b59f05e31eba3e70037ce1bbe9ed5bed8af5a9e74632`

The workflow passed exact prior commit/blob guards, `refs.lock.toml` ares-pin verification, Python compilation, the adversarial composition model, `git diff --check`, and artifact upload.

## What prior research was composed

This result composes, rather than supersedes:

- RSP DMEM latest-writer research, which established per-byte writer generations and same-value mutation sensitivity;
- CPU SP DMEM -> IMEM copy research, which established instruction/register/storage causality and equal-value/clobber rejection for a Word copy;
- RSP IMEM provenance research, which established distinct resident generations and later fetch resolution.

The important new invariant is that the copy edge must carry **two different kinds of identity**:

1. the destination IMEM storage generation created by the completed sink;
2. the corresponding source-byte ancestry vector inherited from the exact source read/GPR dataflow chain.

Collapsing either into the other loses information.

## Closed-world impact

For ultimate RSP executable provenance, a future production copy/transform certificate cannot stop at a whole-object event identity or content digest when the source span can contain mixed writer generations. It must preserve byte/range ancestry, or an equivalently lossless interval representation, through the transform.

This matters directly to closed-world proof composition: if an RSP executable image is installed through a CPU copy, Plaid must be able to defend both the resident executable generation and where each covered byte came from. A flat Word-copy fact can be true while still being insufficient for that stronger proof obligation.

The correct failure mode for missing ancestry is UNKNOWN/OPEN. Equal bytes, equal hashes, equal addresses, equal read/write values, or one common destination generation must not manufacture upstream provenance.

## Remaining gap

This result intentionally does **not** prove:

- a complete RSP or CPU mutation census;
- byte/half/unaligned/64-bit CPU copy forms;
- general control-flow dataflow, joins, loops, calls, exceptions or interrupts around the copy;
- CPU D-cache effects or cached source/destination copies;
- SP DMA in this composed path;
- RSP IMEM hardware atomicity;
- task/microcode start and retirement boundaries;
- save/restore/reset/debugger mutation handling;
- exhaustive RSP execution roots or indirect targets;
- whole-ROM closure or native completeness.

The model also uses one Word sink for the CPU copy because that is the scope of the validated source contract. It does not infer hardware atomicity from the model.

## Integration recommendation

**ADOPT the composition invariant, not this research model as production architecture.**

When production provenance models copies/transforms, the certificate should retain a lossless mapping from destination byte/range generations back to the exact source byte/range writer generations established at the source read. A destination storage generation is separate from upstream origin. Same-value writes and same-value GPR definitions remain new generations/definitions. Unidentified mutations cut lineage to UNKNOWN.

The existing bounded CPU Word-copy certificate should remain usable as evidence that the copy occurred, but it must not be promoted into an ultimate executable-byte-origin certificate unless the source ancestry is attached or recoverable from an independently immutable, exact chronology record.

No changes were merged into `main`.
