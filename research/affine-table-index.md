# Affine table offsets and guarded indices (ADR-0214)

Starting from canonical 7c12a36, the inferred-input Paper Mario probe improves
OPEN/12 to OPEN/11, with 56,813 blocks, 4,604 indirect sites and 162 loads.
The five-entry dispatch at 8093c2e0 closes; six blocks are added and no new
blocker sites remain. Addresses here describe local evidence, not compiler
constants. Native Paper Mario emission remains refused.

## Proof rule

A normalized expression over low 32-bit GPR values tracks byte_offset minus
four times the unsigned guarded index. Supported nontrapping arithmetic is
substituted backward modulo 2^32. Paired offset/index increments can therefore
preserve the same full backward predicate around a loop. A constant nonzero
expression refuses the path; only exact zero discharges it. Unsupported
required writes, external entries and incompatible incoming predicates refuse.
The existing full-width SLTIU guard, address construction, source/table hashes,
target identity, binding and lifetime checks remain independent obligations.

Every live expression term must survive guest calls through checked no-write
effects. A variable SLLV adds an exact shift requirement of two; the consumer
alone transfers constant definitions. Transferring them in both the expression
helper and consumer was caught by an authored shift-amount counterexample and
removed before integration. No guest ABI preservation is assumed.

A placed caller may read an incoming fixed-text source only if it is the exact
JR RA encoding and appears in the checked callee effect. Each source is charged
to the same 4096-read budget and included in the deterministic source hash.
Wrong alternates, text holes/data tails and unrelated returns remain refused.
This permits an existing native guest-call contract; it adds no runtime guest
execution or new acceptance assumption.

## Evidence and failed hypothesis

The original authored affine positive fails on the pre-change implementation.
Eleven module tests compare backward substitutions with forward instruction
semantics, including aliases, overflow, high words and variable shifts. Eight
integration tests cover initial values, every loop update, unknown entries,
constant-transfer ownership, callee clobbers, exact return witnesses, other
alternates and data tails.
Native loop/call/shift fixtures compare complete register/PC/FPU/RAM output
with pinned ares; wrong stride and shift cases refuse native lowering.
A separate public-CLI contract copies a synthetic payload into a declared
loaded slot, executes its affine loop and calls a fixed-text guest leaf.
Its full state matches pinned ares; corrupted byte-offset and wrong-stride
variants refuse closure/lowering.

The first private ROM probe (05860fd) returned OPEN/15: candidate table evidence
did not reverify, producing two table blockers and a dependent return blocker.
The exact failure occurred after 11 reads, disproving the proposed budget
explanation. A slot-scoped source read refused the fixed callee return before
the callee witness could be checked. A new positive reproduces that rejection;
an unrelated fixed return remains a negative after fresh indirect analysis.
Candidate 7328cdb corrects the source read and returns OPEN/11.

Independent Luna xhigh reviews found no correctness issues in the affine rule
or the subsequent fixed-return change. The latter independently ran seven
integration, fourteen callee-effect and eleven expression tests. A mutation
changing exact-zero conjunction to disjunction is caught by callee-clobber and
unrelated-return regressions; restored source passes. Exact-tree full local
validation remains the integration gate.

Ignored receipts: target/paper-mario/0214/affine-baseline.log,
double-transfer-red.log, fixed-return-red.log, mutation.json and fixed-return/.
The optimized fixed-return rebuild takes 26.030 s; discovery 53.166 s and solve
16.028 s. The prior private build/discovery/solve took 222.041/48.422/15.371 s
with concurrent builds. These are operational timings, not a controlled speed
claim. The final focused native suite takes 20.410 s.

## Remaining scope

Four remaining calls reference raw TLB bridge addresses whose placed blocks
are already present. They require binding-aware call effects, with mapping and
active-frame proofs retained. They are not declared SDK boundaries. Other
remaining sites require save/restore, stack-cell memory provenance or justified
entry-origin proofs. None is discharged by this affine change.
