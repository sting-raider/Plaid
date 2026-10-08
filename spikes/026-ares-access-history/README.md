# Shared fetch access history

Hypothesis: given the unchanged controlled CACHE fixture, adding completed
identity-RAM scalar read/write callbacks and successful fetch begin/end callbacks
to the existing ledger can identify the actual uncached word-read interval while
preserving the complete previous trace projection and reported machine state.

```powershell
python spikes/026-ares-access-history/test_recipe.py
python spikes/026-ares-access-history/run.py
python spikes/026-ares-access-history/test_primitives.py
```

The shared spike-003 builder makes the two new sensors explicit opt-in options.
They coexist with burst/fill/completed-CACHE callbacks in ignored generated
headers/TUs. Both recompilers stay disabled. Callbacks use existing successful
results/fields, with no additional guest reads, translations or clocks. Default
builds retain original handlers and no scalar/fetch-boundary callbacks.

The controlled history includes fixture/debugger scalar writes with explicit
attribution, not guest store claims. The independently recovered scalar-fetch
and CPU-copy fixtures additionally exercise the shared builder and demand exact
agreement with their earlier complete JSON, including real guest data reads and
stores. All generated reference code, executable files and results stay ignored;
the pinned ISC/BSD reference is compiled separately with its LICENSE preserved.

## Verdict: VALIDATED for the declared fixtures

### Evidence

- Six recipe/reuse combinations pass without compiling a CPU. They check sensor
  combinations and removal of stale RAM shadows.
- Independent baseline, callbacks-disabled and repeated enabled reference runs
  pass on x64 WSL Ubuntu/G++ 15.2. The 95 records include 34 boundary records,
  nine scalar fetch reads and nine attributed fixture writes. Every payload is
  referenced once; all nine uncached reads lie inside their fetch interval.
- Removing only the new access records restores the exact earlier 43-record
  history and complete trace projection. Count 257 and full RAM/I-cache hashes
  are unchanged; six forged contexts/read histories fail.
- Shared fetch/copy builds pass every independent original fixture check and
  retain complete earlier traced JSON, including the equal-valued data decoy,
  unsupported source paths and stale cached copy/writeback sequence.
- Controlled semantic JSON SHA-256:
  `80e20d26822fc2ad3bdd9a4911b3baee8d8d2730bea3f352f0e82303248cee4e`.

### Constraints and surprises

- This checks one finite identity-RAM fixture and separately reproduced primitive
  fixtures. It supplies neither a complete mutation census nor arbitrary-ROM
  causality, execution-mode, cache lifetime or byte-origin closure.
- Boundaries bracket successful `CPU::fetch` accesses after endian address
  selection; translation failures have no boundary or backing witness.
- RAM callbacks deliberately exclude nonidentity/degraded/failed/EBUS paths.
- Reported checkpoint agreement covers the retained fields, not all device/FPU
  state. Host fixture writes remain separate from guest CPU instructions.

### Recommendation

Extend the same contexts to a bounded boot
capture while retaining prior streams and checkpoints exactly. Keep production
source/image/lifetime promotion and whole-ROM closure separate.
