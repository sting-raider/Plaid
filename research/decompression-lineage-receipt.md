# Causal lineage receipts for dictionary/LZ-style decompression

Status: **VALIDATED (bounded evidence-contract model)**

Date: 2026-10-10

Plaid canonical base inspected before claim: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/decompression-lineage-receipt-gpt56sol`

Coordination claim: issue #4 comment `6091038512`

## Question

Plaid's current progress map still lists decompression/relocation lineage as open. Runtime relocation has separately acquired a causal provenance model, and prior CPU copy/transform work established that value compatibility is not causal provenance. The remaining higher-order question here is what a **decompression receipt itself** must retain before decompressed bytes may participate in executable provenance.

A tempting certificate is something like:

- compressed input span/hash;
- output span/hash;
- decompressor/format identity.

That can authenticate result bits. It does not, by itself, prove the causal ancestry of those bits.

The difficult case is ordinary dictionary/LZ behavior: a backreference can read bytes emitted earlier by the same transform. With overlap, later bytes in one backreference can read generations created only moments earlier by that very backreference. Source and output storage can also alias, so an earlier output write can replace a future input byte before the decompressor reads it. Equal values make both cases invisible to before/after or hash-only reasoning.

This experiment asks for the minimum bounded evidence contract that survives those adversaries.

## Scope and non-claims

This is deliberately an **evidence-contract experiment**, not a claim that one compression format describes arbitrary N64 software.

It does not recognize MIO0, Yay0, Yaz0, gzip/deflate, bespoke game codecs, or arbitrary decompressor machine code. Instead it uses the two data-movement primitives needed to expose the provenance problem:

1. literal read from a declared source span;
2. sequential backreference from already-produced output.

Any format-specific recognizer still has to prove which literal/backreference operations actually occurred. The result here says what causal identity such a recognizer must preserve once those operations are known.

No physical-N64 timing or hardware transaction claim is made. No production Plaid file is modified.

## Prior work composed or challenged

This work composes these already-established Plaid invariants:

- CPU copy provenance requires actual def-use/storage history rather than equal payloads;
- the bounded `LW/LWU -> XORI -> SW` result requires an explicit transformation generation even for identity-valued `XORI 0`;
- byte-level mutation work retains successful writer generations, including same-value writes;
- ADR-0009 requires deletion/fabrication resistance and fail-closed proof inputs;
- runtime relocation provenance is a separate transformation precedent, not a decompression substitute.

It challenges the shortcut that an authenticated compressed blob plus deterministic decompressor plus authenticated final output uniquely authenticates executable-byte **provenance**. Those facts establish content compatibility. They do not distinguish alternate storage generations, decoy equal-valued source bytes, output-to-output ancestry, same-value redecompression, or read-before-clobber chronology.

## Pinned reference context

The exact pinned N64ModernRuntime revision is
`cdf5abbd5026fef5c364c676e4667c45e42b6863`.

Its `librecomp/include/librecomp/game.hpp` Git blob
`a4cf7e861c678931dc9916ab84dcf0b8e68ba6e3` exposes, for projects whose code is compressed, a project-supplied callback:

```cpp
std::vector<uint8_t> (*decompression_routine)(std::span<const uint8_t> compressed_rom)
```

and `librecomp/src/mods.cpp` calls that routine on the ROM and retains the resulting decompressed bytes for compressed-code support.

That is useful behavioral context: a native/recomp runtime can consume a deterministic decompressed image. It is not a guest causal provenance receipt. The callback boundary does not by itself state which source storage generation produced each output byte, whether a byte came from a literal or a prior output generation, or what guest chronology installed those bytes. Plaid's closed-world evidence burden is therefore stronger than simply possessing a host decompression function.

## Executable model

Artifact:

- `experiments/decompression_lineage_receipt.py`
- branch-only workflow `.github/workflows/research-decompression-lineage-receipt.yml`

The model maintains byte-addressed memory where every byte is:

```text
(value, generation_token)
```

Initial source bytes receive storage-generation identities such as:

```text
I:<source epoch>:<address>
```

Every successful output byte write receives a fresh output generation:

```text
O:<transform invocation>:<sequence>
```

The tiny transform IR is:

```text
literal(source_offset)
backref(distance, length)
```

Backreferences are copied sequentially. Therefore when `length > distance`, later bytes may read earlier output writes from the same operation. This is intentional and is the core overlapping-copy adversary.

A write receipt records:

- transform invocation identity;
- ordered write sequence/output index;
- destination address;
- byte value;
- exact source address actually read;
- exact source generation actually read;
- fresh destination/write generation.

The model allows source/output address overlap, so the current source generation at the instant of the read matters.

## Three verifier strengths

The experiment compares three acceptance rules.

### 1. Hash-only/content verifier

It independently replays the transform values and authenticates:

- input value hash;
- transform-op hash;
- output value hash.

It deliberately ignores source/output generations and the claimed causal write history.

This is stronger than blindly trusting a claimed output digest, but it remains provenance-blind.

### 2. Value/event-shape replay

In addition to the hashes, it requires the same:

- write count;
- output sequence/index;
- destination addresses;
- output byte values.

It still ignores causal source generations and fresh destination generations.

This models an apparently respectable transaction trace that retained all final write effects but discarded ancestry.

### 3. Strict causal replay

It starts from the supplied storage generations, re-executes ordered reads/writes, and requires the claimed receipt to exactly match:

- source address;
- source generation;
- output sequence/destination/value;
- fresh output generation;
- transform identity.

If history is missing, reordered, generation-collapsed, or attached to an equal-valued decoy, the receipt fails.

## Deterministic positive corpus

GitHub Actions run `38005027990`, job `114071724066`, at code head
`cd56c951584176db44f2bbe796164d688466f653` completed successfully.

With deterministic seed `344876730692` (`0x504c414944`), the model generated:

- 20,000 valid random transform programs;
- 880,132 successful output-byte writes;
- 19,916 programs containing at least one self-feeding overlapping backreference;
- 2,858 programs with source/output storage overlap.

Strict causal replay accepted all 20,000 valid histories.

The complete run was executed twice and stdout was byte-identical.

Hashes:

- report payload SHA-256:
  `336443e2a109033f0aad3c43ffdb7d6f94c8c8ea2a820b7be25ac516047d0a24`
- experiment file SHA-256:
  `4b33a3ada5d3347bc93099a576e7c8e98a63bcbaa4a1fc1759033205d5577835`
- complete stdout SHA-256:
  `15e2bcf5e8d5ff16f8d735e15729d4ed4981a9def48a33ff1480c6ac6d4383db`
- Actions artifact ID: `11650344170`
- artifact ZIP digest:
  `sha256:0e1b21445bde084b8170fa42a7a9ec1ec716deb40964ec5fa23071a94e43012e`

## Adversarial falsification corpus

The same run generated 10,000 forged histories for each of eight independent axes, 80,000 forgeries total.

Strict causal replay rejected **80,000 / 80,000**.

The hash/content verifier falsely accepted **80,000 / 80,000**.

The stronger value/event-shape replay falsely accepted **70,000 / 80,000**. It rejected only the 10,000 histories whose write list was truncated, because the remaining seven axes preserve all output values and locations while corrupting only causal identity.

### A. Input storage-generation swap

Two compressed-source memories have byte-identical contents but different storage generations. A receipt captured against generation A is presented with generation B.

- hashes: identical;
- decompressed values: identical;
- write locations: identical;
- causal input generations: different.

Hash and value replay accept. Strict replay rejects.

Thus an input digest identifies content, not the storage/writer generation that the decompressor actually consumed.

### B. Overlapping backreference flattened to a literal

A distance-1 backreference produces repeated equal bytes. By sequential-copy semantics, output byte `n` reads output generation `n-1`, not the original literal generation.

The forged receipt replaces one output-to-output parent with the equal-valued original input byte.

All values remain identical, yet the causal DAG is false. Hash and value replay accept; strict replay rejects.

This is the central counterexample against treating dictionary expansion as a simple `compressed input -> final output` edge.

### C. Equal-payload decoy input

Two source addresses contain the same byte. A literal actually reads source A; the forged receipt names source B.

No value/hash check can distinguish them. Strict generation/address replay does.

### D. In-place equal-value future-source clobber

Source bytes are equal and output begins inside the source span. The first output write overwrites a byte that a later literal will read, but writes the exact same value.

The later literal therefore reads the **new output generation**, not the initial source generation, even though before/after bytes are equal.

A forged receipt that assigns the old source generation passes hash and value replay. Strict replay rejects.

This falsifies any in-place certificate based only on final memory equality or static source-span identity.

### E. Future generation reordered as parent

An early output write is forged to claim a later, not-yet-created output generation as its source.

The bits remain compatible. Only chronology exposes the impossible edge.

### F. Missing source generation

The receipt deletes a parent-generation identity while preserving source address and byte value.

A verifier that tolerates this deletion turns UNKNOWN provenance into apparently valid content. Strict replay refuses the certificate.

### G. Same-value redecompression generation collapse

The same transform runs twice into the same destination span with identical bytes. The second transform is forged to reuse the first transform's output generation tokens.

The final contents are identical, but the second successful write sequence is a distinct causal lifetime/generation. Hash and value replay accept the collapse; strict replay rejects it.

### H. Truncated write history

The final write event is removed from the claimed history while the content hashes remain unchanged.

Hash-only verification still accepts. Value/event-shape and strict replay reject because the causal/effect history is incomplete.

This is the one adversary visible without generation identity; the other seven demonstrate why merely preserving write values and locations is not enough.

## Resulting minimum decompression receipt

For a bounded transform instance, a defensible decompression certificate needs enough evidence to reconstruct or independently verify these facts:

1. **Transform invocation/generation identity.** A second identical decompression is still a new operation and output generation.
2. **Exact source storage generations.** Literal/control/input reads bind to the actual byte/storage generations consumed, not merely equal values or a content digest.
3. **Ordered output ancestry.** Backreferences bind to the exact earlier output generations actually read. Overlapping/self-feeding copies therefore form output-to-output ancestry, not one flat edge from the compressed blob.
4. **Successful destination effects.** Each output byte/range must be tied to a successful write generation/effect; same-value writes still create new history.
5. **Alias/read-before-clobber chronology.** If source and destination overlap or alias, the certificate must prove which generation existed at each source read. Static initial/final snapshots are insufficient.
6. **Deletion/reordering resistance.** Missing parent generations, impossible future parents, omitted writes, and forged ancestor IDs must fail closed.
7. **No provenance promotion from hash equality.** Input/output hashes can authenticate content and are useful integrity fields, but they cannot substitute for causal storage/transform identity.

The receipt need not literally store one node per byte in production. Range nodes, dictionary-copy spans, symbolic transform nodes, compressed ancestry DAGs or Merkleized receipts may be valid scalability strategies, provided they preserve the same causal distinctions and can be rechecked without value-equality inference.

## Closed-world impact

A decompressed executable image cannot become a CLOSED executable generation merely because Plaid knows:

- a compressed ROM/RAM span;
- the decompressor or format;
- a deterministic final output hash; and
- that the resulting bytes were later executable.

That tuple is compatible with multiple causal histories in the adversarial cases above.

For native-complete closure, a format/decompressor recognizer must establish a particular transform invocation and its causal output ancestry, or an equivalent independently verified evidence object. Unknown source generations, ambiguous backreference ancestry, source/output aliasing without read chronology, or missing successful write effects keep decompressed executable provenance OPEN.

This receipt is only one layer. After decompression, Plaid still must compose the resulting output generation with:

- physical backing identity and aliases;
- mapping/TLB/context history;
- D-cache/writeback chronology where relevant;
- I-cache resident/fill generation for cached execution;
- overlay/executable lifetime;
- control-flow/root reachability.

A valid decompression receipt therefore does **not** by itself close the executable universe. It turns one transformation edge from an unverifiable blob into recheckable causal evidence that can be composed with the rest of the proof system.

## Remaining gaps

- No commercial ROM decompressor was recognized or traced in this experiment.
- No MIO0/Yay0/Yaz0 or game-specific format-specific verifier is implemented.
- No production ProgramMap/provenance schema stores transform receipts yet.
- General CPU register/dataflow discovery needed to infer a decompressor from arbitrary machine code remains open.
- Cached/TLB/alias storage effects during a real guest decompressor are separate composition obligations.
- This model uses byte-granular sequential backreferences; formats with larger atomic units or other transform semantics need their own verified operation model.
- The experiment proves an evidence obligation by adversarial construction; it is not N64 hardware timing evidence.
- Scalability of per-byte ancestry for large histories is unresolved; production should compress the representation without erasing generation/ordering identity.

## Integration recommendation

**ADOPT the evidence obligation and adversarial regression shape, not the research branch wholesale.**

Production provenance should support an explicit transform-invocation generation whose outputs reference exact source generations, including prior output generations for overlapping dictionary copies. A format-specific decompression recognizer may issue a compact range/DAG receipt only when it can rederive those parent relations and successful effects. Missing, ambiguous or value-inferred ancestry must remain UNKNOWN/OPEN.

Do not use `(input hash, decompressor id, output hash)` as a decompression provenance certificate. It is a content-integrity statement, which is useful, but humans already invented enough ways for identical bytes to have different histories without asking Plaid to invent one more.

## Reproduction

On the research branch:

```bash
python3 -m py_compile experiments/decompression_lineage_receipt.py
python3 experiments/decompression_lineage_receipt.py
python3 experiments/decompression_lineage_receipt.py
```

The two outputs must compare byte-identically and report:

```text
REPORT_SHA256=336443e2a109033f0aad3c43ffdb7d6f94c8c8ea2a820b7be25ac516047d0a24
PASS: strict causal replay accepted all valid transforms and rejected every forged ancestry; hash/value-only rules falsely accepted generation, backreference, decoy, in-place and redecode forgeries
```

The branch-only workflow performs the syntax check, two deterministic runs, byte comparison, file/output SHA-256 calculation, and artifact upload.
