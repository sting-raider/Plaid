# ares TLBWR mapping-generation identity

Date: 2026-10-09

Result: **VALIDATED for the bounded exact-pinned-ares scope**

Integration recommendation: **ADOPT** an explicit TLB mapping-mutation event that records the concrete slot chosen at the write boundary. Do not reconstruct `TLBWR` replacement identity from pre/post snapshot differences, CP0 Index, payload equality, or a later virtual-to-physical mapping.

## Question

Can Plaid reconstruct every VR4300 `TLBWR` mapping-generation transition from ordinary pre/post TLB snapshots, CP0 Index, or payload equality, or must it capture the concrete random replacement slot at the mutation boundary?

## Hypothesis

At exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, `TLBWR` chooses one slot using `getControlRandom()` constrained by `Wired`, ignores CP0 Index as replacement identity, clears `devirtualizeCache`, writes the selected slot from staged `scc.tlb`, synchronizes derived entry state, and reports that concrete local slot to `debugger.tlbWrite(index)`.

Therefore a complete mapping-history stream must retain the actual selected slot and an ordered generation/event identity. Snapshot diffs may identify a value-changing write but fail for a same-value rewrite; CP0 Index and payload matching are not substitutes.

The hypothesis is **VALIDATED** within the tested interpreter scope.

## Exact source contract

The source guard requires, in order inside `CPU::TLBWR()`:

```text
u8 index = getControlRandom();
if(index >= TLB::Entries) return;
devirtualizeCache = {};
tlb.entry[index] = scc.tlb;
tlb.entry[index].synchronize();
debugger.tlbWrite(index);
```

It also guards `getControlRandom()`:

```text
if (scc.wired.index > 31) return (n6)random();
return random() % (32 - scc.wired.index) + scc.wired.index;
```

and the interpreter decode `op(0x06, TLBWR);`.

This matters because the concrete replacement slot exists as a local `index` before the architectural entry assignment and is explicitly passed to the debugger notification. CP0 Index is not consulted by this path.

## Executed matrix

`spikes/044-ares-tlbwr-mapping-generation/driver.cpp` executes real interpreter opcode `0x42000006` with both CPU/RSP recompilers disabled. No ares source is patched or instrumented.

### 1. Misleading Index + equal-payload decoy

Slot 7 already contains the target mapping, CP0 Index is 7, and `Wired=31`. The real `TLBWR` changed exactly slot 31, left CP0 Index at 7, and cleared the devirtualization cache.

Observed:

```text
first_changed_slot = 31
index_after_first = 7
slot7_equals_slot31 = true
first_cache_cleared = true
```

This independently breaks two tempting inference rules:

- `CP0 Index == TLBWR replacement slot` is false in the tested path.
- matching post-write payload is ambiguous because both slot 7 and slot 31 contain the same mapping.

### 2. Same-value TLBWR

Staging was copied from slot 31, `Wired` remained 31, and a second real `TLBWR` executed. The guarded source contract makes slot 31 the only possible selection. The operation again cleared `devirtualizeCache`, but the complete normalized pre/post TLB snapshot contained zero changed entries:

```text
same_value_changed_count = 0
same_cache_cleared = true
```

This is the key provenance counterexample. An unchanged TLB snapshot does **not** prove that no mapping-generation event occurred. A snapshot-diff importer would erase this real same-value rewrite entirely.

### 3. Wired range

With `Wired=30`, CP0 Index fixed at 5, and 32 unique staged mappings, every value-changing write altered exactly one concrete slot and every selected slot was 30 or 31:

```text
30,31,31,30,30,31,30,31,
31,31,30,31,31,31,31,30,
30,31,31,30,30,30,30,31,
30,31,31,30,31,30,30,30
```

CP0 Index remained 5. The executable was run twice and stdout was byte-identical, SHA-256:

```text
1e821c5629db07c3db72eef57f434fa1bbdbc399b85e8130a40556d67c4264d9
```

This dynamic matrix does not claim hardware random-number distribution. It only confirms the bounded pinned-ares selection range and one-entry mutation behavior under the tested legal `Wired` values.

