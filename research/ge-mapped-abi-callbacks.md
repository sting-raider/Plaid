# Callback obligations at mapped runtime ABIs (ADR-0298)

Hypothesis: a direct virtual call into a declared mapped host ABI carries the
same callback argument obligations as a literal call to its placed source.
GoldenEye after bounded Context writes stops at VI0/fault3/PC8080089c when the
SDK enters its first thread. That function is already lowered, but absent from
plaid_enter. Six direct virtual calls to7000d430 select the verified mapped
osCreateThread source8080d430; the callback pass looked up only the literal
edge target and omitted those obligations. The one placed call was visible.

Index callback ABIs by their exact identities and executable linked aliases,
restricted to the same image/generation. Union each possible ABI's argument
registers. Missing callback targets remain closure blockers. Only an unknown,
unforwarded a2 passed to osCreateThread can use the existing explicit residual
SDK-thread contract; every ABI consuming that argument must agree. Other ABI
alternates cannot inherit that exception. Native source/mapping/content/frame
guards and the native-only target whitelist remain unchanged.

The small ABI set is indexed once per callback pass, avoiding a scan of every
slot at every direct edge. No source bytes, runtime pointer, host ABI or guest
state is substituted. There is no guest decoder, interpreter or JIT fallback.

A synthetic mapped caller invokes a mapped host ABI, which enters a separately
bound mapped callback. Four complete pinned-ares/native state comparisons cover
fixed/mapped callees and alternate callback sources. Missing alternate entry,
entry/interior byte corruption, invalidated mappings, active mapping changes and
non-entry pointers refuse. Removing the source guard is detected. The retained
parent stops the mapped positive fixture at fault3/PC00000001 (unbound source). Explicit metadata
units cover mixed ABI argument unions, the SDK-only exception, image/generation
separation and non-executable slot data. All focused checks pass.

The producing artifacts are target/mapped-callee-baseline-red.log,
target/mapped-callee-focused.log and target/callback-units.log. Fresh production
measurements are recorded below and retained under target/ge-callbacks/. The
final exact-tree gate and all silent controls are required before landing. No logo/title or native-completeness claim is made. No upstream
implementation body or game assets were copied.


## Production measurement

Fresh native identify/discover/solve take6.046/24.250/6.125s and retain49,374
blocks, zero static blockers and five residual sites. Callback entry dispatch
grows from one source entry to seven, closing the six omitted virtual-call
obligations. All newly included targets are proven; no new residual site is
needed. Native completeness remains false. The GCC15.2 build takes67.828s.

GoldenEye passes its first SDK thread and creates five guest threads before
VI0/fault3/PC80805d58, RA70005d60, at the direct call to7f000bd0. The prototype
wrapper takes2.641s. No VI registers, framebuffer, graphics or audio initialize.
The target already has a lowered mapped source; no live TLB entry covers it.
A report-only native stop diagnostic confirms the translation miss and retains
all32 TLB entries (2.844s wrapper). The guest refill vector is present in RDRAM
but has no compiled block. Its MFC0 Context and TLBWR need exception-owned
BadVPN/EPC/Cause provenance, authenticated native vector discovery and a verified
Random/Wired contract. The guest initializer writes Wired=2; staging knowledge
is conservatively invalidated across host boundaries. Do not invent that state
or preload the captured engine page to pass this stop.

The diagnostic reads the runtime stop JSON and RDRAM; PNGs show unrendered RAM.
Artifacts are target/ge-callbacks/{summary.json,ge-callbacks.json,
ge-tlb-diagnostic.json,ge-callbacks.png,ge-tlb-diagnostic.png}. Context and callback
contracts share one final exact-tree gate/landing, with a separate ADR and verifier
for each reduction. Final gate and control receipts are under
target/receipts/ge-context/. No bridge/patch or README is changed.
