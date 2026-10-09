# ares TLBP/TLBR mapping-state effects

Status: **REJECTED**

Canonical Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Exact references:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Question and falsifiable hypothesis

Question: can `TLBP` and `TLBR` be excluded from executable mapping-generation history as pure observers, provided their CP0 register side effects are still recorded?

Original hypothesis: in pinned ares, `TLBP` changes only Index probe state and `TLBR` only copies a selected TLB entry into staged CP0 EntryHi/EntryLo/PageMask state; neither operation changes a TLB entry, translation caches, or the physical result of subsequent translations. If true, neither instruction would need a translation-context generation.

The hypothesis is rejected. The mapping-entry half was true in the tested scope, but the translation-observability half was false for `TLBR`.

## Baseline source facts

Pinned ares `CPU::TLBP()` initializes Index to probe-failure state, scans `tlb.entry[]`, and on the first match updates `scc.index`. `CPU::TLBR()` rejects an out-of-range Index and otherwise performs:

```text
scc.tlb = tlb.entry[scc.index.tlbEntry]
```

Neither handler contains the TLB-entry replacement/synchronization, `devirtualizeCache = {}`, internal `tlbCache = {}`, or debugger TLB-write path used by TLB writes.

The crucial causal link is elsewhere: pinned ares `TLB::load()` and `TLB::store()` reject a non-global entry when its ASID differs from `self.scc.tlb.addressSpaceID`. Therefore EntryHi ASID is part of translation context even when all 32 TLB entry objects are bit-for-bit unchanged.

Pinned Gopher64 likewise keeps `read()`/`probe()` separate from its TLB map/unmap write path. Pinned Mupen64Plus Core's legacy `virtual_to_physical_address()` fast LUT path, however, is keyed by virtual page and contains no active-ASID predicate. That is a reference-model divergence, not evidence that ASID is irrelevant on hardware.

Pinned n64-systemtest source contains `TLBUseTestReadMatchViaASID` and explicitly sets a matching EntryHi ASID before using a non-global TLB entry, plus cases that set a different ASID to require a mismatch. This is hardware-oriented test-source evidence only; this worker did not execute that suite on physical hardware.

## Executable experiment

`experiments/tlbp-tlbr-effects/driver.cpp` executes the real pinned-ares interpreter opcodes with CPU/RSP recompilers disabled and no upstream source patch. It snapshots all 32 TLB entries, the internal four-entry TLB cache, and a sentinel `devirtualizeCache` value immediately around each instruction.

The matrix covers:

1. successful `TLBP` with equal mappings in slots 9 and 17;
2. failed `TLBP` with misleading preexisting Index state;
3. `TLBR` slot 9 changing staged/current EntryHi ASID `0x22 -> 0x55`;
4. reverse `TLBR` to slot 10 changing ASID `0x55 -> 10`;
5. same-value `TLBR` where staged fields already equal slot 9;
6. out-of-range `TLBR` with Index 63.

The decisive adversarial mapping is a valid, non-global `ProbeVa=0x4000` entry at slot 9 with ASID `0x55` and physical address `0x60000`.

### First falsification run

GitHub Actions run `37919189777`, job `113782719098`, compiled the fixture successfully and failed at the original `TLBR` translation-invariance assertion with fixture exit status 9. The failure was preserved rather than weakened away: staged ASID was deliberately `0x22`, and `TLBR` loaded slot 9's ASID `0x55`, so the subsequent translation changed.

### Hardened counterexample run

GitHub Actions run `37919649022`, job `113784223064`, head `80222edc370b372e4db1c51e5152b51c615a5782`, completed successfully. The executable was run twice and produced byte-identical stdout (`a2b032b47ed848391ad45ce1d430a5e3ab00f3f5b5c107995aed8d67b5702d97`).

Observed facts:

- successful `TLBP` selected slot 9 and left the tested translation unchanged;
- failed `TLBP` set exact-ares Index payload 0 plus probe-failure and left the tested translation unchanged;
- `TLBR` ASID `0x22 -> 0x55` changed `ProbeVa` from no match to physical `0x60000`;
- reverse `TLBR` ASID `0x55 -> 10` changed the same `ProbeVa` from matched to unmatched;
- across all cases, changed TLB-entry slots: **0**;
- instruction-side snapshots of ares's internal TLB cache were unchanged;
- planted `devirtualizeCache` sentinels were unchanged;
- same-value `TLBR` left the tested translation stable;
- out-of-range Index 63 `TLBR` was an exact-pin no-op and left translation stable.

