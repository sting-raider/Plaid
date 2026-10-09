# 045 - exact ares `SC` to CPU-visible SP sink

Bounded question: does a decoded VR4300 `SC` create an actual SP DMEM/IMEM Word storage effect only on successful conditional-store execution, including same-value success?

This experiment is intentionally Word-only. It does not cover `SCD`, partial stores, COP1 stores, DMA, RSP-origin writes, or hardware-wide LL/SC reservation semantics.

## Exact references

- Plaid canonical baseline: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 source comparison: `e96debac941a26ba4961e5145056c0821d3a56f7`

## Cases

For both DMEM (`0xffffffffa4000000`) and IMEM (`0xffffffffa4001000`):

1. `SC` with no linked load, expected no sink;
2. real aligned `LL` followed by misaligned `SC +1`, expected AddressStore and no sink;
3. real aligned `LL`, `XORI` transformation, aligned `SC`, expected one changed-value Word sink;
4. real aligned `LL`, aligned `SC` with no payload change, expected one same-value Word sink.

The fixture then performs one equal-valued direct CPU SP write outside any decoded-instruction context. It is an adversarial decoy: value/address equality alone must not steal `SC` provenance.

## Reproduce

With exact refs checked out under `.refs/`:

```sh
python3 -m py_compile spikes/045-ares-cpu-sc-sp-sink/*.py
python3 spikes/045-ares-cpu-sc-sp-sink/run.py
```

The runner builds an uninstrumented baseline and an SP-sink-observer build, requires architectural facts to match, requires two instrumented traces to be byte-identical, verifies the exact sink/context matrix, and rejects forged histories.
