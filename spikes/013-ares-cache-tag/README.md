# Guest CACHE tag mutations

Hypothesis: a later effective fetch page can differ from the last fill's burst
page, because guest CACHE index-store-tag can retag resident words without a new
bus burst. Execute original guest CACHE opcodes between
cached fetches, retaining complete baseline/plain/traced/repeated checkpoints.
The baseline reference build has no fill callback.

Run `python spikes/013-ares-cache-tag/run.py`.

## Verdict: VALIDATED counterexample to using the current tag as byte origin

### Evidence

The fixture retags page 0 to page 0x4000, invalidates/refills, then retags back.
Seven fetched guest instructions cause two fills. Two cached fetches use resident
words whose last fill belongs to another physical page: effective PA 0x4000 uses
word 0x24100001 filled at burst 0; effective PA 0 uses word 0x24100009 filled at
burst 0x4000. Guest tag stores change tags without changing words or fill count;
guest invalidation forces the next refill. Baseline without a fill callback,
instrumented plain/traced/repeated CPU/COP0/timing/RAM/cache checkpoints agree.
Repeated JSON is exact. Count=103, hits=2, misses=2 and s0=9. Fixed RAM SHA-256:
`acadcf93aed6b50df4253efb0a898bef4aa107253e68c3a2038a75315a65db82`.
Cache SHA-256: `f1fae837b5c53982dab46e78c4aa73ed3b082f54c63b8bf26b2578c12c5d315e`.

### Constraints and surprises

Host setup supplies TagLo/target registers and fixed instruction entry PCs;
guest CACHE instructions perform every observed tag/invalidation mutation.
This is a controlled integer/cache scope, with both recompilers disabled.
No RAM/ROM backing, broad boot coverage or executable lifetime is certified.

### Recommendation

Keep effective fetch/tag addresses separate from the historical origin of
resident words. Tag stores preserve prior data, so an observed prior fill remains
a candidate byte-history event; its backing source still needs witnesses.
Track tag/invalidation boundaries explicitly before general lifecycle joins.
