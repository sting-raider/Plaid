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

Status: implementation in progress. No new validation claim yet.
