# Source-aware return continuations

Worker ge-closure-r2-14bd4091. This is ADR0285, following ADR0284's fixed-source
table repair. Commercial inputs, generated maps, oracle binaries, RAM and PNGs
remain local and ignored. No child agents or RT64 bridge/patch changes.

## Root cause and change

A call's analysis address may be a placed alternate. Its architectural PC+8 is
not necessarily the next analysis allocation. Direct discovery had already
handled the boundary, while return certificates still used storage PC+8. Reuse
CodeImage::sequential_pc for callers with the matching image/generation. Keep
other caller identities intact rather than borrowing this image's metadata.

No closure assumption is weakened. The verifier independently recomputes the
certificate; native RA stays virtual, and dispatch still checks the independent
continuation source, physical mapping and generation. No interpreter/JIT or new
runtime target fallback is introduced.

## Fixed-source receipt

Both maps use ADR0284's same ten first-use data snapshots and222 authenticated
engine pages. They contain47161 blocks. Residual blockers improve124->109:
indirect-target blockers20->5; slots42/direct37/unmapped9/runtime-body8/callbacks7/
TLBWR1 remain unchanged. The five indirect candidates belong to a single table
whose snapshot still contains aligned code words. Emission remains refused.
There is no native GoldenEye VI, framebuffer, logo/title or completeness claim.

The retained current-source discover/solve probe takes34.578/3.485s; the isolated
return-certificate candidate takes39.703/3.734s. These are work receipts collected
with other local checks, not a speed claim. Before:target/ge-final-production-tables;
after:target/ge-return-proof-after. Later exact-tree reruns are retained with the
landing receipts at target/receipts/ge-return-continuations.

## Verification

The core regression separates the caller's virtual continuation from neighboring
storage. It fails before the change, and changing a valid certificate back to
that old storage address fails verification. The native JAL/JALR fixture adds an
unused alternate between caller and continuation allocations. The retained CLI
fails the JAL lower-map gate. With the fix, all nine existing linear/call/ordinary/
likely/linking branch scenarios match pinned ares on complete GPR/FPR/PC/HI/LO/
FCSR and output RAM. Existing source-corruption and wrong-continuation mutations
remain detected. Baseline-red and green logs are retained in the isolated
candidate's target directory; final full gates and quiet visible silent controls
belong under target/receipts/ge-return-continuations before the canonical write.

Compiler, runtime and reference identity checks preserve GCC15.2 and the pinned
ares9408cb43 ISC/SLJIT oracle. Existing notices remain; no upstream body is copied.
MM's earlier1612-VI observation was not reproduced by standalone clean-main or
candidate controls. No shim rebuild is needed for this certificate-only change.

## Separate prepared work

A call-entry prefix heuristic also crosses from its authenticated fragment into
neighboring analysis storage; its isolated red/green candidate is a later change.
Three new independently verified refill pages give a225-page map with48134 blocks
and99 blockers using this return fix. Neither that source expansion nor the
prefix change is included in124->109. Remaining independent delay-slot fetches,
refill/exception and Random/Wired semantics, callbacks and runtime boundaries need
separate general contracts before a GoldenEye native build can be accepted.
