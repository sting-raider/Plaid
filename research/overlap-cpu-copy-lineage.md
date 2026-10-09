# Overlapping CPU-copy lineage: dynamic source generations beat snapshot provenance

Date: 2026-10-10

Result: **VALIDATED** for the bounded interpreted uncached word-copy composition described here.

Integration recommendation: **ADOPT** the causal invariant and adversarial model. Do not treat a bulk `(src, dst, len)` copy description, initial source snapshot, or final byte equality as executable provenance when source and destination may overlap.

## Question

The existing exact-pinned ares CPU-copy work established a narrow causal primitive for an adjacent interpreted uncached `LW/LWU rt -> SW rt`: the successful load's backing transaction plus exact instruction/register state can bind the store to that source without guessing from equal values.

This experiment asks the next compositional question:

> If multiple such word-copy steps overlap in memory, can an executable-provenance system attribute the whole destination to the **initial** source span, or must each iteration consume the exact storage generation that was actually read?

The important adversary is `dst > src`. A forward copy can overwrite a later source location before that location is loaded. The copy then legally consumes its own earlier output. A backward copy of the same spans can instead preserve the original source ancestry.

## Exact inputs

Plaid canonical base at claim time:

`211176e7a489fecf8331d02915ee982cd279cb62`

Research branch:

`research/overlap-cpu-copy-lineage-gpt56sol`

Pinned ares revision from `refs.lock.toml`:

`9408cb43d4948fc3ea6e152a307a34348df3fe04`

Composed prior CPU-copy result:

- branch: `research/ares-cpu-copy-dataflow-gpt56sol`
- final research head: `7079fe6d46b6a7ec5a0bc34cf52049e1b5d7385c`
- executable experiment receipt: `c1d57fd0d2e028feaf9fe0a9962ed6f6497091bf`
- GitHub Actions run: `37915748860`
- result: validated narrow adjacent interpreted KSEG1 uncached `LW/LWU rt -> SW rt` causal certificate

The branch-only workflow explicitly fetches and guards those exact inputs before composing them. It does not silently upgrade value equality into provenance.

## Hypothesis

For an overlapping byte-preserving CPU copy, every accepted destination write needs a causal edge from:

1. the exact storage generation successfully read at that iteration's source address;
2. through the exact register/dataflow generation produced by that successful load;
3. to the exact destination storage generation produced by the successful store.

Therefore:

- forward `dst > src` overlap may self-feed an earlier destination generation into a later load;
- backward copy over the same span can preserve the original per-word source generations;
- a same-value backing write still changes the source generation later consumed;
- a same-value register overwrite still changes the store's causal register writer;
- final payload equality cannot reconstruct which history happened;
- deleting/reordering one operation or substituting an equal-valued generation must reject the claimed chain or make it UNKNOWN.

## Actual exact-pinned ares fixture

`spikes/overlap-cpu-copy-lineage/driver.cpp` executes real interpreted VR4300 instructions against the exact pinned ares checkout. CPU and RSP recompilers are disabled; RDRAM uses the controlled identity mapping; data loads/stores use KSEG1 so the tested accesses are uncached.

The fixture unrolls two three-word copies over the same logical overlap:

- source starts at physical `0x1000`;
- destination starts at physical `0x1004`;
- count is 3 words.

### Forward order

The guest executes:

```text
LW t0, 0(s0); SW t0, 0(s1)
LW t0, 4(s0); SW t0, 4(s1)
LW t0, 8(s0); SW t0, 8(s1)
```

With unique initial words `A, B, C, D`, the first store replaces the location that the second load will read, and so on.

### Backward order

The guest executes the same logical copy in reverse word order:

```text
LW t0, 8(s0); SW t0, 8(s1)
LW t0, 4(s0); SW t0, 4(s1)
LW t0, 0(s0); SW t0, 0(s1)
```

This reads each original source word before the overlapping destination can replace it.

The fixture repeats both directions with every source word equal to `0xa5a5a5a5` as a value-equality adversary.

## Actual-reference result

Branch-head workflow run:

