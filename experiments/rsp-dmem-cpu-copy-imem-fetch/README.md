# RSP DMEM -> CPU copy -> IMEM -> RSP fetch composition

This bounded experiment composes three already validated exact-pin research contracts instead of adding another emulator sensor:

1. decoded RSP DMEM storage effects produce byte-granular writer generations;
2. a CPU `LW` -> preserved GPR -> `SW` chain can certify an actual SP DMEM -> IMEM Word copy;
3. completed IMEM storage generations can explain later RSP interpreter fetch bytes.

The seam under attack is the CPU Word-copy certificate. Its current bounded form records the completed source-read ordinal, destination-write ordinal and Word value, but not the source read's per-byte ancestry. A Word can already contain mixed origins from CPU, scalar RSP, vector RSP or UNKNOWN writers.

`model.py` replays one ordered chronology with a mixed DMEM word, an equal-valued decoy read, same-value RSP writer generations, a valid CPU copy, a same-value post-copy IMEM mutation, a same-value GPR clobber, and a second valid reload/copy. It separately tracks IMEM resident generation and ultimate byte ancestry.

The test deliberately demonstrates a projection collision: two histories have identical bounded Word-copy certificate fields, identical fetch payload, and identical IMEM resident generation, but different upstream byte ancestry. Therefore the Word-copy certificate is adequate for the bounded copy fact but insufficient by itself to preserve ultimate executable-byte provenance across that seam.

`source_guard.py` verifies the exact prior Plaid commits and Git blob IDs being composed plus the ares revision in `refs.lock.toml`. The experiment makes no new hardware or emulator-behavior claim beyond those validated inputs.

Run from the repository root after fetching the two referenced research commits:

```bash
python3 experiments/rsp-dmem-cpu-copy-imem-fetch/source_guard.py
python3 experiments/rsp-dmem-cpu-copy-imem-fetch/model.py
sha256sum target/rsp-dmem-cpu-copy-imem-fetch/results.json
```

Expected properties:

- the first valid IMEM copy has one resident write generation but three distinct upstream source identities across four bytes;
- the equal-value RSP rewrite remains the newest source generation;
- an equal-value read into another GPR does not steal the copy source;
- a same-value GPR rewrite prevents memory ancestry certification;
- a same-value post-copy IMEM byte mutation changes resident generation and degrades that byte to UNKNOWN;
- ten forged histories fail strict replay;
- two equal-payload histories collide under the flat Word-copy projection while retaining different strict byte ancestry.

This is a composition/proof-model result, not whole-ROM closure, RSP hardware atomicity, a complete mutation census, or native completeness.
