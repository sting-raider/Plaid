# Completed guest cache-operation witnesses

2026-10-08. Hypothesis: sampling the selected line around the existing CACHE
handler can retain the mutation boundary exposed by spike 013, without another
guest access or clock. The optional generated interpreter TU copies tag/eight
words before the switch and samples the result after it, preserving instruction
PC and effective virtual/physical operand addresses. The hook selects instruction-
cache index invalidate, store tag, hit invalidate, fill and writeback. Failed
translation returns before the observer. No extra memory/coherence/translation
helper or step is called; all reference artifacts remain ignored and licensed.

Spike 014 measures tag-store/index-invalidate cases only, reusing original guest
instructions from spike 013. Exact transitions are 1→0x4001, 0x4001→0x4000 and
0x4001→1, with the same eight words before/after and completed-fill counts 1/1/2.
PCs are uncached 0xffffffffa0002000/2004/2008; effective operands name physical
0x4000/0x4000/0 and selected slot 0. The two prior fills and seven fetched guest
instructions remain, including the retagged-data counterexamples.

Plain/traced/repeated CPU/COP0/timing/RAM/cache checkpoints match spike 013's
separately built baseline goldens. JSON repeats exactly. Count=103, hits=2,
misses=2, s0=9; all GPR/HI/LO/PC, exception, status/configuration and full RAM/cache
hashes agree. The default generated header/handler omits this optional observer.
The complete prior JSON projection has SHA-256
`4ffd0952041adf8b8b79bfb5f941594531a4e061db7cb862e6d1a846e0407ebe`.
A fresh default-observer spike 013 rebuild also preserves every prior golden.

Operation completion supplies a finite transition witness, not proof of a
successful backing-memory writeback. Hit/miss, explicit fill and writeback cases
need separate tests, as do reset/restore boundaries, actual RAM/ROM bus sources
and ordering across fill/mutation/fetch/copy events. This research does not yet
construct a cache lifecycle, executable image, generation or native artifact.
