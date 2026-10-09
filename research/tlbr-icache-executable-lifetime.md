# TLBR can reactivate an older resident executable generation

Date: 2026-10-10

Result: **VALIDATED for the bounded exact-pinned ares interpreter scope**.

Integration recommendation: **ADOPT the composition obligation, not the research fixture.** A successful `TLBR` can change translation context by loading EntryHi ASID while every installed TLB entry remains unchanged. If a matching cacheable instruction generation was already resident, later TLBR-driven ASID reactivation can make that old resident generation executable again even after its physical backing changed. Therefore cached executable identity must compose translation-context chronology, installed mapping identity/generation, physical backing generation and resident-cache generation. Temporary translation-context unreachability is not lifetime retirement.

Canonical Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`.

Validated executable head: `dd84b71880cff84e1173b1950fe90bee38be8965` on `research/tlbr-icache-lifetime-gpt56sol`.

## Prior research composed

This experiment deliberately composes rather than re-proves two earlier findings:

1. `research/ares-tlbp-tlbr-effects.md` on `research/tlbp-tlbr-effects-gpt56sol`: exact pinned ares `TLBR` can load a different EntryHi ASID and flip translation reachability without changing installed TLB entries or translation-cache objects; `TLBP` only changed Index/probe state in that matrix.
2. `research/asid-icache-executable-lifetime.md` on `research/asid-icache-lifetime-gpt56sol`: an A -> B -> A EntryHi-ASID sequence can reactivate an older resident cacheable instruction generation; changed backing does not update the resident line, and equal payload at a different PA is not the same resident generation.

The missing question was whether those facts still compose when **real guest TLBR itself** performs the ASID transition.

## Exact references and guarded source receipts

From `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

The branch source guard verified the exact pins were clean and rechecked these contracts:

- ares `CPU::TLBR()` returns for out-of-range Index, otherwise performs `scc.tlb = tlb.entry[scc.index.tlbEntry]`;
- the TLBR body has no installed-entry replacement, TLB-cache clear, devirtualize-cache clear, debugger TLB write, or I-cache mutation path;
- ares mapped load/store matching rejects a non-global entry when its stored ASID differs from `scc.tlb.addressSpaceID`;
- ares I-cache selects the line by virtual index and validates residency with a physical-page tag;
- pinned Gopher64 instead indexes its I-cache by physical address, so the ares virtual-index policy is not promoted to hardware truth;
- pinned Mupen's inspected legacy fast LUT translation path has no active-ASID predicate, preserving the known reference-model disagreement;
- pinned n64-systemtest source explicitly contains ASID-dependent TLB-use tests.

Source SHA-256 receipts from Actions:

```text
ares interpreter-scc.cpp  df7252d14f532e9fa44a39147be05afeb9851196a7d5249ab325900cee2aa722
ares tlb.cpp              93722177331f1df2cd7cbf313909bf20a148183d8cbd73db928b7cf0bff506d1
ares cpu.hpp              6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27
gopher64 cache.rs         45fad688563424d08d8db0e2ce52c588f65cb8f114f14648e190dee6090af177
mupen64plus tlb.c         e8892285ad085d954bf76623367d7a36d985b38c7994eed1b2350c4105fe150c
n64-systemtest tlb/mod.rs 221bc0f3239ddbb1f9e4d16b2910edf007db34997915db7b2d4703f5683d88f4
```

## Executable fixture

`experiments/tlbr-icache-lifetime/driver.cpp` builds through Plaid's existing exact-ares headless oracle path with both CPU and RSP recompilers disabled. No upstream source is patched.

The fixture installs these mappings before testing and then snapshots the full installed TLB array:

```text
slot 0: VA 0x4000, ASID 0x11 -> PA 0x1000, cacheable, ORI t1,zero,0x1111
slot 1: VA 0x4000, ASID 0x22 -> PA 0x3000, cacheable, ORI t1,zero,0x2222
slot 2: VA 0x4000, ASID 0x33 -> PA 0x5000, cacheable, ORI t1,zero,0x1111  (equal-payload decoy)
slot 3: VA 0x6000, global    -> PA 0x7000, cacheable, ORI t2,zero,0x7777
slot 4: unrelated VA, ASID 0x44 -> unrelated PA, used only to load an unmatched active ASID
```

