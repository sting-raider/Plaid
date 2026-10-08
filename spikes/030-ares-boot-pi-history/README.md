# Bounded boot PI source contexts

Hypothesis: real boot PI transfers can retain actual ROM half-read, buffer-lane
and successful destination contexts while preserving the complete v0 history
projection, v5 fetch stream and reference checkpoints. Data-copy return and later
scheduled busy/interrupt completion must remain separate.

```powershell
python spikes/030-ares-boot-pi-history/run.py
python spikes/030-ares-boot-pi-history/run.py --verify-existing
python spikes/030-ares-boot-pi-history/test_verifier.py
```

This opts into research history v1, which production v0 inspection must reject.
Original sensors sample existing results only. Reference code/firmware/ROM/traces
remain ignored and separately licensed. NTSC/6102/8-MiB/deterministic/PIF-HLE,
single-run capture and a finite instruction-call budget bound the scope.

## Verdict: VALIDATED

### Evidence

- The 610,000-call capture and repeated stream retain 8,823,134 records and
  1,638,808 successful PI byte writes, all joined through consumed buffer lanes
  to exact canonical ROM origins. Four copy calls return; three actual status
  transitions occur. Final reference DMA busy is 1; completion stays uncertified.
- Complete v0 projection (3,881,089 records), complete v5 bytes and all reported
  baseline/disabled/repeated machine checkpoints agree. The separate original PI
  build supplies the baseline. No guest-test completion is claimed.
- The 10,000-call preflight also passes; 17 forged protocol/metadata/context cases
  fail. Production v0 rejects research v1; projected v0 inspection/rechecking pass.
- V1 SHA-256:
  `994d62686ff5d57a0a9a26ab6bc8454c6026d79c3bd069d1c921513431cfc7af`.
- `spikes/006-ares-rom-source/run.py` reproduces its prior three known/three
  unknown source cases with independent original/disabled/repeated state.

### Constraints and surprises

- A finite stop may leave scheduled completion pending despite completed writes.
- The status callback reports the observer's last unfinished write context;
  queued read/write identity, replacement and guest cancellation are not sensed.
  Reports count actual status transitions without certifying transfer completion.
- General copies, RAM/cache/restore lifetimes and mutation completeness stay open.

### Recommendation

- Validate complete versioned sources before considering original production
  inspection; never promote finite origins to executable lifetime certificates.
