# RSP IMEM installation lifetime composition

Date: 2026-10-09

Status: **IN PROGRESS**

Canonical Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.

Exact ares pin: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Question

Can one promoted SP-DMA read request plus its ordered completed IMEM sink effects define a bounded RSP executable-installation generation across count/skip rows and modulo-IMEM wrap without incorrectly absorbing interleaved CPU IMEM writes or merging byte-identical reloads?

## Hypothesis

A promoted current request can group only the concrete completed DMA IMEM sink events causally executed while that request is active. The grouping must not imply homogeneous ownership of the whole requested span. Same-value CPU writes create distinct writer generations, same-payload reloads create distinct request generations, and request handoff cannot depend on a BUSY falling edge.

## Experiment

Durable fixture: `spikes/043-ares-rsp-imem-install-lifetime-gpt56sol/`.

The exact-pin source guard requires the already-reproduced upstream `dma.cpp` and `io.cpp` hashes. A generated observer shadow records completed promotion/DMA-sink/CPU-sink/completion boundaries. An uninstrumented baseline, sensor with callbacks disabled, and two repeated traced runs must preserve identical architectural checkpoints. A replay verifier derives per-byte writer generations and attacks forged request IDs, reused generation IDs and missing completion.

Results and receipts will be appended after the isolated workflow executes.