Guest opcodes `TLBR` (`0x42000001`) and `TLBP` (`0x42000008`) execute from an uncached KSEG1 helper page. Each context-control step snapshots installed entries, the serialized ares I-cache contents and I-cache miss count around the instruction so the helper cannot silently provide the claimed effect by refilling or replacing the tested cache state.

The adversarial sequence was:

1. real guest TLBR slot 0 activates ASID A; fetch VA `0x4000` and fill resident A from PA `0x1000`;
2. real TLBP control finds slot 0 while leaving EntryHi context, installed entries and I-cache state unchanged;
3. real TLBR slot 1 activates B while the installed array and resident A line remain unchanged;
4. mutate current PA-A backing from `0x34091111` to `0x34094444` while A is inactive;
5. fetch unrelated global code at another ares I-cache index, preserving A's resident line;
6. execute the same TLBR slot 1 again; EntryHi before/after is equal, but the instruction really executed, and installed/I-cache state remains equal;
7. execute out-of-range TLBR Index 63; exact pinned ares leaves staged EntryHi, installed entries and I-cache state unchanged;
8. TLBR slot 4 loads unmatched ASID `0x44`; VA `0x4000` faults with TLB-load exception code 2 and does not refill/replace A's resident line;
9. TLBR slot 0 reactivates A, with installed entries and I-cache still unchanged;
10. fetch VA `0x4000` and require a **cache hit of stale `0x1111`** even though current PA-A backing is `0x4444`;
11. TLBR slot 2 selects PA `0x5000`, whose bytes equal A's old payload; require a miss/tag replacement despite equal bytes;
12. TLBR slot 0 again; because C replaced the shared resident slot, require a miss and execute fresh A backing `0x4444`.

## Decisive executable observations

Actions emitted:

```json
{
  "first_a": {"paddr": 4096, "value": 4369},
  "fault": {"badvaddr": 16384, "exception": 2},
  "stale_reactivated_a": {"paddr": 4096, "value": 4369},
  "equal_c": {"paddr": 20480, "value": 4369},
  "fresh_a": {"paddr": 4096, "value": 17476},
  "inactive_backing_word": 873022532,
  "installed_entries_unchanged": true,
  "tlbp_context_unchanged": true,
  "same_value_tlbr_unchanged": true,
  "out_of_range_tlbr_unchanged": true
}
```

The miss chronology was:

```text
initial A fill:                    0 -> 1
unmatched-ASID fault:             2 -> 2
TLBR A stale reactivation fetch:  2 -> 2   (hit)
equal-payload PA 0x5000 fetch:    2 -> 3   (replacement)
return to A after replacement:    3 -> 4   (fresh refill)
```

The reactivation fetch therefore executed old resident immediate `0x1111` from the cache while current PA `0x1000` backing already contained instruction word `0x34094444` (immediate `0x4444`). TLBR itself did not mutate the installed mapping array or serialized I-cache state.

Equal bytes did not imply equal resident provenance: selecting ASID `0x33` translated the same VA to PA `0x5000`, changed the resident physical tag from the PA-A tag to the PA-C tag and incurred a miss even though the loaded instruction bytes were also `0x34091111`.

## Adversarial reducer

`model.py` keeps five histories separate:

- TLBR instruction-operation generation;
- successful translation-context writer generation;
- installed TLB-entry generation;
- physical backing generation;
- resident cache-fill generation.

The canonical reducer rejected seven forged histories, including:

- pretending TLBR changed installed-entry generation;
- attributing the stale A hit to current backing generation 2;
- reusing A's fill generation for equal bytes at PA `0x5000`;
- treating TLBP as a translation-context write;
- treating out-of-range TLBR as a successful context write;
- fabricating a successful fetch for the unmatched-ASID fault;
- reusing stale A generation after the conflicting PA-C refill replaced it.

A deterministic 50,000-step adversarial run produced:

```text
fetches:                              13,153
faults:                                4,467
same-value successful TLBRs:           3,434
out-of-range TLBRs:                     3,583
TLBP operations:                        5,016
naive current-backing wrong origins:    3,231
equal-payload/different-PA transitions:   938
installed-entry generation:                 1
model SHA-256: 73f3a67c9cf0c83e213f083db2eb996056779edc63ff1c3de5a582129c3c540f
```

