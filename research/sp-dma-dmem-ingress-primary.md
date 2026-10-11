# Primary harvest: finite forward SP-DMA DMEM ingress

2026-10-11. Source contract reconciled under spike 051; no general certificate.

Reviewed complete driver/runner/note and closeout 6079016567 at
`research/sp-dma-dmem-ingress-gpt56sol` exact head
`7041402beb2ce63a43336ae627372098af50ff0f`. Authenticated successful final-head
Actions 37916920825 and earlier 37916353399; both historical results hash to
`618b9def7180d8eec2624d348bd33e7c1d99b836d8b767439dd966bca04861b1`.
The original project-owned ISC driver is unchanged in main's numbered fixture.

Fresh clean exact-ares execution reproduces all 27 records: twelve successful
RDRAM Word reads, fourteen completed DMEM DMA Word sinks and one direct Word
sink. All event values/addresses/lanes and the reported state match historical
execution. Fourteen Word checkpoints, raw DMEM/IMEM/RDRAM storage hashes and
DMA busy/full agree across unmodified, observer-disabled and enabled builds.
Two enabled runs have identical stdout. This is a selected reported-state
neutrality check, not equality of every machine field or full timing coverage.

The first sink (ordinal 3) consumes successful read 1 at 0x1000, while its
nearest equal-valued read is ordinal 2 at 0x1004. The six measured eight-byte
fragments preserve both Word lanes even though ares reads both before writing
either. Reloads advance local sink generations; count/skip excludes poison
Words; 4-KiB wrap resolves completed sinks; OOB zero sinks have no successful
read identity. The same-value direct CPU-visible write replaces four bytes,
while adjacent DMA-written bytes retain their earlier source read.

Primary audit of the original runner accepts a matched changed payload at
source/read and sink 0x3014, ordinal 1 as boolean True and extra source metadata.
The reconciled independent typed census rejects these plus the five original
attacks and additional wrap/OOB/width/checkpoint attacks: twelve measured
forgeries total. Six synthetic tests also check every effect payload/schema,
missing/extra sinks and boolean reported-state fields. Full plaid-core, fmt
and strict locked workspace/all-target Clippy pass.

Fresh raw trace SHA-256:
`b38f44902eb82b2a23caa1cc9465405e59ffb749415345d8ed72aff6dd67835e`.
Primary schema-0 result SHA-256:
`169ae68d834c56ffa8648c4a81967ac9f3841511b08937d534d630866ef5b2c4`.
Reproduce with `python spikes/051-ares-sp-dma-dmem-ingress/run.py`; generated
references, traces and notices remain beneath ignored output.

Five exact ares source blobs are guarded. Source inspection covers successful
identity-RDRAM bounds checks, actual paired transfer statements, direct SP
routing and count/skip/bank wrap. Exact Gopher64 RSP-interface source SHA-256
`a5864c02f742bc922284d7866bbe76fe80efda63d3a3c69af7e37c50fe661053`
at `e96debac941a26ba4961e5145056c0821d3a56f7` corroborates four-byte accounting
but interleaves reads/writes. It was source-inspected, not executed; no GPL
implementation is imported. Ares ISC/SLJIT BSD notices remain ignored. Original
project observer recipes generate shadows only, with no new reference guest
access or clock step and no upstream implementation tracked.

Disposition: retain the strict finite fixture and measured adversaries. The
older branch reducer is superseded as a validator; historical behavior remains
evidence. This is direct component scheduling and a directly staged CPU-visible
Word write, not a decoded guest writer, request-token or complete lifecycle
certificate. Successful source reads do not establish earlier RDRAM storage
ancestry. General producer/census, translated/degraded paths, combined RSP/CPU
dataflow, executable consumption/lifetime and native/whole-ROM closure stay
OPEN. No progress milestone changes.