- run: `38005696143`
- job: `114073854994`
- tested head: `71a5c44b246bcd2bb52a1d0b0fd77b09b4d8f19e`
- conclusion: **success**
- result artifact: `overlap-cpu-copy-lineage-results`
- artifact id: `11650977445`
- artifact ZIP SHA-256: `09e2f47c45e49c977549c386144ecb92257fbbacccd20b0f02c96cdab8e22c0e`

The exact pinned reference produced:

```text
forward_unique = [0x11111111, 0x11111111, 0x11111111, 0x11111111]
backward_unique = [0x11111111, 0x11111111, 0x22222222, 0x33333333]
forward_equal  = [0xa5a5a5a5, 0xa5a5a5a5, 0xa5a5a5a5, 0xa5a5a5a5]
backward_equal = [0xa5a5a5a5, 0xa5a5a5a5, 0xa5a5a5a5, 0xa5a5a5a5]
```

The run repeated the fixture and required byte-identical stdout. Final reported state included:

- effective Count: `120`
- RDRAM SHA-256: `58cc60780aee680ca56da061797ace944042febc29617038bbca6d485af93efd`
- `actual.json` SHA-256: `cc2cf454b6394ae3f6d6fad4697b35568cd53ac017080e56447d0882f1f38f8c`

The unique-word case directly validates the ordering/self-feed behavior in the exact reference. The all-equal case is the more important provenance adversary: forward and backward executions finish with identical destination bytes even though the causal source histories are different.

This fixture is a behavioral oracle, not a hardware-truth claim by itself.

## Generation-aware replay model

`experiments/overlap_cpu_copy_lineage/model.py` composes the already-validated adjacent-copy primitive into an explicit storage/register generation history.

Each memory cell carries:

- current value;
- storage generation;
- ultimate provenance root;
- causal path.

The reducer requires:

- every load to name the exact current storage generation and value at the source address;
- every successful load to mint a new register generation while preserving that source root;
- every store to name the exact current register generation and value it consumes;
- every successful store to mint a new destination storage generation;
- explicit same-value backing writes and register writes to mint new causal generations despite unchanged bits;
- strictly increasing event ordinals.

It never infers provenance from value equality.

## Deterministic adversarial results

The canonical replay report is:

`a233772b218285ab7f69be3d4b2c6ed7f13cb8c22ba66cb01f730aa2e67e5523`

The branch workflow runs the model twice and requires byte-identical output.

### Unique overlap

For the same `A, B, C, D` source history as the actual fixture:

- forward roots at destination words become `init:0, init:0, init:0`;
- backward roots remain `init:0, init:1, init:2`.

A naive initial-source-snapshot claim is therefore wrong for the later forward writes. Those later loads do not consume `init:1` or `init:2`; they consume storage generations written by earlier iterations.

### Equal-payload history collision

With every word equal to `0xa5a5a5a5`:

- forward and backward final payloads are identical;
- forward destination roots are `init:0, init:0, init:0`;
- backward destination roots are `init:0, init:1, init:2`.

Final bytes are therefore insufficient to recover ancestry, even when the whole destination range is byte-for-byte identical.

### Same-value generation changes

Two additional controls deliberately keep the bits unchanged:

- a same-value external backing write before the later load causes that destination to root in `external:Wsame`;
- a same-value register overwrite between load and store causes that destination to root in `regwrite:Rsame`.

This is exactly why storage generation, register generation and value identity must stay separate.

### Forged histories

The strict reducer rejects all five deliberate corruptions:

1. stale initial source generation substituted after an overlap writer;
2. overlap writer deleted while retaining the later provenance claim;
3. wrong register generation supplied to a store;
4. duplicate/reordered event ordinal;
5. equal-payload backing rewrite replaced with the older equal-valued generation.

## Fuzzing

Fixed seed: `0x504c414944` (`344876730692` decimal).

10,000 generated overlapping histories used counts from 2 to 8 words, random positive overlap shifts smaller than the copy length, and a deliberately small repeated-value alphabet to produce many equal-value histories.

Results:

```text
forward trials:                         4,987
forward initial-snapshot mismatches:    4,987
backward trials:                        5,013
backward initial-snapshot mismatches:       0
equal-payload, same-final/different-root controls: 104
```

