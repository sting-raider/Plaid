# ASID switching can reactivate an older resident executable generation

Date: 2026-10-09

Result: **VALIDATED for the bounded exact-pinned ares interpreter scope**.

Integration recommendation: **ADOPT the composition obligation, not the research fixture**. Cached executable identity must keep translation-context generation, installed mapping generation, physical backing generation, and resident cache generation distinct. Making a mapping temporarily inactive by changing ASID does not itself retire the resident instruction bytes. A later context switch can make that resident generation reachable again if its cache slot/tag still matches the newly selected mapping.

Canonical Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.

Exact references:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

This experiment composes two previously validated Plaid research results rather than re-proving them independently:

1. `research/mtc0-entryhi-asid-context.md` on branch `research/mtc0-entryhi-asid-gpt56sol`: real interpreted `MTC0 EntryHi` changes active ASID matching without changing installed TLB entries, and same-value writes are still ordered context-writer events.
2. `research/ares-tlb-icache-synonyms.md` on branch `research/tlb-icache-synonyms-gpt56sol`: exact pinned ares keeps I-cache residency independently of TLB rewrites, indexes the selected line by virtual address and validates it with a physical-page tag, while pinned Gopher64 disagrees on cache index source.

The new question is whether those facts compose into a stronger executable-lifetime rule when only translation context changes.

## Hypothesis

For already-installed non-global mappings of one virtual instruction address, an `A -> B -> A` ASID sequence can make A's old resident I-cache generation executable again without any TLB entry mutation or refill. If A's physical backing changes while A is inactive, returning to A can therefore execute stale resident bytes rather than current backing.

If exact execution instead invalidated/refilled the resident line on `MTC0 EntryHi`, or made the old line unreachable after switching away, the hypothesis would be rejected.

## Exact source contracts

The branch source guard rechecks exact upstream revisions before execution.

Pinned ares:

- `CPU::MTC0` routes the guest write through `setControlRegister`.
- EntryHi register write updates `scc.tlb.addressSpaceID`, VPN and region but does not mutate installed `tlb.entry[]` or I-cache state.
- non-global TLB matching rejects an entry whose stored ASID differs from the active EntryHi ASID.
- a cacheable successful translation returns a physical address to the instruction fetch path.
- `InstructionCache::line` selects by `vaddr >> 5 & 0x1ff` and `Line::hit` checks the resident physical-page tag.

Exact source SHA-256 receipts from Actions:

```text
interpreter-scc.cpp  df7252d14f532e9fa44a39147be05afeb9851196a7d5249ab325900cee2aa722
tlb.cpp              93722177331f1df2cd7cbf313909bf20a148183d8cbd73db928b7cf0bff506d1
cpu.hpp              6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27
```

Pinned Gopher64 source remains an independent disagreement guard for the cache-index detail:

```text
src/device/cache.rs  45fad688563424d08d8db0e2ce52c588f65cb8f114f14648e190dee6090af177
```

Gopher64 indexes its cache by physical address at this revision. Therefore the experiment does **not** promote ares's virtual-index policy into N64 hardware truth. The portable result below is the need to preserve resident-byte history independently from current translation context/backing.

## Executable fixture

`experiments/asid-icache-lifetime/driver.cpp` builds through Plaid's existing exact-ares headless oracle path with both CPU and RSP recompilers disabled. No ares source is patched or instrumented.

The fixture installs these mappings before the test and then verifies that every installed TLB entry remains unchanged:

```text
VA 0x4000, ASID 0x11 -> PA 0x1000, cacheable, instruction ORI t1,zero,0x1111
VA 0x4000, ASID 0x22 -> PA 0x3000, cacheable, instruction ORI t1,zero,0x2222
VA 0x4000, ASID 0x33 -> PA 0x5000, cacheable, instruction ORI t1,zero,0x1111
VA 0x6000, global    -> PA 0x7000, cacheable, instruction ORI t2,zero,0x7777
```

The ASID changes execute real guest opcode `0x40885000` (`MTC0 t0,EntryHi`) from an uncached helper page. The helper therefore does not perturb the cacheable test slot.

The adversarial sequence is:

1. Set ASID `0x11`, fetch VA `0x4000`, and fill the selected I-cache line from PA `0x1000` with `0x34091111`.
2. Change only EntryHi ASID to `0x22`. Assert all installed entries and the resident A line are unchanged.
3. While A is inactive, change PA `0x1000` backing to `0x34094444`.
4. Fetch the separate global mapping at VA `0x6000`, a different ares I-cache index, so it cannot replace A's selected line.
5. Execute the exact same `MTC0 EntryHi(0x22)` value again. The before/after EntryHi value is equal, but a second context writer executed.
6. Switch to unmatched ASID `0x44` and fetch VA `0x4000`; require a TLB-load exception and no I-cache miss/refill.
7. Switch back to ASID `0x11` and fetch VA `0x4000`.
8. Switch to ASID `0x33`, which maps the same VA to different PA `0x5000` containing bytes equal to A's old resident payload. Require a miss/tag replacement despite equal bytes.
9. Switch back to ASID `0x11`. Because the ASID `0x33` fetch replaced the shared resident slot, require a miss and observe current A backing `0x4444`.

## Exact observations

The decisive reactivation event was:

