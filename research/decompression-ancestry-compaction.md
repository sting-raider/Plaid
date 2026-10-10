# Lossless compaction of decompression ancestry receipts

Status: **VALIDATED (bounded evidence-representation model)**

Date: 2026-10-10

Canonical Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/decompression-ancestry-compaction-gpt56sol`

Coordination claim: issue #4 comment `6096716331`

## Question

`research/decompression-lineage-receipt.md` established that dictionary/LZ-style executable decompression cannot be authenticated by an input hash, output hash, decompressor identity, or even by output write values/locations alone. Literal reads must retain the exact storage generation consumed, overlapping backreferences may read generations created moments earlier by the same transform, successful same-value writes mint new generations, and source/output aliasing requires exact read-before-clobber chronology.

That result deliberately left scalability open: can Plaid retain those distinctions without one persistent provenance record per output byte?

This experiment asks a narrower question:

> Given a separately verified transform operation stream, can the byte-granular causal receipt be replaced by a compact operation/DAG receipt and later expanded/rechecked to exactly the same byte ancestry, including self-feeding overlap, in-place aliasing and same-value generations?

It also attempts to falsify the stronger initial hypothesis that an overlapping backreference must be split whenever it begins reading generations produced inside that same backreference.

## Scope and non-claims

This is a provenance-representation experiment, not a decompressor recognizer and not an N64 hardware-timing experiment.

The operation IR is intentionally the same causal core used by the prior bounded decompression-receipt model:

- `literal(source_offset)` emits one byte from the current source cell;
- `backref(distance, length)` performs a **sequential** dictionary copy from already-emitted output, so `length > distance` is self-feeding.

A future format-specific recognizer still has to prove that a particular MIO0/Yay0/Yaz0/game-specific or bespoke guest decompressor performed the claimed operations. This work begins only after those operation semantics are independently established.

No pinned emulator behavior is promoted to hardware truth here. `refs.lock.toml` at the canonical base was inspected; no reference implementation was executed because the uncertainty is representation equivalence, not CPU/RSP/device semantics.

No production Plaid file was changed.

## Prior work composed

This experiment composes:

- `research/decompression-lineage-receipt.md`: exact source/output generations and ordered transform ancestry are required;
- prior CPU copy/dataflow and XORI work: value compatibility does not identify a causal parent, and identity-valued transforms still create generations;
- same-value writer-generation work: successful equal-payload writes remain distinct history;
- ADR-0009: deletion/fabrication of proof inputs must fail closed;
- `research/history-scalability.md`: chronology volume and retained identity cardinality are separate scaling concerns.

It is intentionally separate from the active ProgramMap merge-scaling lane and from decompressor recognition.

## Compact receipt

The executable experiment is:

- `experiments/decompression_ancestry_compaction.py`

A compact receipt retains the transform header and one canonical node per recognized transform operation. Each node contains:

- operation index;
- first output sequence number;
- output length;
- first destination address;
- operation kind and exact arguments;
- `causal_sha256`, a commitment over the canonical expanded write stream for that operation.

The committed causal stream is not a value hash. Each expanded write includes:

```text
(seq,
 destination,
 value,
 exact_source_address,
 exact_source_generation,
 fresh_write_generation)
