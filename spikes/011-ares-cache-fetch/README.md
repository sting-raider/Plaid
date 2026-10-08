# Selected cache context on the boot prefix

Hypothesis: the selected-line sensor from spike 010 can preserve cache slot/tag/
index/eight-word context on the untouched homebrew boot prefix without changing
the prior instruction stream or complete CPU/device/memory checkpoints.
Research v5 declares the snapshot policy and retains the complete v4 boot inputs.
Cached fetches require a resident-line snapshot; uncached fetches have none.
Point snapshots do not establish fill/copy lineage, lifetimes or execution of
all eight resident words. Firmware/reference artifacts remain ignored.

Run `python spikes/011-ares-cache-fetch/run.py --budget 1000000`.
## Verdict: VALIDATED at one million calls

### Evidence

Plain/traced/repeated CPU/device/timing/RAM/SP and complete instruction-cache
checkpoints match; repeated raw bytes are exact. Complete v3/v4 projections and
existing checkpoint hashes remain unchanged. Of one million fetches, 400,954
cached fetches carry 32 distinct resident snapshots; 599,046 uncached fetches have
none. Each slot/tag/index/effective-word selection is checked. The raw stream is
210,032,160 bytes, SHA-256
`c0dcae4870aaec1b30097d7fd95f2b6214f043e2ac1dea6366b1814655ce4ce9`.
The full cache checkpoint is
`eb0abce6ce91d78b5c335be4cb364a7d10744af865a758b9026f9c653c474892`.
Production rejects the unsupported cache policy without writing a map.

### Constraints and surprises

This is the declared NTSC/6102/8-MiB/deterministic/PIF-HLE boot scope. Guest tests
have not begun at this prefix. Payload counts are neither fill counts nor cache
epochs. Resident words do not prove RAM/ROM origin, immutable lifetime or
execution of every word. Recompilers remain disabled; no extra bus, translation
or coherence call occurs. Firmware and reference artifacts stay ignored.

### Recommendation

Check the longer boot prefix and legacy observers. Production import requires
a separate decision, strict snapshot validation and full-source verification,
preserving all source/lifetime unknowns. No executable identity is promoted.
