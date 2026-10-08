# PI writers and resident fetch history

Hypothesis: successful buffered PI byte writers can explain an actual RAM fetch
or completed cache fill, but a later reload must not replace the origin retained
by a still-valid instruction cache line. Partial writes need per-byte origins.

```powershell
python spikes/029-ares-pi-fetch-history/run.py
```

Original toy ROMs and direct PI component setup exercise identical and changed
reloads, actual CPU uncached SW, guest CACHE invalidation and a three-byte reload.
The CPU executes each fetched ORI/NOP/control instruction; PI setup/completion
remains a host fixture and proves no guest DMA scheduling. Observers sample only
existing results/fields. Generated reference code remains separately licensed,
ignored and outside Plaid core. No installation/lifetime certificate is issued.

## Verdict: VALIDATED

### Evidence

- The command passes on pinned ares with both recompilers disabled: 481 ordered
  records, 99 successful PI byte writers, 16 actual CPU fetches, three RAM-backed
  fills and two completed guest invalidations.
- A separately compiled original-source baseline, disabled sensors and exact
  repeated traces preserve every reported checkpoint, GPR/HI/LO/PC/Count/exception,
  full RAM/hidden hashes and all instruction cache data/tags. Count is 970.
- Seven forged chronology cases fail; equal-source substitution and ambiguous
  scalar reads conservatively remove origins. Mixed partial words retain each
  byte's writer and cannot claim a contiguous canonical ROM source.
- Complete result SHA-256:
  `b98481bdccdd2e408048fa82342dd7505d8e14815fe642d9cc1fac72c2e9a68f`.

### Constraints and surprises

- Backing bytes and resident cache bytes have separate histories.
- Equal words cannot identify a reload, and a mixed-origin word need not have a
  contiguous canonical ROM origin.
- Identity RAM and a single controlled capture without restores bound the scope.

### Recommendation

- Preserve source writers through actual read/fill contexts before deciding any
  broader boot schema or executable lifetime representation.
