# SP-DMA -> RSP -> CPU -> IMEM provenance composition

This bounded model composes three already-validated Plaid research contracts:

1. successful RDRAM source transaction -> forward SP-DMA DMEM writer generation;
2. RSP scalar DMEM load -> live GPR generation -> scalar DMEM store;
3. CPU DMEM `LW` -> live GPR generation -> IMEM `SW` -> RSP fetch.

It does not emulate N64 execution and does not claim new hardware behavior. The point is to attack the join: can ultimate byte provenance survive all three transformations without confusing equal values with identity?

Run:

```sh
python3 experiments/spdma-rsp-cpu-imem-chain/source_guard.py
python3 experiments/spdma-rsp-cpu-imem-chain/model.py
```

The model includes same-value DMA reloads, an equal-valued source decoy, same-value RSP rewrites, a same-value one-byte CPU overwrite, a completed DMA sink with no successful source read, a same-value RSP GPR clobber, and an equal-valued CPU-copy decoy. It also constructs two valid histories with identical downstream writer/resident/fetch projections but different RDRAM source backing identities.
