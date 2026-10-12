# Primary composition: memory reads through physical FPR bytes to backing stores

Base: bd06940bc4bf0ff0de948c73efeb891a2e408459. Claim: 6115418520.
PR #17 @ 7c6de0b3849a119db815bf35ffbb91efb4b063c6; source research
cop1-load-store-lineage-gpt56sol and its prepared receipt. Reconcile project-owned
Rust only, keeping the canonical CU1-aware cpu_mutation wrapper unchanged.

Production cop1_lineage preserves exact completed read/load definition links,
physical FPR byte generations, same-value move replacement, failed-load absence
and mixed stores. Its composed API/CLI invokes canonical completed-store
normalization rather than accepting caller-forged mutation conclusions. Require
exact complete store correspondence, replayed FPR state, selected physical lanes,
FR/ft/kind, payload and direct-KSEG1 backing address. Cache-resident mutations
cannot pass this uncached contract. Source and normalization contexts require
separately retained external CLI receipts; reports retain every side input and
complete nested replay. Unknown event/origin envelopes reject.

The accessible historical runs retained summary receipts, not the raw matrix
needed for the new Rust source join. A single necessary local pinned-reference
reproduction used the original spike-043 project-owned harness with only its
relative include path relocated under ignored target/cop1-lineage-primary.
Source and model semantic hashes are preserved. Plain/traced semantic outputs
and repeated traced observations agree across all 96 actual cases. No Actions
execution. Keep the new raw controls so this reference build is not repeated
merely to validate another compatible consumer.

Exact ares pin: 9408cb43d4948fc3ea6e152a307a34348df3fe04, clean relied-on
source. Canonical interpreter-fpu.cpp + NUL + rdram.hpp source-pair SHA256:
48c5aa9ee8fef943fccdb80bae000ace0e815ab1f51710a41694548e3044d17e.
Working-tree CRLF byte hashing differs but canonical Git objects and source
guards agree; no reference source edits or line-ending reset was needed.
Independent 67-case model SHA256:
5a771c25653c96a8f858bc35b41d2acd835dd6d5c65ac9e65f82d8ccd617cf69.
Repeated 96-case receipt matches the swarm exactly:
f9c06faf9a98c48916d48f1b4409410b8dafca715074ff84585867850d6f0450.
New retained complete matrix/control SHA256:
773673751c6735cb4c4f7b66c736eb18f2d59ddcac7c8ad817caf2d81a41291a.
Normalized history/context set SHA256:
d27a857597bf3182315263e60c31c51529d224f53e618dc6797d9774b320a572.
Complete composed report set SHA256:
3258808138a6fa61a229beed4e4ae2e34a3fdd5f6f00057529a589beb7551503.

The fixture adapter retains actual backing callbacks and selected-register
snapshots. FPR write occurrences/physical selections and decoded normalization
contexts are projections from authenticated controlled instruction/FR/ft/GPR
inputs and the exact pinned selector; they are not new raw sensors. All modeled
FPR0/1 states agree with actual before/load/move/final snapshots, and unchanged
register constants follow the bounded fixture's restricted ft=0/1 instructions.
Report flags do not promote this into arbitrary-guest writer/context completeness.

LOCAL PASS: nine Rust FPR/source/composition regressions, five canonical
normalizer regressions, two-input CLI source/context/report/overwrite adversaries,
all 96 actual cases/72 completed-store joins, ten mixed stores, six equal-value
counterexamples, eight same-value move cuts, 24 failures, and 72 fresh CU1
forgeries; fmt, strict locked workspace/all-target Clippy, full locked workspace
including actual outer fixed-point deletion adversary, canonical CLI and diff.
ADR-0120; STATUS/NEXT/DEVELOPMENT updated, progress unchanged.

Superseded: PR #17's isolated consumer recommendation and duplicate prepared
production surface. The generic FPR replay remains reusable, now joined to
canonical store normalization. Neither bare payload equality nor phase labels
join separate source clocks. RAM producer ancestry, complete FPR/mutation census,
architectural-context ancestry, arithmetic/other writers, cache/TLB/endian paths,
executable lifetime and whole-ROM/native closure remain OPEN. No upstream
implementation is copied into production, no runtime guest executor or solver
waiver is introduced.
