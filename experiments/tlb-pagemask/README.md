# Large-PageMask mapped-fetch experiment

Status: executable fixture prepared; exact-pin Actions execution is the authority for the dynamic result.

This experiment extends the already validated 4 KiB mapped-uncached fetch witness to nonzero VR4300 `PageMask` values without changing production Plaid code.

## Falsifiable question

Can a mapped executable-byte witness reconstruct the selected TLB half with fixed virtual bit 12 and the page offset with `vaddr & 0xfff`?

The fixture is designed to reject that rule. Pinned ares derives `addressMaskLo` and `addressSelect` from the synchronized `PageMask`; a 16 KiB mapping selects halves with bit 14 and a 64 KiB mapping with bit 16. Equal-valued decoy instructions are installed at the addresses that a fixed-4-KiB rule would choose.

The matrix contains:

- 4 KiB control where both rules agree;
- 16 KiB even page with virtual bit 12 set;
- 16 KiB odd page with virtual bit 12 clear;
- 64 KiB even page with virtual bit 12 set and a 0x5000 in-page offset;
- 64 KiB odd page with virtual bit 12 clear;
- global 16 KiB odd mapping under an ASID mismatch;
- non-global 16 KiB ASID mismatch that must stop before fetch;
- invalid actual 16 KiB even half while the fixed-bit-12-selected odd half is valid and contains an equal-valued decoy.

Successful fetches reuse the existing neutrality-tested scalar-RDRAM/fetch-boundary observer. The verifier accepts a byte-origin witness only from the one completed uncached RDRAM read nested inside the actual fetch interval at the actual translated/bus physical address. It separately demonstrates that substituting the fixed-4-KiB guessed address destroys that join.

## Exact references

- Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

Pinned n64-systemtest independently names `0b11 << 13` as 16 KiB and `0b1111 << 13` as 64 KiB in its TLB PageMask tests and checks malformed-mask normalization.

## Reproduce

With exact references checked out at `.refs/ares` and `.refs/n64-systemtest`:

```sh
python3 -m py_compile experiments/tlb-pagemask/source_guard.py \
  experiments/tlb-pagemask/source_model.py \
  experiments/tlb-pagemask/run.py
python3 experiments/tlb-pagemask/source_model.py
python3 experiments/tlb-pagemask/run.py
```

Generated pinned-reference build products and result JSON stay under `target/ares-tlb-pagemask/` and are not committed.
