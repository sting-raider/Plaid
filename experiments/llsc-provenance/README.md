# LL/SC provenance adversarial experiment

## Question

Can Plaid treat VR4300 LL/SC and LLD/SCD as ordinary stores for executable-byte provenance, and can any one pinned emulator be used as the authority for reservation lifetime/address semantics?

## Hypothesis

SC/SCD need a conditional mutation witness. A mutation may be recorded only after the store actually succeeds. Cached success is initially a D-cache-resident mutation; uncached identity-RDRAM success can become a backing mutation only at the completed backing write. Failed reservation/translation/write paths must not fabricate a mutation.

The experiment also tries to falsify the assumption that the pinned reference implementations agree closely enough to infer hardware LL/SC reservation semantics from emulator consensus.

## Inputs

Exact revisions from `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

The exact source map and limitations are in `research/llsc-provenance.md`.

## Run

```sh
python3 -m py_compile experiments/llsc-provenance/llsc_contract.py
python3 experiments/llsc-provenance/llsc_contract.py
```

The tested harness file SHA-256 is:

```text
d3d94d86e59afce5bdcd1b78c54c6a2233cf4edfe8a77f74e8603628c5055dec
```

The full captured stdout (including the final `REPORT_SHA256` line) had SHA-256:

```text
5d5e0e0fb612e59ee35618972ee9511033178d5d2b35148941a3a17b76811855
```

The canonical JSON body printed by the harness reports:

```text
REPORT_SHA256 2b76d9d77e2d556d13a56385190f30e32c54110a25b6f783f4851e942638fc70
```

## Key counterexamples

1. **LLAddr divergence is immediate.** The pinned ares and Gopher64 source paths write physical `paddr >> 4` on LL/LLD. The pinned Mupen LL/LLD path sets `llbit` but does not update CP0 LLAddr. The pinned n64-systemtest LL/LLD tests explicitly expect physical-address-derived LLAddr.
2. **Successful-SC reservation lifetime diverges.** Pinned Mupen and Gopher64 clear `llbit` after/before a successful SC/SCD write. Pinned ares interpreter SC/SCD only gates on `scc.llbit` and returns the result of `write(...)`; it does not clear `scc.llbit`. The ares cached recompiler path likewise consumes `SccLlbit` for conditional selection without an observed clear at the conditional store. The deterministic repeated-SC model therefore writes twice under ares semantics but only once under Mupen/Gopher semantics.
3. **ERET is an oracle-backed reservation boundary.** The pinned n64-systemtest explicitly expects SC/SCD after ERET to fail while LLAddr remains populated. All three pinned emulator source paths clear their reservation bit on ERET.
4. **Virtual identity is not a sound reservation key.** The pinned n64-systemtest maps two distinct TLB virtual addresses to the same physical page, performs LL through one and SC through the other, and expects success. Plaid must not key a reservation/provenance join by guest virtual address alone.
5. **Reference consensus is not proof.** All three source models gate SC primarily by the reservation bit rather than visibly comparing the current SC physical granule against LLAddr, but the exact pinned n64-systemtest file has no different-physical-address SC case. The experiment therefore leaves that behavior unpromoted rather than manufacturing an N64-wide invariant from three emulators.

## Result

`PARTIAL`.

The provenance obligation is strong enough to adopt: emit an executable mutation only from the actual successful store/cache mutation boundary; failed SC/SCD emits none; cached success stays cache-resident until verified writeback; ERET terminates the reservation; LLAddr/alias reasoning is physical, not virtual.

The precise hardware rule for repeated SC and SC to a different physical reservation granule is not established by a fresh hardware execution in this worker. Those remain open and must not be inferred from the pinned ares behavior.
