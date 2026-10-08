# RAM mapping and degradation boundaries

Hypothesis: the identity-only burst observer must omit remapped/degraded/failed
accesses, while preserving actual 16/32-byte identity results without extra reads
or clocks. Use direct reference-component calls with declared chip/RI setup.

Run `python spikes/017-ares-rdram-boundaries/run.py`.

## Verdict: VALIDATED for the declared direct-component boundary cases

### Evidence

Bus address zero maps to backing chip one; translated stores and zero/partial
degradation pass. Missing mappings, inactive RI and out-of-bounds accesses return
zeros. All these cases remain outside the identity-only policy. Exactly three
successful identity transactions emit witnesses: a 32-byte read/store and a
16-byte read. A baseline without the header callback matches every returned
word, GPR/HI/LO/PC/Count, RI error and full RAM/hidden-memory hashes; repeated JSON
is exact. Partial degradation also has fixed returned-word goldens. Count=0 and
RI error=1. RAM SHA-256:
`b34ba68aca7b98053ef23b552d335c428b1fb33b19972b1bfb2e4cbeaf0d515c`.
Hidden-memory SHA-256:
`68510b252b438d53c7be9eb09f1d519e8d0f3193d0f0a1d942852d282070cf6e`.

### Constraints and surprises

This is a direct-component synthetic fixture; it executes no guest instructions.
Host setup declares chip/RI state and requestor arguments. A requestor argument
is no independent execution/caller certificate. Remapped data stays outside the
identity policy even when returned bytes equal backing bytes. Both recompilers
are disabled; ROM origins, copy/lifetime joins and reset/restore stay unknown.

### Recommendation

Keep unsupported access policies unknown and unify verified transaction/cache/
fetch ordering before constructing executable identities.