```

The transform ID is part of fresh output-generation construction (`O:<transform>:<seq>`), so byte-identical redecompression is still a new causal generation.

The input/output value hashes remain useful integrity fields, but they are not accepted as provenance substitutes.

## Independent verifier

`stream_verify_and_expand()` does not trust the node digest or output values. Starting from generation-bearing memory plus the independently supplied operation stream, it:

1. checks the operation-stream digest and canonical node shape;
2. replays operations in order;
3. resolves every source address from operation semantics;
4. reads the exact source generation currently resident at that address;
5. creates the required fresh output generation;
6. recomputes the node causal commitment;
7. updates memory before the next byte, including bytes later consumed by a self-feeding backreference;
8. checks the final output value digest.

Expansion can be streamed rather than retained. The equivalence tests collect the expanded writes only to compare them byte-for-byte with the prior explicit receipt.

## Falsified part of the initial hypothesis

The initial claim predicted that an overlapping backreference might need to be split at every causal-generation boundary.

That is **not necessary** for this operation model.

A single node `(distance, length, sequential-copy semantics)` is sufficient even when `length > distance`. During replay, byte `n` is written before byte `n+1` resolves its source; therefore later bytes naturally read the newly-created output generations. The node can commit to the resulting expanded ancestry without listing or splitting every intermediate generation persistently.

The important requirement is not a physical split. It is **unambiguous sequential semantics plus independent causal replay**. A generic flat range edge without those semantics would still be unsound.

## Positive semantic equivalence

Hosted workflow run `38046586892`, job `114197241092`, at code-tested head `75206c7cef33b9c9cb1f02796e574420af2850da` succeeded.

The deterministic corpus used seed `88288443057219` and covered:

- 5,000 valid random transforms;
- 675,151 byte-level writes;
- 47,068 compact nodes;
- all 5,000 programs containing an overlapping backreference;
- 19,665 overlapping backreference operations retained as **unsplit** compact nodes;
- 556 source/output-overlap programs.

Every compact receipt independently expanded to exactly the byte-granular causal write sequence.

Stable semantic digest:

`d5fffb1bd106f35f4431458bdad89740c729d111b56408111c1037402a497b1a`

Experiment SHA-256 on the hosted runner:

`e5e41d6c222c30ac042cf75f1a857994460fed9af10e0336328ae5272b10397f`

The workflow executes the semantic corpus twice; both executions produced the same semantic digest.

Artifact:

- ID `11667835598`
- ZIP SHA-256 `942e073b7d8c334af227c93b4409bfd174e83f5998cdebbe6a5d2f4e4b4c5c90`

## Adversarial compact-receipt attacks

The same hosted semantic run generated 2,000 forgeries on each of nine axes, 18,000 forged receipts total.

Strict causal replay rejected **18,000 / 18,000**.

The intentionally weak value/shape verifier accepted every case on the six ancestry-only axes below, because their final operation shapes and values remain compatible:

1. same-value input storage-generation swap;
2. causal-digest deletion/erasure;
3. equal-value backreference-parent digest substitution;
4. transform-generation reuse;
5. same-value redecompression digest reuse;
6. impossible/future-parent causal digest forgery.

That is 12,000 / 12,000 ancestry-only false accepts by the weak control.

The weak verifier did reject node deletion, reordering and widening because those three corrupt visible operation shape. Strict replay rejected those structural attacks too.

The result therefore does not derive provenance from SHA-256 or value equality. Exact ancestry is rederived first; a node digest merely commits the compact artifact to that independently reconstructed causal stream.

## Direct compact construction

The second executable artifact is:

- `experiments/decompression_ancestry_compaction_bench.py`

It builds the compact receipt directly while executing the recognized operation stream. It never materializes the byte-write receipt. A separate equivalence corpus compares that direct builder against the byte-history compactor and then expands the direct receipt through the independent verifier.

Hosted benchmark workflow run `38046586945`, job `114197241151`, succeeded at the same code head.

Deterministic direct-builder equivalence corpus:

- 2,000 programs;
- 275,903 byte writes;
- 18,703 compact nodes;
- 7,951 unsplit overlapping backreference nodes;
- 223 in-place source/output cases;
- direct receipt == byte-history-derived compact receipt for every case;
- independent expansion == byte-granular write sequence for every case.

Stable equivalence digest:

`a14624c47caedec6b27c5e0d1576009ab3b1581b8cd5c28c4f81fbebe6889a80`

Direct benchmark script SHA-256:

`6b2fb045b6c3ac16e2508e8dd52a3cfd6557b91ad521a8a86368bdb50a72835c`

Artifact:

- ID `11667995491`
- ZIP SHA-256 `84a1d578a60cf05841035a64bf562cc9b68eb1bb591013dc5140063fad7928f0`

Two hosted executions reproduced the same equivalence digest.

## Scalability measurements

The direct-builder workflow runs byte and compact construction in separate child processes so peak RSS does not inherit the other representation. Timings are runner measurements, not platform guarantees; the compact timing below includes independent verification while the byte timing is only construction, so they are intentionally not presented as an apples-to-apples speed win.

### Highly compressible self-feeding history

Workload: one literal followed by one distance-1 sequential backreference.

Hosted first run:

| Output writes | Byte receipt JSON | Compact JSON | Compact nodes | Compact/byte | Byte peak RSS | Compact peak RSS |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 147,017 B | 720 B | 2 | 0.004897 | 20,404 KB | 19,860 KB |
| 10,000 | 1,517,016 B | 723 B | 2 | 0.000477 | 29,496 KB | 23,716 KB |
| 100,000 | 15,699,782 B | 726 B | 2 | 0.000046 | 125,724 KB | 72,160 KB |

The second hosted run reproduced the exact encoded sizes and ratios. At 100,000 writes it measured 125,712 KB versus 72,228 KB peak RSS.

Thus retained receipt size scales with **recognized operation count** for this case, not with output-byte count. The 100k compact artifact is about 21.6k times smaller by encoded JSON size.

The compact path still performs O(output bytes) replay. In the first hosted run, byte construction took 137.848 ms while compact direct-build + strict verification took 658.586 ms. Storage compression does not erase the work needed to re-establish chronology.

### Adversarial incompressible operation history

Workload: alternating single-byte literal operations. Every output byte is a separate recognized operation.

| Output writes | Byte receipt JSON | Compact JSON | Compact nodes | Compact/byte | Byte peak RSS | Compact peak RSS |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 131,140 B | 182,139 B | 1,000 | 1.388890 | 20,516 KB | 20,896 KB |
| 5,000 | 663,140 B | 918,139 B | 5,000 | 1.384533 | 24,984 KB | 25,828 KB |
| 10,000 | 1,338,141 B | 1,838,140 B | 10,000 | 1.373652 | 30,452 KB | 32,292 KB |

The semantic model separately checks a 4,096-write worst case and requires exactly 4,096 compact nodes.

This is an important negative result: operation-level compaction is **not universally smaller**. When the verified operation stream itself is byte-granular, the compact metadata can be larger than the explicit byte receipt. A sound implementation must accept that worst case or choose another independently verified operation algebra. Equal values are not permission to coalesce nodes.

## Resulting evidence contract

A compact transform receipt is defensible for this bounded model when all of the following are true:

1. **Operation semantics are independently authenticated.** A node cannot invent its own decompressor behavior.
2. **Transform generation is explicit.** Byte-identical redecompression still mints distinct output generations.
3. **Ordering is canonical.** Operation index, output sequence and destination range are rechecked.
4. **Sequential-copy semantics are explicit where required.** This is what makes one unsplit overlapping backreference node sufficient.
5. **Initial/current source generations are available to replay.** Values alone are insufficient.
6. **Successful effects are causally committed.** The compact node commits to source generation and write generation, not just output bytes.
7. **Replay recreates fresh output generations before later reads.** Source/output overlap and self-feeding backreferences therefore preserve read-before-clobber chronology.
8. **Missing/reordered/widened/substituted nodes fail closed.** A compact receipt is a proof object, not a hint.
9. **Worst-case explicitness is allowed.** If verified operation cardinality equals byte cardinality, provenance remains large rather than being value-collapsed.

A cryptographic causal commitment is an integrity mechanism over a rederived causal stream. It does not convert a value hash into provenance and must not be used as a substitute for replay.

## Closed-world impact

This result removes one scalability concern from the prior decompression evidence contract: Plaid does not necessarily need to persist one parent edge per decompressed output byte.

For sequential dictionary-style operations, one compact node can stand for a large output range, including a self-feeding overlapping copy, provided the node's operation semantics and transform identity are independently verified and the exact byte ancestry can be reconstructed on demand.

That can make causal decompression evidence materially smaller without collapsing generations or weakening deletion resistance.

It does **not** make a decompressed executable generation CLOSED by itself. The compact transform output still must compose with:

- actual guest decompressor recognition/dataflow;
- successful backing-memory effects;
- D-cache/writeback chronology where applicable;
- physical aliases and TLB/mapping generations;
- I-cache resident/fill generations;
- overlay/executable lifetimes;
- roots and direct/indirect reachability;
- whole-ROM mutation completeness.

If any of those joins are missing, the executable universe remains OPEN.

## Remaining gaps

- No production `ProgramMap`/provenance schema stores transform nodes or causal commitments.
- No MIO0/Yay0/Yaz0/game-specific guest decompressor was recognized or traced here.
- General CPU/RSP dataflow discovery required to derive transform operations remains open.
- The verifier retains generation-bearing output memory needed by arbitrary backreferences; receipt storage shrinks, but live transform state is not proven O(operation count).
- The operation algebra here has byte literals and sequential backreferences only. Other transforms need separately verified semantics.
- The causal SHA-256 field assumes ordinary cryptographic collision resistance as an integrity commitment; causal truth still comes from independent replay.
- Cached/TLB/alias/storage-effects and executable lifetime are separate obligations.
- Hosted timing/RSS numbers are measurements of this Python model, not production performance guarantees.
- There is no hardware-universal claim.

## Integration recommendation

**ADOPT the representation principle, not the Python model wholesale.**

Production transform evidence should be allowed to retain canonical operation/range nodes instead of byte-parent edges when an independent verifier can reconstruct the exact source and writer generations from those nodes. In particular, a sequential backreference node may remain unsplit across self-feeding overlap; splitting at every generated byte is unnecessary if the operation semantics unambiguously recreate that chronology.

Keep a causal commitment over the expanded generation-bearing effects for artifact integrity, but never accept an output/value hash as ancestry. Do not coalesce operations because values, addresses or final bytes happen to match. Permit a byte-granular/worst-case fallback when the verified operation stream does not compress.

A production design should also avoid requiring the compact builder to materialize a byte receipt first; the direct-builder experiment demonstrates that the compact commitment can be accumulated while the transform is replayed.

## Reproduction

On the research branch:

```bash
python3 -m py_compile \
  experiments/decompression_ancestry_compaction.py \
  experiments/decompression_ancestry_compaction_bench.py
python3 experiments/decompression_ancestry_compaction.py
python3 experiments/decompression_ancestry_compaction_bench.py
```

The semantic experiment must report:

```text
SEMANTIC_SHA256=d5fffb1bd106f35f4431458bdad89740c729d111b56408111c1037402a497b1a
PASS: compact operation/DAG receipts expand exactly to byte-granular ancestry; unsplit sequential backrefs preserve self-feeding generations; strict replay rejects every forged compact receipt
```

The direct-builder benchmark must report:

```text
EQUIVALENCE_SHA256=a14624c47caedec6b27c5e0d1576009ab3b1581b8cd5c28c4f81fbebe6889a80
PASS: direct compact construction equals byte-history compaction and expands to the identical causal write sequence without retaining byte-write receipts
```

Benchmark wall times/RSS may vary by host; encoded sizes, node counts and stable semantic/equivalence digests are deterministic.
