# ares cacheable TLB synonyms and I-cache executable lifetime

Result: **VALIDATED** for the bounded exact-pinned ares question.

This result does **not** establish a hardware-wide VR4300 synonym-indexing rule.
Pinned Gopher64 materially disagrees with pinned ares on the index source, so the
portable Plaid conclusion is a conservative provenance/lifetime obligation, not
"ares behavior equals N64 hardware".

## Scope and exact revisions

Plaid base inspected before the claim:

- `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Exact pinned references from `refs.lock.toml`:

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`

The exact behavioral receipt was produced from worker commit
`0ee7e517bc71434b8f9f6f7471f328262ae7e78b` by GitHub Actions run
`37916234376`, job `113772979171`.

Source-guard SHA-256 receipts from that run:

- pinned ares `ares/n64/cpu/cpu.hpp`:
  `6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27`
- pinned Gopher64 `src/device/cache.rs`:
  `45fad688563424d08d8db0e2ce52c588f65cb8f114f14648e190dee6090af177`

## Question

Can cacheable TLB virtual synonyms or remaps produce distinct/stale resident
instruction generations such that executable provenance cannot be keyed only by
physical backing, only by virtual PC, or only by the current TLB mapping?

The falsifiable exact-ares hypothesis was:

1. ares selects an I-cache slot using `vaddr >> 5 & 0x1ff`;
2. the selected line is validated against a physical 4-KiB tag from
   `paddr & ~0xfff`;
3. two virtual synonyms with different virtual cache-index bits can therefore
   retain independent resident generations for the same physical code;
4. TLBWI alone does not end that resident cache lifetime;
5. fetching through a same-VA remap to a different physical page must miss and
   refill because of the physical-tag mismatch, even when payload bytes match.

## Baseline/source behavior

Pinned ares `CPU::InstructionCache` selects the line with:

```text
lines[vaddr >> 5 & 0x1ff]
```

and `Line::hit` compares the selected line's physical page tag against
`paddr & ~0xfff`. `Line::fill` stores that physical tag and reads the 32-byte
line from `tag | index`.

Pinned ares `CPU::TLBWI` clears the devirtualization lookup cache, writes and
synchronizes the TLB entry, and emits the debugger TLB-write event. It does not
invalidate or otherwise mutate `cpu.icache`.

Pinned Gopher64 is an independent counter-reference: `icache_fetch` selects its
line with `(phys_address >> 5) & 0x1ff`, then tests a physical page tag. Thus the
two pinned emulators disagree on whether virtual synonyms can occupy distinct
cache indices. This disagreement is part of the result, not something to smooth
over.

## Experiment

Durable artifacts:

- `experiments/tlb-icache-synonyms/driver.cpp`
- `experiments/tlb-icache-synonyms/run.py`
- `experiments/tlb-icache-synonyms/model.py`
- `experiments/tlb-icache-synonyms/source_guard.py`
- `experiments/tlb-icache-synonyms/README.md`
- `.github/workflows/research-tlb-icache-synonyms.yml`

The fixture uses the existing headless exact-ares build path from
`spikes/003-ares-oracle/`, disables CPU and RSP recompilers, uses identity RDRAM,
and does not install any CPU/I-cache/TLB observer or shadow header. The standard
headless builder's UI-only Vulkan guard remains outside the CPU/cache path.

The fixture programs real `CPU::TLBWI` mappings and executes one interpreted
instruction per probe. It uses synthetic `ori t1,zero,imm` words rather than a
ROM or copyrighted asset.

### Address matrix

- VA A = `0x4000`
- VA B = `0x5000`
- VA C = `0x8000`
- initial PA = `0x1000`
- equal-payload remap PA = `0x3000`
- different-payload remap PA = `0x5000`

For exact ares, A/B/C select I-cache indices `0/128/0`. A and B map to the same
physical instruction line while selecting different resident slots. C is a
same-physical, same-slot alias control for A.

### Executed adversarial sequence

1. Put `ori t1,zero,0x1111` at PA `0x1000`.
2. Fetch A: miss and fill index 0.
3. Fetch C: hit the same index/tag; no new miss.
4. Fetch B: miss and fill index 128 from the same PA.
5. Change physical backing to `ori ... 0x2222` without touching I-cache.
6. Fetch A and B: both still execute stale `0x1111`.
7. Invalidate/refill only A's resident slot. A now executes `0x2222`, while B
   still executes `0x1111`. The two resident words are simultaneously
   `0x34092222` and `0x34091111` despite one shared current physical backing.
8. Invalidate/refill B so both colors contain `0x2222`.
9. Change PA `0x1000` backing again to `ori ... 0x4444`.
10. TLBWI-remap A away to PA `0x3000` **without fetching**, then TLBWI-remap A
    back to PA `0x1000` **without fetching**.
11. Fetch A. Its previous physical tag remains present and valid, there is no
    additional I-cache miss, and it executes resident `0x2222`, not current
    backing `0x4444`.
12. Put the same resident payload `0x2222` at PA `0x3000`, remap A there, then
    fetch. TLBWI itself still leaves the old cache line valid, but the next fetch
    sees a physical-tag mismatch and increments the miss count while returning
    the equal payload.
13. Remap again to PA `0x5000` containing `0x3333`; the next fetch misses/refills
    and executes `0x3333`.

