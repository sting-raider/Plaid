# Frame-local table-pointer reloads (ADR-0217, partial)

Base: `7f09341eae3a3cf41e50192988430ae66b4e31e2`.
Branch: `experiment/pm-closure-0217`; no canonical write authorized.

Hypothesis: an exact SW/LW stack-cell pair may carry a captured table pointer
when all predecessor paths prove an unchanged SP, an enclosing negative ADDIU
frame allocation, and no intervening potentially aliasing store or call.
The forwarded value must still satisfy the existing ADDU/scale/base/index
proof; a word spill is not evidence of full 64-bit GPR preservation.

Attack order: the three independent address-taken entry/base barriers remain
unknown-state entries. The two callee-effect sites require width-aware
save/restore and memory effects through nested calls and unknown heap stores;
no ABI assumption can discharge those requirements. The two stack-cell sites
are considered next, retaining refusal of every unproven alias/index relation.
Diagnostic addresses and instruction output are ignored under
`target/paper-mario/0217/diagnosis.txt`. No ROM bytes enter git.
