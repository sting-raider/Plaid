# Observed boot PI byte chains at fetched instructions

Hypothesis, 2026-10-09: the validated complete v2 chronology can retain the
recorded PI writer for each RAM byte, snapshot it through an adjacent actual
identity-RAM I-cache read/fill, and associate it with a matching fetched resident
line. Later backing writes must not replace resident history. Uncached attribution
requires exactly one eligible completed read in its actual fetch interval.

This continues the executed spike-029 contract and the strict v2 source consumer;
it does not change ProgramMap or the closed-world solver. The first implementation
will expose a separate finite inspection report with raw v2 writer/fill/read
ordinals and exact nested prior reports. Replaying both complete sources again
must reproduce their digests, preventing changes between validation and lineage
replay. The report rechecker will reconstruct every field.

Adversaries must cover equal/changed PI reloads with stale resident instructions,
partial words, ordinary writes and burst writeback, tag changes and invalidation,
unwitnessed fills, ambiguous uncached reads, payload contradictions and source/report
tampering. Retained boot results must agree with an independent Python replay.

Important limit: this describes chains in observed records. The current identity
sensor does not certify all mutation, mapping, reset or external-device epochs.
Matching bytes cannot prove that an unobserved same-value write never happened.
Keep mutation-coverage, executable-lifetime and native-completion flags false.
Known byte chains are evidence for future contextual discovery, not production
image generations or continuous first/last-fetch lifetimes.

Status: **VALIDATED for finite observed lineage**, 2026-10-09.

The full retained v2/v5 corpus passes Rust inspection and complete report source
rechecking. The complete nested queue/v1/v0 report remains exactly equal to its
prior validated report. An independent Python replay agrees with every sample,
count, source digest and the ordered fetch-chain digest.

- 610,000 fetches; 10,954 fully attributed PI-byte observations, no partial words
  in this prefix, 599,046 unattributed by this PI-only path.
- 43,816 observed ROM-byte fetches; all full words use one contiguous transfer.
- 185 distinct samples, all tied to transfer 1; zero payload contradictions.
- Ordered fetch-chain SHA-256:
  `67158997c3fbec624afaea75cd8b255ef59c863258345a89ca80cda1bb3da5c7`.
- The 139,762-byte pretty JSON report SHA-256:
  `c866f99653680a13b2f1a1695bba0c3ae580dd0b4659ad42d4cdf0a00492b3fb`.

Three Rust unit tests cover stale resident/equal or changed reloads, equal scalar
and full burst writes, partial words, tag changes, invalidation, unknown fills,
explicit fills and contradictory backing reads. Two integration tests bind raw
writer/read ordinals to full nested sources, reject forged flags/writers and
ambiguous reads, and detect either source changing between validation and replay.
All 94 integration tests plus three unit tests pass; formatting and strict Clippy
pass. These tests do not establish complete mutation coverage.

A source-domain audit explains the remaining prefix: 2055 uncached PIF fetches,
191379 uncached CPU fetches from SP DMEM and 405612 from SP IMEM. All 10954 RAM
fetches are cached and have the recorded PI chains above. This makes the actual
CPU-to-SP backing-read sensor, followed by PIF and SP producer history, the next
concrete source-coverage task; assigning ROM origin from SP addresses would be
unsound. No additional reference execution is claimed by replaying retained data.
