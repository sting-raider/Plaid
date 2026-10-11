# Primary takeover: observed timer acknowledgement generations

Base: bed2aa5cd2de5691401384bd7248cdaa69867849.
Recovered candidates: PR #46 at a311cdd9140f8e071a478de24aa40b14234bef28;
CAS branch cbb183101b8969e7fd050b222a8b8c9ece4e3841. Module bytes are identical.
Research: research/count-compare-interrupt-producer-gpt56sol at
74fcfa7cf20314048e612b9685249fb738cfa7af; handoffs 6111289509/6111559824.

Hypothesis: Compare acknowledgement needs ordered operation identity even for
equal values. Count writes cannot substitute for acknowledgements; explicit
observed assertions are distinct transitions and never inferred from equality.

Keep the prepared eight adversarial regressions and strict full-report replay.
Clarify the existing scope: already captured primitive operations need separate
authentication; no decoded guest context or automatic Count progression exists
in this schema. The additional regression rejects an unrepresented elapsed Count
change. Preserve strict before-state continuity rather than guessing timing.

Authenticated saved artifact 11647629606 ZIP SHA-256:
3ab6f788ffc879cfa2aee755914ba4600d726ace51e283fdac1b2f2a248e77c2.
Results SHA-256:
ee28a2c899b8c5b4db000d143b6216d7524bb5eb92ea8e9aa1f932937fcf22c9.
Source guard SHA-256:
249c840f1baac98737268072c638e2a1e756234fd9949807097a14c09c3c1d50.
All sixteen saved state rows pass the retained source verifier locally. Exact
relied-on LF source bytes match the seven saved hashes in ares, Gopher64,
Mupen64Plus and n64-systemtest; exact HEADs and selected-file cleanliness checked.
Mupen's unrelated existing instrumentation is preserved, not reverted.

Local production adapter checks the five selected Count/Compare write cases
against actual pending-before/after checkpoints and controlled driver operands.
It checks eleven actually attempted boundary gates against canonical
interrupt_roots and observed admission/root PCs. Synthetic adapter ordinals and
driver-derived initial snapshots do not claim sensed chronology or full-state
observer neutrality. In particular the guest-MTC0 fixture stages Status.IM7
between instructions; that is not a guest gate-writer provenance observation.

Exact source audit retains scheduling disagreement: ares/Mupen derive a new
deadline after Count rewrite; Gopher translates the existing queued deadline.
No scheduling policy is chosen as hardware truth. No reference rebuild, upstream
implementation copy, Actions dispatch, workflow or raw research branch merge.

Required final local gate: focused nine regressions; fmt check; strict locked
workspace/all-target Clippy; locked workspace suite with the real outer
fixed-point deletion adversary; CLI and diff check. Publish by exact-head
refetch/CAS force=false. Local logs/evidence: target/timer-primary (ignored).

Sensor/primitive authentication and census, exact Count timing, reset/save/
restore epochs, interrupt producer/gate chronology, handler provenance/lifetime,
whole-ROM roots and native completeness remain OPEN (ADR-0112). All broader
report flags remain false; progress map and solver gates unchanged.

Outcome: all nine regressions, saved checkpoint/root comparisons and required
fmt/strict Clippy/full workspace/CLI gates PASS on the exact base. Supersede
both prepared candidates and PR #46; preserve source research as evidence.
