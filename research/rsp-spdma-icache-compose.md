# RSP producer -> reverse SP DMA -> cached CPU fetch composition

Status: **VALIDATED at the causal composition/model boundary**, pending the branch CI receipt recorded below. This note does not claim a new hardware timing result or a new emulator execution primitive.

Date: 2026-10-10

Canonical Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/rsp-spdma-icache-compose-gpt56sol`

Pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

## Question

Can Plaid compose already-validated RSP writer provenance, reverse SP-DMA RDRAM effects, and I-cache resident provenance into one defensible cached CPU instruction origin without silently replacing causal identity with equal bytes, current RAM, a matching cache tag, or a matching historical line tuple?

This is the seam left open by two prior results. `research/rsp-dmem-spdma-rdram-fetch.md` validated decoded RSP DMEM writer generations through reverse SP DMA into a later **uncached** CPU fetch. `research/icache-rdram-chronology.md` and the later shared-cache chronology established the separate cache rule: a witnessed identity-RDRAM fill captures backing into resident state, and later backing mutation does not retroactively rewrite already-resident instruction bytes.

## Hypothesis

A cached CPU fetch may inherit an RSP producer root only through four distinct identities:

1. the current per-byte RSP DMEM writer generation;
2. the concrete reverse-SP-DMA RDRAM sink/storage generation produced from it;
3. the exact backing generations consumed by the I-cache fill; and
4. the resident cache generation selected by the fetch.

The identities must not be collapsed merely because all payloads remain equal. In particular:

- an equal RSP rewrite followed by equal reverse DMA changes RDRAM storage generation but not an already-resident line;
- an equal CPU/RDRAM overwrite after fill changes backing generation but not the stale resident line;
- invalidation/refill must switch lineage to the backing generation actually read by the new fill;
- an equal overwrite *before* fill must win at that fill;
- restoration of an equal tag/data tuple without an observed causal fill cannot resurrect an old fill identity.

## Prior executable evidence composed

The reverse-DMA side is taken from the exact-pin validated `research/rsp-dmem-spdma-rdram-fetch-gpt56sol` result. That experiment executed decoded RSP stores, measured primitive DMEM sinks and successful `SP_DMA` RDRAM effects, and showed that equal writer values still produce distinct writer generations. Its primary exact-pin Actions receipt was run `37916462499`; the measured uncached terminal fetch is not reused as cache evidence here.

The I-cache side is taken from the previously executed fill/CACHE/RDRAM fixtures and their shared-chronology composition. The exact pinned ares implementation performs cached interpreter fetches through `InstructionCache::fetch`; a miss performs `Line::fill`, and `Line::fill` synchronously calls `busReadBurst<ICache>` before the fetched word is read from resident storage. The bus labels that burst `VR4300_ICACHE`, and MI delegates the normal RDRAM burst to RDRAM backing.

The new `source_guard.py` binds this composition to those exact source seams at the pinned ares revision. It is a guard against silently applying the result after the reference implementation changes; it is not itself hardware truth.

## Deterministic composition fixture

`experiments/rsp-spdma-icache-compose/model.py` builds a 24-event history. Every byte retains both a storage generation and an ultimate root. The cache separately retains a resident generation. The verifier replays the history independently and checks every claimed generation rather than selecting an equal-valued predecessor.

### Phase A: RSP -> DMA -> miss/fill -> fetch

RSP writer context 1 creates instruction word `0x34081234` in DMEM. Reverse SP DMA creates fresh RDRAM storage generations rooted in context 1. The fill consumes those exact RDRAM generations, creating resident generation `fill:4`. Fetch 5 roots all four instruction bytes in RSP context 1.

### Phase B: equal RSP rewrite and DMA while the line is resident

RSP writer context 2 writes the identical word and reverse DMA replaces current RDRAM with new storage generations rooted in context 2. Cached fetch 8 still roots in context 1 because it reads the unchanged resident generation. A deliberately naive `current RDRAM -> hit origin` rule instead reports context 2 and is therefore falsified. After invalidation and fill 10, fetch 11 correctly roots in context 2.

### Phase C: equal CPU overwrite after fill

A CPU RDRAM write replaces backing with the same word. Fetch 13 remains rooted in the resident context-2 line, while a current-backing policy incorrectly attributes it to the CPU write. Invalidation/refill 15 captures the CPU storage generation, so fetch 16 correctly roots in that CPU writer.

### Phase D: equal overwrite before fill

A new RSP context 3 and reverse DMA first replace backing, then an equal CPU write replaces the same bytes before the fill. Fill 21 must consume the CPU storage generation, not recover the older equal RSP/DMA chain. Fetch 22 roots in the CPU writer.

### Phase E: equal restored tuple without a fill witness

The fixture restores an identical line tag/data tuple but supplies no causal fill witness for that residency. Fetch 24 therefore has `UNKNOWN` provenance. An intentionally naive `latest historical fill whose tuple equals the restored tuple` policy resurrects the prior CPU fill and is falsified. This composes with the already-reproduced restore/residency warning in canonical STATUS rather than treating tuple equality as lifetime evidence.

## Adversarial replay

Seven forged histories are required to fail closed:

- substitute the older equal RSP writer generation into the later reverse DMA;
- substitute the older equal RDRAM generation into the later fill;
- delete the later equal reverse-DMA sink;
- insert an equal backing overwrite before fill while retaining obsolete fill claims;
- move the fill to the wrong physical line;
- forge the resident generation on a hit;
- duplicate an event ordinal.

The strict replay rejects all seven. These mutations specifically attack generation identity and ordering, not merely payload correctness.

## Determinism

The local pre-CI replay was executed twice byte-for-byte identically.

- model stdout SHA-256: `0e44da1f703fff536c3bb4e593bfe8b654d5eb96afdff61d0a33d77811f70c6d`
- canonical trace SHA-256: `6a9e0bea95160957ff404b1fabaec599c90399778068134ae57a1ed59d29435d`
- internal report-payload SHA-256: `82a5137174bef25a914010c8e3d4cdca4be5f5871f2fb47c1b894e37d0027b1a`

The branch workflow independently checks out the exact ares pin, runs the source guard, byte-compiles the model/guard, executes the model twice, compares outputs, and records SHA-256 receipts.

## Result

**VALIDATED for the bounded proof-composition contract.**

The minimum sound causal state at this seam is not one generic "code generation." It needs at least:

- source writer generation for each relevant byte;
- destination/storage mutation generation for reverse DMA or later writes;
- fill identity bound to the exact backing generations it consumed; and
- resident-cache generation/lifetime selected by the fetch.

Backing mutation and resident mutation are different events. Equal bytes do not merge them. A cached hit must follow resident provenance, not current backing provenance; a refill follows the new backing generation; restore/eviction without a witnessed causal resident installation remains unknown.

This is useful for a future executable certificate because it prevents a plausible false proof: a solver that re-attributes cached execution from current RDRAM can silently assign the wrong producer after an equal reload/write, while a solver that matches old cache tuples can resurrect dead provenance after restore.

## Closed-world impact

This closes one composition uncertainty, not whole-ROM closure. It supplies a concrete fail-closed contract for carrying an already-known RSP producer across reverse SP DMA into a **cacheable** CPU fetch. A future CLOSED decision must preserve the four identities above or an equivalent causal representation. It cannot use payload equality, current RAM, PC/physical address, tag equality, or an equal historical tuple as substitutes.

## Limitations and remaining gaps

This experiment deliberately does not claim:

- new reference-emulator execution beyond the primitive receipts already validated by prior experiments;
- hardware-exact cache/DMA timing;
- arbitrary SP-DMA count/skip/wrap/overlap behavior;
- translated/degraded/TLB backing paths;
- D-cache-delayed writes and writeback interactions beyond the modeled successful RDRAM storage generations;
- reset/save-state restore provenance when an actual restore mechanism supplies stronger causal evidence;
- RSP IMEM reverse-DMA sources;
- complete executable mutation sensing, cache lifetime census, exception roots, or whole-ROM closure.

A production evidence model should adopt the identity separation and replay obligations, then bind them to the project’s ordered backing/cache history rather than promoting this standalone model directly into ProgramMap.

## Reproduction

```bash
python3 -m py_compile \
  experiments/rsp-spdma-icache-compose/model.py \
  experiments/rsp-spdma-icache-compose/source_guard.py
python3 experiments/rsp-spdma-icache-compose/source_guard.py --ares .refs/ares
python3 experiments/rsp-spdma-icache-compose/model.py > /tmp/rsp-cache-1.json
python3 experiments/rsp-spdma-icache-compose/model.py > /tmp/rsp-cache-2.json
cmp /tmp/rsp-cache-1.json /tmp/rsp-cache-2.json
sha256sum /tmp/rsp-cache-1.json
```

Integration recommendation: **PRIMARY-INTEGRATOR-REVIEW / ADOPT THE COMPOSITION INVARIANT**, not the research scaffolding wholesale.