```text
current PA 0x1000 backing word:     0x34094444
active ASID after MTC0:             0x11
translated fetch PA:                0x00001000
executed immediate:                 0x1111
I-cache miss count before/after:    2 -> 2
resident physical tag:              0x00001001
```

Thus returning to ASID A made the old resident generation reachable again and executed stale `0x1111` even though current A backing would execute `0x4444` on a refill.

The equal-payload decoy then selected ASID `0x33` / PA `0x5000`:

```text
executed immediate:                 0x1111
I-cache miss count:                 2 -> 3
resident tag:                       0x1001 -> 0x5001
```

Equal instruction bytes therefore did not preserve resident-generation identity. Returning to ASID `0x11` after that conflicting fill caused another miss `3 -> 4` and finally executed fresh `0x4444` from PA `0x1000`.

The unmatched ASID control raised TLB-load exception code `2` at VA `0x4000` and left miss count `2 -> 2`. The global mapping remained executable under both tested non-global ASIDs. Installed TLB entries remained byte-for-semantics unchanged through the full sequence.

## Adversarial reducer

`model.py` separately models four generation classes:

- translation-context generation;
- fixed installed mappings;
- physical backing generation;
- resident fill generation.

It rejects four explicit forged histories:

- attributing the stale hit to current backing generation 2;
- treating equal-payload PA `0x5000` as reuse of A's fill generation;
- fabricating successful mapped execution for the unmatched-ASID fault;
- reusing A's old stale generation after the conflicting PA `0x5000` fill replaced it.

A deterministic 50,000-step adversarial run produced:

```text
fetches:                              14,873
faults:                                5,246
same-value ASID writes:                4,373
naive current-backing wrong origins:   3,597
stale-hit wrong origins:               3,597
equal-payload/different-PA transitions:1,144
model SHA-256: 97228e1e17f1810806795d40e346e5a7832d77a5441ef609c66aaf1f708ebd8f
```

The model is not a hardware oracle. It is a falsification harness for provenance reducers once the exact executable run establishes that a resident generation can outlive temporary ASID inactivity.

## Reproducible receipts

Exact-pin GitHub Actions run:

```text
run:                       37969367332
job:                       113951744017
executed Plaid head:       9071d5471fe85eca0c17fb9626492616036449a1
result JSON SHA-256:       448051784104daca1c2ec2c079a60afcd18ace1b71b708a3bcf815c74196714d
repeat stdout SHA-256:     103bcf603e8d4a70bac74c07c99d1d1ee6993db92295563e2921db3d5a520d55
final I-cache SHA-256:     130c3e8f7638eb65c18bbc3e5690f667ddf0d3796c03ae3af4908d99e2fad1ea
artifact ID:               11635555459
artifact ZIP SHA-256:      dd58e647b8724358f9d861464cfef4678849d9d228778ad0235eecd4aa72605c
```

The run passed exact reference checkouts, Python syntax, source guards, the adversarial reducer, exact ares build, two byte-identical fixture executions, semantic assertions, and artifact publication.

## Closed-world impact

A cached executable certificate cannot model a virtual instruction address as having one lifetime tied only to its **currently active** TLB mapping. Nor can switching ASID away be treated as retirement of the old resident bytes.

For a scope in which ASIDs and cacheable mappings can change, the evidence model needs to be able to answer at each fetch:

1. which installed TLB-entry generation matched under the current translation-context generation;
2. which physical address/tag that match produced;
3. which resident cache generation occupies the selected cache slot;
4. which backing-generation/fill transaction produced that resident generation;
5. whether any intervening replacement, invalidation, cache operation, reset/restore action, or other modeled cache mutation ended it.

A translation-context change can alter **reachability** without mutating the stored mapping or resident bytes. Temporary non-reachability is therefore not the same thing as lifetime retirement.

This does not by itself close any whole-ROM certificate. It removes one unsafe simplification that a future cache + TLB + overlay/lifetime verifier must reject.

## Limitations

- This is exact pinned ares interpreter evidence, not a physical VR4300/N64 measurement.
- Pinned Gopher64 disagrees with ares on I-cache index source, so no universal virtual-index claim is made.
- Only 4-KiB cacheable mappings, one VA, a few ASIDs, big-endian mode and identity RDRAM backing were executed.
- Large PageMask geometry, ASID/global corner cases, TLBWR/TLBP/TLBR, save/restore/reset/NMI, explicit CACHE operations, privilege/64-bit regions and recompiler behavior remain separate obligations.
- The backing mutation is debugger-originated to isolate lifetime composition; its producer provenance is not established by this experiment.
- The run does not establish arbitrary-ROM reachability, a complete cache mutation census, overlay completeness, or native-complete closure.

## Reproduce

With `.refs/ares` and `.refs/gopher64` at the exact revisions above:

```bash
python3 -m py_compile experiments/asid-icache-lifetime/{source_guard.py,model.py,run.py}
python3 experiments/asid-icache-lifetime/source_guard.py
python3 experiments/asid-icache-lifetime/model.py
python3 experiments/asid-icache-lifetime/run.py
sha256sum target/asid-icache-lifetime/results.json
```

Expected result SHA-256:

```text
448051784104daca1c2ec2c079a60afcd18ace1b71b708a3bcf815c74196714d
```
