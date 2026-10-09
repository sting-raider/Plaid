# Exact ares adjacent CPU-copy dataflow

Question: can the existing completed identity-RDRAM transaction witness be joined to actual interpreted CPU instruction/register state strongly enough to certify a deliberately narrow adjacent `LW/LWU rt -> SW rt` copy without relying on equal values?

This spike composes two observational boundaries against pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` with recompilers disabled:

- completed identity-mapped scalar RDRAM transactions;
- interpreter instruction begin/end boundaries with the exact fetched instruction and complete GPR snapshots.

One monotonic ordinal orders both event families. The verifier emits a copy certificate only when the immediately previous decoded instruction is a successful `LW` or `LWU`, its one completed uncached Word read matches the effective backing address, its destination GPR has the architectural sign/zero-extended result at instruction end, and the immediately following `SW` reads that same GPR and produces one matching completed uncached Word write.

Adversaries are part of the contract:

1. equal-valued second load before the store;
2. equal-valued `ORI` clobber between load and store;
3. a `NOP` gap, intentionally outside this tiny certificate;
4. a misaligned failed load with no successful backing transaction;
5. forged load backing address;
6. forged store source register;
7. fabricated successful read for the failed load.

The equal-value decoy is designed so a nearest-equal-value reducer chooses the wrong source address. Matching data is therefore explicitly demonstrated to be weaker than causal instruction/dataflow identity.

Run from a Plaid checkout containing `.refs/ares` at the exact pinned revision:

```sh
python3 spikes/043-ares-cpu-copy-dataflow-gpt56sol/run.py
```

Expected successful final line:

```text
PASS exact interpreted adjacent LW/LWU->SW dataflow; equal-value decoy/clobber/gap and failed load stay uncertified
```

The runner builds an unmodified-reference baseline, generated observer-disabled build, observer-enabled build and a repeated enabled run. Reported facts/state must agree across baseline/disabled/enabled, and repeated trace output must be byte-identical. Generated reference shadows and build products stay under ignored `target/`; the pinned reference checkout is required clean and unmodified.

This does **not** certify general CPU-copy provenance. It deliberately excludes non-adjacent dataflow, branches/delay slots, transformations, byte/half/double/unaligned/merge loads and stores, cached source/destination residency, TLB/remapped/degraded paths, exceptions after successful loads, recompilers, and executable lifetime/closure.