The test intentionally attacks the hypothesis: if a forward overlapping history ever preserved the naive per-word initial snapshot relation under this geometry, or a backward one failed it without an injected writer, the asserted rule would be falsified.

## What this closes

For this bounded composition, **VALIDATED**:

A byte-preserving CPU copy cannot be summarized for provenance as only `(initial source span, destination span, length, final bytes)` when overlap is possible. Direction and chronology are semantically relevant, and the correct causal unit is the successful read generation -> register/dataflow generation -> successful write generation chain.

This matters directly to executable discovery. A copied instruction word may come from an earlier destination write rather than the initial source byte occupying the corresponding logical offset. If Plaid later treats that instruction as executable, collapsing the overlap history to an initial snapshot can fabricate the wrong executable ancestry while all final bytes still look plausible.

## Minimum evidence contract

A future reusable CPU-copy certificate should retain, for every copied storage unit it certifies:

1. source physical/backing identity and exact storage generation at the successful read;
2. operation/instruction identity for that successful read;
3. the register/dataflow generation produced or selected by the read;
4. any intervening register writers that can replace that generation, including same-value writers;
5. operation/instruction identity for the successful write;
6. exact register generation consumed by the write;
7. destination physical/backing identity and newly minted storage generation;
8. total ordering sufficient to decide whether prior destination writes become later source generations.

A bulk copy may only be safely compressed to one initial-source snapshot relation after an independent proof establishes non-overlap or a direction/order rule that guarantees every source read precedes all overlapping destination writes that could replace it.

## What remains open

This result does **not** prove general CPU-copy closure. In particular it does not establish:

- loop/control-flow reconstruction or induction over arbitrary guest copy loops;
- non-adjacent GPR def-use beyond the existing adjacent-copy primitive;
- interrupts, exceptions, restart/replay or delay-slot behavior between load and store;
- cached KSEG0 source/destination lineage or D-cache writeback composition;
- TLB-mapped aliases, remaps or context generations;
- byte/halfword/doubleword/unaligned/merge load-store families;
- multi-register/vectorized copy implementations;
- decompression, relocation or other value-transforming ancestry;
- executable lifetime, I-cache residency, retirement or later executable-fetch consumption;
- completeness of all CPU copy implementations in an arbitrary ROM;
- independent hardware confirmation of the exact reference behavior.

Whole-ROM closure and native completeness therefore remain unchanged and OPEN.

## Reproduction

Run the deterministic model:

```sh
python3 experiments/overlap_cpu_copy_lineage/model.py
```

Expected final lines include:

```text
REPORT_SHA256=a233772b218285ab7f69be3d4b2c6ed7f13cb8c22ba66cb01f730aa2e67e5523
PASS overlap copy requires per-read storage generation and per-store register generation; equal final payload does not recover ancestry
```

With `.refs/ares` checked out exactly at the pinned revision:

```sh
python3 spikes/overlap-cpu-copy-lineage/run.py
```

Expected final lines include:

```text
ACTUAL_SHA256=cc2cf454b6394ae3f6d6fad4697b35568cd53ac017080e56447d0882f1f38f8c
PASS exact pinned ares executes forward overlap as self-feeding and backward overlap as preserving source words
```

The branch-only workflow `.github/workflows/research-overlap-cpu-copy-lineage.yml` guards the exact prior composition receipt and exact ares pin, repeats the deterministic model, executes the actual-reference fixture, and uploads the result logs.

## Integration recommendation

**ADOPT** the invariant, not a high-level `memcpy` fiction.

When production provenance learns CPU-copy chains, represent them as generation-bearing causal edges or an equivalent auditable DAG. Do not collapse an overlapping copy to initial source offsets merely because the final bytes match. Keep same-value writes and same-value register definitions as distinct generations. Only coalesce many scalar edges after proving an overlap-safe ordering invariant.

No production Plaid source was changed by this research branch; the workflow, model, exact-reference fixture and this note are research scaffolding for the primary integrator to reproduce and selectively adopt.
