# Executed XORI/cache visibility controls

Reconciles the project-owned ISC fixture from
`research/xori-cache-fetch-compose-gpt56sol` at
`20c342f6255ac93c7c0e04a066124313d4dfb42e`. Run:

```text
python spikes/048-ares-xori-cache-visibility/test_verify.py
python spikes/048-ares-xori-cache-visibility/run.py
```

The reference command uses WSL Ubuntu on Windows, the shared 003 builder and
unmodified ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`. Both recompilers
are disabled; synthetic identity RDRAM, NTSC/6102, deterministic entropy and
8-MiB RAM bound the fixture. No observer callbacks or reference patches are
requested. Two executions must report identical facts.

Four scenarios run actual LW/XORI/cached SW/CACHE instructions: ordinary
writeback then refill, a subsequent identical uncached writer, refill before
writeback, and XORI zero. Cached store and writeback leave the resident old
instruction executable. An early refill also remains old after backing changes.
The normal, foreign and identity scenarios execute new bits after later refill.
The foreign writer shows why identical final bits cannot identify a producer.

`verify.py` checks exactly 22 typed behavioral fields against independently
declared expectations. Four synthetic tests retain stale-cache, early-refill,
type and extra-certificate negatives. Ignored output lives under
`target/ares-xori-cache-visibility-primary/`. Its schema-0 result SHA-256 is
`0f9ddcca1413a844786768f0350d70d66190616e914e2b3b07f8f59f07517f59`;
compact fact SHA-256 is
`707e06fecb81975e8e611b13cfc55f6cdc28ab1916975f8ab105eaf083e51910`.

These are selected behavioral checkpoints, not a captured generation history or
full machine-state comparison. The branch's abstract replay is reviewed in
`research/xori-cache-primary.md`, not imported as a production verifier.
Producer ancestry, mutation census, executable lifetime and native completeness
remain explicitly false. Generated reference builds preserve core ISC / SLJIT
BSD notices and remain ignored; no upstream implementation or ROM is vendored.