## Deterministic observations

Exact run JSON:

```json
{
  "away_back": 8738,
  "away_back_tag_preserved": true,
  "different_remap": 13107,
  "divergent_words": [873013794, 873009425],
  "equal_remap": 8738,
  "first": [4369, 4369, 4369],
  "fresh": [8738, 8738],
  "icache_sha256": "ec81afee0023067ac41d333351de2e4ad9b91c8c15fcd64a46b2f7634f65f785",
  "idx_a": 0,
  "idx_b": 128,
  "idx_c": 0,
  "initial_tags": [4097, 4097],
  "misses": {
    "after_a": 1,
    "after_a_refill": 3,
    "after_away_back": 4,
    "after_b": 2,
    "after_b_refill": 4,
    "after_c": 1,
    "after_different_remap": 6,
    "after_equal_remap": 5,
    "start": 0
  },
  "post_equal_remap_tag": 12289,
  "pre_remap_tag": 4097,
  "stale": [4369, 4369],
  "tlbwi_preserved_resident_valid": true
}
```

Key receipts:

- result JSON SHA-256:
  `0a1b89ae6849efb93596cfba35308ce8dbbe727c2e764b27ab86f6206076f903`
- independent source-model SHA-256:
  `50f35c9fc635afb588a998a13f9e54dc24c8772ade6b7a0e00ed31a7c2d4212c`
- uploaded Actions artifact ID: `11609793701`
- uploaded artifact ZIP SHA-256:
  `84daacab85dabd7576b67dcba4ad20af8a393f7db27d7e55030dcf03b828b417`

`run.py` executes the built exact-pinned fixture twice and requires byte-for-byte
identical stdout before accepting the result. The Actions job passed syntax,
exact-source guards, independent model, exact ares build/execution, and artifact
upload.

## Independent-reference counterexample

`model.py` contains two deliberately tiny source-derived index/tag models:

- exact-pinned ares index: `(vaddr >> 5) & 0x1ff`
- exact-pinned Gopher64 index: `(paddr >> 5) & 0x1ff`

For the same A/B synonym sequence, the ares model has two initial cache misses
and leaves B stale after only A is invalidated/refilled. The Gopher64 model has
one initial miss because A/B collapse to the same physical index; after that
single slot is refilled, B observes the fresh word.

This is not a hardware oracle comparison. It demonstrates that emulator
consensus does not exist for this indexing detail at the pinned revisions, so
Plaid must not turn the ares virtual-color behavior into an N64-wide invariant.

## Result

**VALIDATED**, narrowly:

- exact pinned ares can hold two different I-cache resident executable
  generations for cacheable virtual synonyms that resolve to the same physical
  backing;
- current RDRAM contents do not identify the bytes actually fetched on an
  I-cache hit;
- a TLB mapping rewrite is not, by itself, an executable-resident lifetime end;
  remapping away and back without an intervening conflicting fetch can make the
  previous stale resident generation reachable again;
- equal payload values across a physical remap do not prove generation identity;
  exact ares records a miss/refill and a new physical tag despite equal bytes;
- virtual PC alone cannot identify a generation across physical remaps;
- physical backing alone cannot identify a resident generation across ares
  virtual-color synonyms.

## Plaid implication

For cached executable provenance/closure, do not certify a fetch from current
physical contents or current TLB state alone. A resident cached-executable
witness needs a cache-residency generation that can be connected to the fill
that supplied its bytes and preserved until a verified replacement,
invalidation, reset/restore transition, or other modeled lifetime boundary.
Where the oracle exposes them, selected cache slot/index and physical tag are
part of that causal state.

Because the pinned references disagree about the index source, production logic
should not hard-code "virtual index" as a universal N64 fact merely because ares
does it. The safe architectural obligation is to preserve actual resident-byte
history and generation identity, and fail closed when the execution scope does
not model the relevant cache/TLB lifetime behavior.

## Limitations / what this does not prove

- No physical N64/VR4300 measurement was run.
- Pinned ares and pinned Gopher64 disagree on the relevant indexing policy.
- The executable fixture uses the ares interpreter; recompiler behavior is not
  separately certified here.
- Only ordinary 4-KiB TLB pages, big-endian context, identity RDRAM backing, and
  one synthetic instruction line are exercised.
- ASID/global changes, large pages, exceptions during remap/fetch, save/restore,
  reset, explicit guest CACHE operations, and actual game overlay flows remain
  separate obligations.
- Backing mutation uses the debugger-facing identity-RDRAM write intentionally
  to isolate cache lifetime; this experiment does not establish the provenance
  of CPU/DMA/RSP mutation producers.
- The result is a cached-fetch/lifetime fact, not an exhaustive reachability or
  closed-world proof.

## Reproduction

With exact pinned checkouts under `.refs/ares` and `.refs/gopher64`:

```bash
python3 -m py_compile \
  experiments/tlb-icache-synonyms/source_guard.py \
  experiments/tlb-icache-synonyms/model.py \
  experiments/tlb-icache-synonyms/run.py
python3 experiments/tlb-icache-synonyms/source_guard.py
python3 experiments/tlb-icache-synonyms/model.py
python3 experiments/tlb-icache-synonyms/run.py
```

GitHub Actions reproduction is encoded in
`.github/workflows/research-tlb-icache-synonyms.yml`.