### 4. Adversarial inference model

`model.py` generated 10,000 deterministic synthetic histories to attack three reconstruction shortcuts.

Observed:

```text
trials = 10000
same_value = 1981
snapshot_diff_invisible = 1981
cp0_index_wrong = 9709
payload_ambiguous = 2414
model_sha256 = 7040a6bed6ad935ad583656aaa298d8c860ff6429f9541b9334295e72ccd2e24
```

Every generated same-value event disappeared under snapshot-diff inference by construction. The model is not an emulator oracle; it is a deterministic adversarial reducer showing why those inference strategies cannot satisfy the required identity contract even if ordinary value-changing cases often look recoverable.

## Exact run receipts

First successful exact-pin workflow:

```text
Plaid base:       ae41bdba82993ec8e77f47e5f9d3bb9af06f9256
branch code head: 290babf592839e66e48c89987fd04576a23ea6ca
ares pin:         9408cb43d4948fc3ea6e152a307a34348df3fe04
Actions run:      37917241697
job:              113776321351
artifact id:      11611195370
artifact digest:  sha256:b404edf708c1c81f87a215a8e15fc863560b26c25fc7a1388279b3964437163f
results.json:     405def4f3c1e33c9cd0a8dd331ee1d33d0e664d1c578692989623796d986c11c
```

The job fetched the exact pinned ares revision, checked that the checkout was clean, ran the source guard and deterministic adversarial model, compiled the unmodified reference fixture, executed the full matrix twice, required byte-identical stdout, hashed `results.json`, and uploaded it.

## Safe integration contract

A mapping-history event suitable for closure reasoning should retain at least:

```text
chronology / generation id
operation kind (TLBWI or TLBWR)
selected concrete slot
full normalized pre-entry identity
full normalized post-entry identity
staged CP0 mapping state as useful evidence
Wired / Index context as context, not replacement identity
epoch (reset / restore handling remains separate)
```

For `TLBWR`, the concrete selected slot must be captured at the mutation boundary if complete same-value history matters. In pinned ares, `debugger.tlbWrite(index)` is already downstream of the actual local replacement choice and synchronized slot update, so it is a natural research instrumentation boundary. Plaid need not adopt that exact debugger mechanism, only the causal requirement.

A consumer must fail closed rather than infer replacement identity from:

- changed-state diff alone;
- CP0 Index;
- matching entry payload;
- the mapping observed by a later fetch;
- virtual or physical address equality.

This composes directly with the earlier mapped-uncached fetch result: a per-fetch current translation can explain one observed fetch, but mapping-history closure needs the ordered TLB mutation generation that made that translation current.

## Limitations and explicit non-claims

This result is intentionally narrow.

- It is exact pinned-emulator evidence, not a hardware characterization of VR4300 random-number quality.
- Legal tested values were `Wired=30` and `Wired=31`; `Wired > 31` is not characterized.
- `TLBWI`, `TLBR`, `TLBP`, save-state restore and reset epochs are not solved here. `TLBWI` had prior mapped-fetch coverage, but a unified production mapping-generation stream remains separate work.
- Overlapping-entry architectural behavior, large PageMask values, 64-bit regions/address modes and exception corner cases are not tested.
- No claim is made about I-cache residency or cacheable virtual synonyms; that is a separate active lane.
- This proves a bounded mapping-mutation identity requirement, not exhaustive reachability or whole-ROM closure.
- Emulator behavior is not promoted to physical-hardware truth.

## Reproduce

From the research branch with `.refs/ares` at the exact pin:

```sh
python3 -m py_compile spikes/044-ares-tlbwr-mapping-generation/{run.py,source_guard.py,model.py}
python3 spikes/044-ares-tlbwr-mapping-generation/model.py
python3 spikes/044-ares-tlbwr-mapping-generation/source_guard.py
python3 spikes/044-ares-tlbwr-mapping-generation/run.py
sha256sum target/ares-tlbwr-mapping-generation/results.json
```

Expected first-run `results.json` SHA-256:

```text
405def4f3c1e33c9cd0a8dd331ee1d33d0e664d1c578692989623796d986c11c
```
