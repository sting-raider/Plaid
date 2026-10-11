# Primary XORI transformation reconciliation

Hypothesis: exact adjacent captured load/transform/store register def-use,
architectural continuity and completed uncached backing effects can establish
one XORI transformation, including a distinct zero-immediate transform context.

Reviewed every fixture/sensor/verifier file in
`research/cpu-xori-transform-gpt56sol` at
`c37fc109074c5be63ccdfe5157175933be441586`. Authenticated its successful Actions
`37918087716` synthetic artifact with results SHA-256
`763be0ae69e5400a059f3c9dd5f79094592af0ccfda33eb5c50c381c759ddaef` and reproduced
all four controls. Its unmodified verifier also accepted three additional
forgeries: altered high GPR bits between load/XORI, a nonsequential XORI PC and
a KSEG0 destination claimed uncached. Each still emitted all four certificates.
Reject that verifier as written; equal transformed bits are not continuity.

The primary fixture preserves all seven phases but reuses spike-044's strict
field/type/complete-effect/address/GPR/PC verifier and shared instruction/scalar
sensor. XORI is enabled explicitly for this finite contract; ordinary copy mode
still rejects it. Exact adjacent register identities must match the load,
transform source/destination and store source. Source/transform/store contexts
are retained separately even for immediate zero. Four byte expressions preserve
the big-endian Word relation. No branch-only compiler/workflow or duplicated
observer/generator is adopted.

At unchanged ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, twenty reported
instruction checkpoints agree in original/disabled/enabled/repeated runs.
Forty boundary records and thirteen completed scalar effects yield four intended
certificates. Thirteen measured adversaries fail; six independent synthetic
contract tests pass, including a wrong-source/equal-bits negative and explicit
copy-mode separation. The weaker expression matcher still admits phase 5 and
cannot distinguish the phase-4 competing source. Schema-0 result SHA-256:
`e73a87e0106b5bc6b9631f35795015aa6275a6d70f171a9c186d2c32a732e783`.
Full locked core, fmt and strict workspace Clippy pass; unchanged copy controls
and their seven synthetic regressions remain exact.

Pinned ares decodes XORI with an unsigned 16-bit immediate and performs a full
64-bit GPR XOR. Pinned Gopher64
`e96debac941a26ba4961e5145056c0821d3a56f7` agrees at source level; that GPL source
is inspected only and is not copied or behaviorally run. Core ISC / SLJIT BSD
notices remain in generated ignored ares builds. Only project-owned fixtures and
observers are retained; no upstream implementation enters production.

The same attempt-census and reported-state limitations as spike-044 apply.
This is not arbitrary dataflow, cached/translated access, decompression,
relocation, ultimate ROM ancestry, executable consumption/lifetime or hardware
truth. No ProgramMap/solver transform certificate or native gate is installed.
The branch's bounded fixture/verifier is superseded by the reconciled contract;
its broader obligations remain open.
