# ares large-PageMask mapped-fetch provenance

Date: 2026-10-09

Result: **VALIDATED for the bounded tested pinned-ares scope**

Integration recommendation: **ADOPT** the PageMask-aware mapping obligation. For a successful mapped fetch, retain the actual translated physical address produced by the current TLB entry and the completed backing transaction. Do not reconstruct EntryLo selection with fixed virtual bit 12 or reconstruct the physical offset with `vaddr & 0xfff` once nonzero PageMask values are possible.

## Question

The earlier `research/ares-tlb-uncached-fetch-provenance.md` validated the causal fetch-boundary + completed scalar-RDRAM witness for 4 KiB mapped pages, while explicitly leaving odd halves and larger PageMask values open.

This experiment asked whether that witness remains sound for 16 KiB and 64 KiB mappings, and whether a tempting fixed-4-KiB reducer could silently misattribute executable bytes even when the guessed physical location contains the same instruction value.

Falsifiable hypothesis:

1. exact pinned ares derives the TLB half selector and in-page offset from the synchronized PageMask, not from fixed bit 12 / low 12 bits;
2. the existing per-fetch witness stays sound when it retains the actual translated/bus physical address;
3. a reducer that reconstructs physical backing with fixed 4 KiB geometry chooses the wrong EntryLo/PFN for adversarial large pages;
4. invalid selected halves and non-global ASID mismatches fail before `CPU::fetch`, even if the fixed-4-KiB-selected opposite half is valid and contains equal bytes.

## Exact revisions

- Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`
- research execution head: `4895ef9fe99ec352f22f4854fe5853e5f952ecb6`

No production Plaid file was changed. The experiment reuses the previously validated scalar-RDRAM/fetch-boundary observer and builds an unmodified-reference baseline separately.

## Exact source contract

Pinned ares `ares/n64/cpu/tlb.cpp` synchronizes an entry as follows:

```text
pageMask &= alternating supported PageMask bits
pageMask |= pageMask >> 1
addressMaskHi = ~(pageMask | 0x1fff)
addressMaskLo = (pageMask | 0x1fff) >> 1
addressSelect = addressMaskLo + 1
```

`TLB::load` then chooses `lo = bool(vaddr & addressSelect)` and computes:

```text
physicalAddress[lo] + (vaddr & addressMaskLo)
```

Consequently the tested selector moves with page size:

```text
4 KiB page:  addressSelect = 0x00001000  (bit 12)
16 KiB page: addressSelect = 0x00004000  (bit 14)
64 KiB page: addressSelect = 0x00010000  (bit 16)
```

The exact source guard also checks pinned n64-systemtest. Its TLB suite independently labels `0b11 << 13` as a 16 KiB PageMask and `0b1111 << 13` as 64 KiB, and includes malformed-mask readback cases that agree with the pinned ares normalization used by the independent model. This is source/test agreement, not a claim that one emulator defines hardware truth.

## Executed matrix

`experiments/tlb-pagemask/driver.cpp` uses real pinned-ares `CPU::TLBWI` entry installation with the CPU and RSP recompilers disabled. Every positive mapping uses CCA=2 and identity ordinary RDRAM.

| Phase | Mapping | VA | exact PA | fixed-4K guess | observed witness |
|---:|---|---:|---:|---:|---:|
| 1 | 4 KiB even control | `0x00004000` | `0x001000` | `0x001000` | 2 |
| 2 | 16 KiB even, bit12=1 | `0x00021000` | `0x011000` | `0x020000` | 5 |
| 3 | 16 KiB odd, bit12=0 | `0x0002c000` | `0x040000` | `0x030000` | 8 |
| 4 | 64 KiB even, bit12=1 | `0x00045000` | `0x055000` | `0x070000` | 11 |
| 5 | 64 KiB odd, bit12=0 | `0x00070000` | `0x0a0000` | `0x080000` | 14 |
| 6 | global 16 KiB odd, ASID mismatch | `0x00084000` | `0x0d0000` | `0x0c0000` | 17 |

For phases 2-6 the fixture places the same instruction word at the fixed-4-KiB guessed physical location as an equal-valued decoy. The actual nested successful RDRAM transaction still occurs only at the PageMask-derived physical address. Mutating the fetch context to the naive guessed address makes the strict transaction join fail closed.

The six executed instruction values were respectively:

```text
0x34091111  0x340a2222  0x340b3333
0x340c4444  0x340d5555  0x340e6666
```

The exact execution also measured synchronized selector values `0x1000`, `0x4000`, and `0x10000`, and normalized masks `0x6000` (16 KiB) and `0x1e000` (64 KiB).

### Negative cases

Phase 7 installs a non-global 16 KiB entry under the wrong ASID. VA `0x00089000` raises TLB-load exception code 2 with `BadVAddr=0x00089000`; no fetch boundary and no eligible uncached-CPU scalar witness occurs.

Phase 8 is the stronger counterexample. VA `0x00091000` is in the actual 16 KiB **even** half because bit 14 is clear, while bit 12 is set. The fixture marks EntryLo0 invalid but EntryLo1 valid and puts an equal instruction at the fixed-bit-12 decoy location. Exact ares raises TLB-load exception code 2 with `BadVAddr=0x00091000` before fetch. A fixed-bit-12 reducer would select the valid opposite half and fabricate a source that the CPU did not execute.

## Independent deterministic model

`experiments/tlb-pagemask/source_model.py` independently implements only the pinned source formulas above and checks PageMask normalization examples also present in n64-systemtest.

It then samples 100,000 deterministic offsets across 16 KiB, 64 KiB, 256 KiB and 1 MiB pages (`seed=0x504c414944`). Fixed-4-KiB reconstruction disagrees with the PageMask-aware `(EntryLo, paddr)` result in **95,784 / 100,000** samples.

Model compact-JSON SHA-256:

```text
a5d4638e35372905086b57571edb56e96d5d682cf78bf11ef606e7bb6765939a
```

This sweep demonstrates the size of the failure surface; it is not reachability evidence.

## Instrumentation neutrality and determinism

The runner builds:

1. an unmodified pinned-reference baseline with the observer compiled out;
2. the observer-capable build with observers disabled;
3. the observer-capable build with observers enabled;
4. a second enabled execution.

The test requires baseline, disabled, and enabled `facts` and `state` to match exactly, and requires the two enabled stdout traces to be byte-identical. The successful run reported:

```text
CPU/state SHA-256: 6abe02c40f092e6d481749bf86520aa8ef38998f6fccc3bc84acb33b58c34ca2
RDRAM SHA-256:     1994864fcac2feb5aa58f4b61cde010b8783968e7e946e364b985e42d5e82889
Count:             6
```

Every positive fetch had exactly one eligible completed four-byte `VR4300_UNCACHED` RDRAM read between its fetch-begin/end events. Failed translations produced neither a fetch pair nor an eligible scalar witness.

## Exact execution receipts

GitHub Actions exact-pin run:

```text
run:            37917557580
job:            113777338541
behavior head:  4895ef9fe99ec352f22f4854fe5853e5f952ecb6
result SHA-256: 486296f8df73a1f0b7ccc2a4849df9130d69084b5bfed4e7c1e2ecc41edaac56
artifact id:    11610251345
artifact SHA:   27dd9bc5f12fc6da64b21852df30d42ca4f89345e4ab134dbc78a19899aa7406
artifact bytes: 1500452
```

The job passed exact-reference checkout guards, Python syntax, the independent model, source guards, both ares builds, the complete execution matrix, repeated-trace determinism, adversarial verifier mutations and artifact upload.

## Result

**VALIDATED** for the bounded pinned-ares scope.

A PageMask-aware current translated physical address composes cleanly with the already validated mapped-uncached backing witness for the tested 16 KiB and 64 KiB cases. Fixed bit-12 / 4-KiB reconstruction is unsound and can both misattribute successful executable bytes and fabricate a successful executable source when the actual selected large-page half is invalid.

For Plaid, the safest integration rule is simpler than reproducing PageMask geometry downstream: preserve the exact translation result and mapping-generation context produced by the translation stage, then join that physical address to the completed backing transaction. If a verifier reconstructs prior mappings later, it must use the exact PageMask-era mapping state, not a permanent 4 KiB assumption.

## Limitations / explicitly not proved

- This is bounded pinned-emulator execution, not a full hardware characterization of every legal/undefined PageMask pattern.
- Dynamic execution covers 4 KiB, 16 KiB and 64 KiB; 256 KiB+ sizes appear only in the deterministic source model.
- The experiment does not resolve overlapping/undefined TLB entries, TLBWR identity, TLBP/TLBR, save/restore/reset mapping epochs, region matching, 64-bit mapped segments, supervisor/user modes or mapping-generation history. The separately active TLBWR lane owns replacement-generation identity.
- CCA=2 identity ordinary RDRAM is the only positive backing class here. Cached I-cache provenance and non-identity/degraded backing remain separate obligations.
- Equal-valued decoys demonstrate why value matching is not provenance; they do not model every possible alias/copy history.
- Successful observed fetch provenance is not exhaustive reachability, indirect-target closure, or a whole-ROM closed-world proof.

## Reproduce

With exact pins checked out under `.refs/`:

```sh
python3 -m py_compile experiments/tlb-pagemask/source_guard.py \
  experiments/tlb-pagemask/source_model.py \
  experiments/tlb-pagemask/run.py
python3 experiments/tlb-pagemask/source_model.py
python3 experiments/tlb-pagemask/run.py
sha256sum target/ares-tlb-pagemask/results.json
```

Expected result JSON SHA-256:

```text
486296f8df73a1f0b7ccc2a4849df9130d69084b5bfed4e7c1e2ecc41edaac56
```
