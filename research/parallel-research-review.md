# Parallel research reconciliation

2026-10-08. The primary checkout fetched the integration instructions through
`3cf45dc`, read issue #4 and inspected all 17 available research branch tips.
Useful notes and original fixtures are transplanted individually; stale branch
state, production changes and branch-only CI workflows are not merged wholesale.
The source pins and licensing boundaries remain unchanged.

2026-10-09 follow-up: the primary fetched and reviewed the new PI, SP lifecycle
and PIF backing branches plus issue #4 closeouts. Useful original notes/fixtures
are retained individually. Branch-only workflows remain outside integration;
historical receipts retain their original policy/scope. The user moved canonical
integration to `main`; `codex/executable-discovery` is now a checkpoint.

| Additional research branch | Inspected tip | Supplied evidence |
| --- | --- | --- |
| `pi-queue-dispatch-gpt56sol` | `ef26a90` | Source guard, fuzz model and actual pinned PI write/CPU dispatch fixture |
| `pi-request-queue-dispatch-gpt56sol` | `2e2bd82` | Actual queue with source-guarded synthetic PI lifecycle |
| `pi-causal-token-gpt56sol` | `26e8360` | Source-guarded C++ extraction with optimized/sanitized differential fuzz |
| `pi-dispatch-sidecar-20261008` | `06c5243` | 200,000-operation identity model and save-only evidence-loss counterexample |
| `sp-dma-lifecycle-gpt56sol` | `ab98ece` | Actual SP pending mutation/row/handoff/wrap fixture; three-reference source comparison |
| `pif-rom-backing-ares-gpt56sol` | `983b8f5` | Actual PIF backing fetch-stage sensor with nine adversaries |

The COP1 store branch subsequently reached `b95a51d` with its durable validated
note and exact-reference receipt. Primary reproduction now passes the payload
model and all 192 repeated handler cases, retaining cache/backing and endian/
fault limits. Adopt the general concrete mutation-sensing obligation under
ADR-0061; reference callback decomposition remains hardware-unresolved.

Primary PI reproduction passes all four recovered contracts. The actual write
fixture reproduces trace SHA-256
`a52ac2df67c03f4bbc68fe26c9a8ac09113212a9c6971af556d02d892d5d300c`
and result SHA-256
`3b5b3850b35dd26ad728b5bac49eb1e8791f4b749d2aba11c09ee73ae4af9b6d`
exactly. The actual-queue lifecycle receipt remains
`ca8d5b75da19f00f2a4b4963de65cca9c82a10d757c190baa6f01797cecc69d0`.
The causal extraction reproduces all 1,280,000 differential operations under
optimized and ASan/UBSan builds, stdout SHA-256
`8f49c659443569004ccc17e377988cdac70d17cb33df669f37ac69667c0f0424`.
The 200,000-operation sidecar model repeats its visible-state digest exactly;
the other fuzz model repeats canonical report digest
`ebab07300e683fa8d555f0fc4228fe3627b04bd261778373594be76cb3be0b27`.
Its Windows receipt encoding differs from the worker's Linux file while the
canonical model report agrees. Local adapters fix CRLF pin checking/WSL paths
and preserve the generated fixture include graph. Shared opt-in generation now
owns queue headers, so the recovered actual runner requests that option explicitly.

Adopt request identity before insertion, explicit scheduling failure, exact valid
removal/CPU dispatch and distinct data effects. Preserve unknowns for unbound,
canceled and restored identities. The primary save-only fix and explicit read/
write dispatch-scope fixture have separate receipts in their topic notes. None
of these results promotes boot history v1 completion or whole-ROM closure.

Primary SP reproduction passes the actual descriptor mutation/row/handoff/wrap
fixture with exact stdout/result hashes from the worker. Canonical LF source
digests and inspected-file guards preserve unrelated reference instrumentation.
Mupen/Gopher remain source-only evidence, and FULL-policy hardware disagreement
remains unresolved. Adopt lifecycle obligations under ADR-0059.

Primary PIF backing reproduction passes all nine actual fetch-stage adversaries,
matching the synthetic worker result hash exactly. All nine also pass with the
known supplied NTSC firmware and independent baseline/repeated checkpoints.
The topic note records both ignored-result digests. Adopt actual in-context
backing reads and separate physical/source identity under ADR-0060, retaining
complete boot, firmware authenticity, lifetime and production schema gaps.

