# Finite SP-DMA RDRAM-to-DMEM lane contract

Run `python spikes/051-ares-sp-dma-dmem-ingress/test_verify.py` for independent
synthetic contracts, or `python spikes/051-ares-sp-dma-dmem-ingress/run.py` for
exact pinned ares execution (g++/Ubuntu WSL on Windows).

The project-owned ISC driver comes from exact research branch
`research/sp-dma-dmem-ingress-gpt56sol` head
`7041402beb2ce63a43336ae627372098af50ff0f`. Its six controlled cases exercise
equal-valued source words, same-value reload, count/skip, 4-KiB DMEM wrap,
out-of-bounds zero sinks and a direct same-value CPU-visible Word write.
Requests are staged through real SP MMIO methods and advanced by direct
`dmaTransferStep` calls; this is not a guest scheduler or decoded CPU producer.

The runner guards five exact reference source blobs and a clean pinned checkout.
Observers in ignored generated shadows record successful identity-RDRAM Word
reads and completed DMEM Word sinks. They add no guest access or clock step.
The verifier checks every typed field of the independent 27-record census and
the reported checkpoints/digests. Ares batches two reads before either sink;
equal value or nearest read cannot select the first source. Sink callback source
addresses come from the exact statement/transfer lane. Gopher64's different
read/write interleaving is source-only context, not an executed second oracle.

Reported state agrees across unmodified, disabled-observer and enabled builds;
enabled traces repeat identically. These snapshots cover fourteen Word
checkpoints, DMEM/IMEM/RDRAM raw-storage digests and DMA busy/full, not all machine
state. The finite replay reports distinct local writers and successful source
read identities; it does not establish the earlier ancestry of RDRAM storage.
Out-of-bounds sinks keep unknown source identities. The direct overwrite replaces
only four bytes despite equal payload.

Twelve measured mutations reject. All effect payloads and schemas are also
independently attacked by synthetic tests. No raw branch reducer/workflow is
adopted; no upstream implementation, ROM or firmware is tracked. Generated core
ISC/SLJIT BSD notices stay under ignored output. Producer census, DMA request
lifecycle, decoded CPU producer, executable lifetime and native completeness
remain uncertified.
