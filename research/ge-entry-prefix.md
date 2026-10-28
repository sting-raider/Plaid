# Source-bounded call-entry admission

Worker ge-closure-r2-14bd4091; ADR0286 follows ADR0285. Commercial bytes, maps,
replay caches, native artifacts and controls stay ignored under target/. No
subagents or RT64 bridge/patch changes.

## Claim and verifier

The bounded prefix heuristic may reject a slot callee only from its own supplied
instruction source. Scanning beyond it into another allocation borrows unrelated
bytes. Use the declared source extent, including identity links, and leave any next
source to discovery. A reserved encoding inside the real prefix still refuses.

The retained implementation fails slot_call_prefix_stops_at_its_source_boundary;
the candidate passes. The synthetic neighbor contains Rabbitizer-invalid70000000
(notffffffff, which is a valid SD). The same word moved into the candidate prefix
is rejected. A second unit contract verifies the identity-link boundary; disabling
the extent check fails it. Red/green logs are retained in target/ge-return-continuations/target/
prefix-final-{red,green}.log. This is general source handling, with no game test
or title-specific address in production code.

## Fixed-source result

Using exactly ADR0285's222 authenticated engine pages and ten repaired snapshots:
blocks47161->47211, residual109->85, direct37->12, unmapped9->10. Remaining slots42,
indirect5, host-runtime-body8, callback7 and TLBWR1 are unchanged. Before:
target/ge-final-return-proof-after; after:target/ge-entry-prefix-after. Retained
discover/solve times are34.063/3.468s before and35.000/3.407s after. These receipts
were collected with other work and do not establish a speed change.

## Separate production convergence

ADR0282's authenticated refill sources first add three pages (225 total), giving
48186 blocks/74 blockers with the prefix fix. Two more sources and four first-use
data repairs from ADR0284 reach227 engine pages/49305 blocks/59 blockers. The final
buckets are43 independent delay slots,8 decoded host-runtime entries,7 callbacks,
and1 TLBWR. There are no remaining direct, unmapped, table or indirect blockers
in that expanded map. No source arithmetic formula or counterfactual root becomes
an execution root. Receipts:target/ge-prefix-source-convergence and
target/ge-prefix-table-convergence. Final discovery/solve take34.922/3.469s;
the last no-change data/refill checks take0.532/0.515s.

The fixed-source reduction must not include these new sources. Emission remains
refused; there is no GoldenEye native VI, framebuffer, Rare/Nintendo logo, title
or completeness claim. Cross-source slot representation, mapped runtime closure,
and refill/Random/Wired/exception semantics need independent native contracts.

## Final integration gate

All required exact-tree cargo/CLI/runtime/progress checks and eight quiet visible
silent game controls must pass under target/receipts/ge-entry-prefix before the
canonical fast-forward. GCC15.2 and pinned ares identity remain unchanged. No
reference code is copied, no runtime guest execution is introduced, and no shim
rebuild is needed. MM standalone clean main measured1769 VIs/fault0; the original
1612 observation was not reproduced. Existing controls remain mandatory.