| Research branch under `origin/research/` | Inspected tip | Evidence supplied by worker |
| --- | --- | --- |
| `ares-fill-rdram-join-gpt56` | `e8823d1` | Standalone chronology model; reference execution pending |
| `unified-cache-order-gpt56` | `58fa683` | Interleaving model and pinned-source guard |
| `icache-reset-restore-gpt56` | `61170d0` | Restore counterexample model and prepared reference fixture |
| `reset-cache-lifetime-20261008` | `bd5c9d6` | Source-derived NMI/reset/restore model |
| `pointer-table-alias-gpt56` | `ef31dc6` | Physical-alias and stale-D-cache counterexamples |
| `cpu-copy-provenance-g56` | `294b6e1` | Exact-unit adjacent-load/store contract model |
| `cpu-copy-rdram-gpt56sol` | `9760f94` | Executed uncached/cached copy transaction fixture |
| `ares-rdram-uncached-fetch-gpt56sol` | `77a2682` | Executed scalar-read/fetch-context fixture; includes recovered copy work |
| `uncached-rdram-fetch-gpt56` | `14276f7` | Earlier context contract and source guard |
| `exception-vector-roots-gpt56sol` | `e58a31c` | Executed 28-case mode-sensitive exception matrix |
| `rsp-imem-provenance-20261008` | `3b66722` | Executed IMEM DMA/reload/direct-write/fetch chronology |
| `pif-rom-backing-gpt56sol` | `3a9c557` | Source-selection model and one-million-case deterministic fuzzing |
| `sp-fetch-backing-gpt56` | `b211271` | Source-derived DMEM/IMEM/mutation contract |
| `swl-swr-byte-mutations-gpt56` | `f1a0b51` | Partial-store model, expected systemtest vectors and C++ dirty-mask probe |
| `64bit-store-mutation-gpt56` | `8b1e9d4` | Executed 158-case cached/uncached SD/SDL/SDR matrix |
| `sd-sdl-sdr-mutation-gpt56` | `34ee849` | Executed independent 98-case SD/SDL/SDR byte-effect matrix |
| `llsc-provenance-gpt56sol` | `8abead9` | Source-derived reference disagreement and mutation contract |

The worker notes retain their original verdicts and run receipts. "Executed" in
this table describes the supplied remote evidence, not independent local
reproduction. Local results below distinguish those levels explicitly.

## Findings adopted for the next implementation

1. Retain one raw chronology plus explicit causal access context. An uncached
   data load shares the CPU requestor and can return the same value as a fetch.
   A requestor/address/value match alone cannot select the instruction's source.
2. Separate backing bytes, D-cache resident bytes and I-cache resident words.
   Cached stores/copies may change only D-cache until later writeback. Current
   source RAM can differ from the bytes loaded earlier. I-cache retags can change
   the effective hit page while retaining historical fill data.
3. Preserve exact successful byte mutations and ordered subwrites. Partial stores
   do not generate read provenance for untouched lanes. The pinned ares dirty
   mask is not an exact byte-lane witness for every SWR case.
4. Distinguish NMI, cache power, backing reset and analysis savestate restore.
   Restore installs serialized resident state without a contemporaneous fill;
   exploration needs explicit checkpoint/restore provenance or a new capture.
5. Pointer-table proof must cover actual load sources, cache state, mappings and
   physical aliases. Excluding writes to one virtual range or backing alone is
   insufficient. Current table candidates remain uncertified.
6. Model exception roots by exception class and proven execution mode. Preserve
   independent handler-byte/reachability obligations. RSP content hashes likewise
   cannot replace latest-writer/transfer/generation provenance.
7. Keep source classes and reference disagreements visible. PIF latch/lockout/RAM,
   SP bank selection, degraded/failed RDRAM and conditional-store reservation
   disagreements need their own evidence; no emulator consensus is fabricated.

## Primary-checkout reproduction

`python scripts/test_research_contracts.py` runs the retained models and source
guards. These tests exercise counterexamples, not reference CPU execution.
The PIF fuzzing reproduces 92,583 positive/907,417 negative cases and 92,426
mirrored positives. The compiled dirty-mask probe reproduces the four reported
mask pairs. Two portability defects were fixed: scope the ordinary-RDRAM guard
to its read method, and include `initializer_list` in the C++ probe.

The newly executed `spikes/018-ares-ordered-history/` separately measures all
43 controlled callback records with independent baseline and prior projection
agreement. It closes the workers' shared-order execution gap for that fixture.
It does not prove general completeness, lifetime or all scalar backing paths.

Local reference reproduction now passes for synchronized cache restore/power,
scalar-fetch contexts, scalar/cached CPU copies, RSP IMEM chronology, all 28
exception cases, and both independent 158/98-case 64-bit store matrices. Each
topic note records the primary-host receipt and its bounded scope. Forced endian
handler contexts do not establish legal guest mode transitions; reported-field
neutrality does not compare unreported machine state. The PIF/SP backing, NMI/
system-reset, pointer-table and LL/SC findings remain source/model evidence.

All 76 Rust integration tests, formatting, strict Clippy and the existing CLI
fetch/boot/cache checks pass at this integration milestone. No production schema
or solver gate changes. Every whole-ROM report remains OPEN with
`native_complete=false`. Next, integrate explicit fetch access boundaries with
the measured shared chronology before extending the bounded boot capture.