Durable result JSON SHA-256: `d72a9ff4876eb18ab46f0bad95d1cb701c8cc1fe20366278243731ae9a3924c3`.

Uploaded result artifact from run `37919649022`: artifact id `11611391341`; uploaded zip SHA-256 `c851eac2f8d65edce3d972fc6a83c90380a327d86d0f3249a3a68fb99feed0b3`.

## Adversarial reducer

`model.py` uses deterministic seed `0x504C414944544C42` for 20,000 synthetic TLBP/TLBR histories. It deliberately distinguishes installed-entry mutations from active translation context.

Run-4 deterministic counts:

- TLB-entry mutations: `0`;
- CP0-changing operations: `14,826`;
- same-value/no-CP0-delta operations: `5,174`;
- TLBP translation flips: `0`;
- TLBR active-ASID changes: `4,838`;
- sampled TLBR translation flips for a stable test VPN: `352`;
- false TLB-entry generations if every CP0 delta is mislabeled as an entry write: `14,826`.

Model summary SHA-256: `d65587630cfc9354d44b395d2bdc228c06c11f052483e9b8ff76553f2af39a12`.

This demonstrates why both naive reductions are wrong:

- "only TLB entry writes can change translation" misses TLBR's EntryHi/ASID context effect;
- "any TLB-related CP0 delta is a TLB-entry generation" fabricates entry mutations for TLBP/TLBR.

## Instrumentation neutrality

The executable fixture compiles against a clean exact ares checkout and does not patch it. Source guards require clean exact revisions. Recompilers are disabled. Instructions are fetched/executed through the real interpreter decoder. The fixture's KSEG1 instruction stream avoids introducing a mapped-code fetch between the pre/post snapshots. Each decisive run is repeated twice with exact stdout equality.

## Result and integration implication

**REJECTED**: `TLBR` cannot be classified as a pure translation observer merely because it does not replace a TLB entry. At least in the pinned ares contract, successful TLBR can change active EntryHi ASID and therefore alter which non-global mappings are usable while every installed TLB entry and translation-cache object remains unchanged.

Plaid should distinguish at least two ordered histories:

1. **TLB-entry mapping generations**, caused by actual entry writes/restores/reset-like events; and
2. **translation-context generations**, including active EntryHi/ASID changes that can change the interpretation/eligibility of otherwise unchanged entries.

A successful `TLBR` should not mint a false TLB-entry replacement generation, but it must not be elided from translation-context history when its loaded EntryHi changes the active ASID. `TLBP` produced only Index/probe-state effects in this bounded dynamic matrix.

## Limitations and explicit non-proofs

This does **not** prove a complete N64-wide TLBR semantic contract. In particular:

- the dynamic counterexample is exact pinned ares behavior, not direct hardware measurement;
- pinned Mupen's fast LUT representation does not model an active-ASID predicate in the inspected translation path, so emulator consensus does not exist here;
- n64-systemtest supplies hardware-oriented ASID expectations, but this worker did not run those tests on physical hardware;
- user/supervisor privilege and Coprocessor Unusable paths were not dynamically exercised;
- TLBWI/TLBWR, save/restore/reset epochs, overlapping-entry undefined behavior, 64-bit region edge cases, PageMask geometry, I-cache provenance, and whole-ROM reachability are outside this result;
- exact ares probe-miss Index payload `0` is not promoted to a hardware invariant; only the failure indication is semantically relied upon.

## Reproduction

```bash
python3 -m py_compile experiments/tlbp-tlbr-effects/{run.py,source_guard.py,model.py}
python3 experiments/tlbp-tlbr-effects/model.py
python3 experiments/tlbp-tlbr-effects/source_guard.py
python3 experiments/tlbp-tlbr-effects/run.py
sha256sum target/ares-tlbp-tlbr-effects/results.json
```

Expected executable result JSON SHA-256 for the recorded exact-pin matrix: `d72a9ff4876eb18ab46f0bad95d1cb701c8cc1fe20366278243731ae9a3924c3`.
