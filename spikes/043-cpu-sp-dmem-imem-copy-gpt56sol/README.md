# CPU SP DMEM -> IMEM copy provenance spike

This branch-only spike asks one narrow question: can a VR4300-mediated copy from
RSP DMEM to executable RSP IMEM be attributed from actual completed storage
effects plus interpreted register dataflow, rather than from matching values?

Scope:

- exact Plaid base `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`;
- exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`;
- ares CPU and RSP recompilers disabled;
- direct uncached KSEG1 SP aperture only;
- Word `LW` -> `SW` dataflow only;
- actual `RSP::readWord` and `RSP::writeWord` completed-result callbacks;
- no claim of ultimate RSP-origin producer identity, mutation completeness,
  executable lifetime closure, or hardware-wide semantics.

The fixture deliberately includes:

1. a positive `LW t0,DMEM` -> `SW t0,IMEM` copy;
2. an equal-valued DMEM read into `t1` between source load and sink store;
3. a different-value `ORI` clobber of `t0`;
4. an equal-value `ADDU` clobber of `t0`;
5. an out-of-instruction `RSP::writeWord(..., cpu)` sink showing that CPU-thread
   identity does not imply an executing producer instruction;
6. a CPU store back to DMEM, which is a real sink but not an executable IMEM copy;
7. a same-value reload/rewrite to the original IMEM word, which must remain a
   distinct storage generation.

`run.py` also mutates eight recorded histories and requires all forgeries to fail.

## Reproduce

From the Plaid repository root, with the exact ares pin checked out cleanly at
`.refs/ares`:

```bash
python3 spikes/043-cpu-sp-dmem-imem-copy-gpt56sol/run.py
```

The runner builds an unmodified-reference baseline, an observer-disabled shadow,
and two observer-enabled runs. CPU state, SP/RDRAM/hidden-memory hashes and the
executed step ledger must agree between all modes; the two traced byte streams
must match exactly.

Generated build products and `results.json` stay under ignored `target/`.
The runner prints SHA-256 receipts for the event stream, accepted copy
certificates and complete result file.