The model is a falsification harness for provenance reducers, not a hardware oracle.

## Reproducible receipts

Exact-pin GitHub Actions run:

```text
run:                         37999435843
job:                         114053639012
validated Plaid head:        dd84b71880cff84e1173b1950fe90bee38be8965
result JSON SHA-256:         3624aea92b6c3f77c455c4342ab967cc0fd3c56eb7044bc6f24bf9fe61e28d67
repeat stdout SHA-256:       a1c1df687d3afdb2a8e06922297fc06c5b0286d1cb3a2c0f23706836b6724f3e
final I-cache SHA-256:       130c3e8f7638eb65c18bbc3e5690f667ddf0d3796c03ae3af4908d99e2fad1ea
artifact ID:                 11648388498
artifact ZIP SHA-256:        3cf09da55c1ed4dca78cc0c909f26ce7c4072afab2c510ec2b79765f0d098527
```

The workflow passed exact pin checkouts, syntax, source guards, deterministic model, exact ares build, two byte-identical executable runs, semantic assertions and artifact upload.

## Closed-world impact

A future Plaid cache + TLB + executable-lifetime certificate is unsound if it assumes any of the following:

- only installed TLB-entry writes can change executable reachability;
- making an ASID inactive retires cache-resident executable bytes;
- a TLBR that leaves the installed mapping array unchanged can be dropped from translation-context history;
- current backing generation identifies bytes executed by a cache hit;
- equal instruction payload at another physical address preserves resident provenance;
- before/after equality proves that no TLBR operation occurred.

For cacheable mapped execution, a defensible fetch certificate needs enough chronology to establish at least:

1. the ordered translation-context operation/value state, including successful TLBR loads of EntryHi context;
2. the installed TLB-entry generation selected under that context;
3. the translated physical address/tag;
4. the resident cache generation occupying the selected cache slot at fetch time;
5. the backing/fill transaction that produced that resident generation;
6. all modeled replacement, invalidation, cache-operation, reset/restore and other lifetime-ending events.

A same-value successful TLBR need not imply a changed translation result, but it is still an executed context-load operation. Production should preserve operation chronology separately from mere before/after value equality. Conversely, exact-pinned out-of-range TLBR was an executed instruction with no successful staged-context load; operation occurrence and successful context-write generation are therefore also distinct facts.

This result does not close whole-ROM certification. It removes one composition ambiguity that could otherwise let a certificate retire stale executable state too early or attribute a later fetch to the wrong backing generation.

## Limitations

- Dynamic evidence is exact pinned ares interpreter behavior, not a physical VR4300/N64 measurement.
- Pinned Gopher64 disagrees with ares on I-cache index source, and pinned Mupen's inspected fast LUT does not model the same active-ASID predicate. Those disagreements are preserved rather than averaged away.
- n64-systemtest contributes hardware-oriented ASID test-source evidence; this worker did not execute it on physical hardware.
- The fixture uses 4-KiB cacheable mappings, a small ASID set, kernel execution, big-endian mode and identity RDRAM backing.
- The backing mutation is debugger-originated solely to isolate executable-lifetime composition; its producer provenance is not established here.
- Large PageMask geometry, overlapping-entry undefined cases, TLBWI/TLBWR interactions, explicit CACHE operations, save/restore/reset/NMI, privilege/64-bit regions, recompiler behavior and hardware cache replacement details remain separate obligations.
- No arbitrary-ROM reachability or complete cache/mapping mutation census is established.

## Reproduce

With exact refs checked out under `.refs/`:

```bash
python3 -m py_compile experiments/tlbr-icache-lifetime/{source_guard.py,model.py,run.py}
python3 experiments/tlbr-icache-lifetime/source_guard.py
python3 experiments/tlbr-icache-lifetime/model.py
python3 experiments/tlbr-icache-lifetime/run.py
sha256sum target/tlbr-icache-lifetime/results.json
```

Expected result SHA-256:

```text
3624aea92b6c3f77c455c4342ab967cc0fd3c56eb7044bc6f24bf9fe61e28d67
```
