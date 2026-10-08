# Spike 033: translated/degraded scalar RDRAM backing provenance

This spike asks whether pinned ares can expose a successful non-identity scalar
RDRAM read as a two-stage provenance fact rather than collapsing the requested
physical address, actual backing bytes, and post-CCI delivered value into one
number.

The exact pin is `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
`run.py` reuses the existing spike-003 build recipe but patches a copy of that
Python builder in memory. It does not edit canonical builder or upstream files.
The generated shadow `rdram.hpp` changes only the successful non-identity scalar
read expression so that the existing backing read executes once, CCI inputs are
snapshotted, the existing `degrade()` executes once, and an optional callback is
made afterward. A source guard rejects source drift.

The fixture crosses chip mappings in both directions, adds an equal-valued
request-address decoy, checks reliable/zero/partial CCI cases, missing mapping,
inactive RI, an identity read, and an EBus HiddenRAM read. Baseline,
observer-disabled, observer-enabled, and repeated observer-enabled execution must
agree on all emulated results and state; repeated traced JSON must be byte exact.

Run:

```sh
python3 spikes/033-ares-rdram-translated-backing/run.py
```

A local `.refs/ares` checkout at the exact pin is required. The branch-only
workflow fetches that revision and runs the spike on Ubuntu.

The intended witness fields are request paddr, translated backing paddr, chip,
width/requestor, raw backing value, CCI bounds/current value, and final delivered
value. The raw backing value supplies byte origin. The final delivered value is
what the consumer observed after RDRAM degradation. Missing mappings and paths
that never perform the ordinary backing read emit no witness.
