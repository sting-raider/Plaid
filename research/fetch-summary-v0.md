# Conservative raw fetch summaries

2026-10-08. Hypothesis: complete finite fetch captures can be summarized into a
deterministic ProgramMap without truncating 64-bit PCs or manufacturing code
generation/copy/retirement identity, while preserving verifiable raw provenance.

The streaming reader accepts only the pinned ares research v0 format/revision,
declared SP entry, 1..10,000,000 instruction-call budget and explicit budget-stop
footer. Records are bounded to one MiB; unknown/duplicate fields, unaligned PCs,
noncontiguous sequences, mismatched ROM hashes/counts and truncated/trailing data
fail. SHA-256 covers the exact complete raw bytes, including formatting. Integer
consumers must preserve full u64 PC and event-index precision.

`FetchCapture` is keyed by `fetch:<raw SHA256>`. `ObservedFetch` retains raw
`GuestVirtualAddr(u64)`, word, delay-slot flag, capture identity and exact first/
last indices plus occurrence count for that tuple. First/last are not a continuous
range; the summary does not reproduce every intermediate sequence position or
memory epoch. Keep the complete raw file for source verification and future
chronological joins. Distinct words/slots/captures remain separate. Validators
check provenance, budget/count conservation, semantic uniqueness and endpoint
witnesses. The source rechecker rebuilds all summaries, detecting altered words,
counts, indices or capture metadata. Merge is commutative/idempotent and preserves
capture identity; legacy maps default the additive fields.

No blocks, executable roots, DMA, source mappings or generations are fabricated.
The solver independently emits `fetch_execution_identity_unknown`, even after
diagnostics are erased and the map is merged into an otherwise closed finite
integer CFG. All whole-ROM reports remain OPEN and native_complete=false.

Reproduce small and broad checks:

```text
python scripts/test_fetch.py
python scripts/test_fetch_corpus.py
```

The broad check requires spike 004's ignored complete capture. Its 465,553,451
bytes and 4,999,998 fetches produce 53,037 summaries in a 20,053,874-byte map.
All counts are conserved, full-source rechecking passes, self-merge is byte-exact
and the solver stays OPEN. This prefix has no differing words or slot states at
the same PC; explicit synthetic tests cover those variants and wider-mode PCs.

One Windows/Rust 1.98 debug import under concurrent verification measured 75.7
seconds and 74,719,232 bytes peak process working set. The ignored
`target/ares-fetch-spike/import-metrics.json` records the invocation. This is a
single-host cost baseline with concurrent load, not an isolated throughput,
optimization or scalability result. Raw data remains an additional required
artifact; summary size is not a claim of lossless chronological compression.

Next: capture actual physical fetch access, verify cartridge backing explicitly,
and join contextual snapshots/mutations/copies into executable identities. Do not
derive those from PC truncation, byte similarity or the first/last sample span.
