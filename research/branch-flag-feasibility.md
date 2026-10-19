# Branch-flag values and feasible predecessor paths (ADR-0212)

Base: `309b0911d0d9a1b9ffdce51226a38b9c5d602520`.

A recovered overlay trace required one unchanged GPR to be nonzero on the
current dispatch path and zero on an earlier loop edge. Such a predecessor
path is infeasible. The table walk now skips that edge after reading its
branch and executed delay slot. Other predecessors still need proof; an empty
result set cannot certify a table. Complete Need cycle equality, source-word
hashing, external-entry barriers and resource limits remain unchanged.

This requires value-version tracking. Pointer and scale transfers had early
returns that could retain a flag after writing the same GPR. A naive pruning
rule consequently accepted an invalid guard whose boolean had been overwritten
by a pointer or shifted index. The final rule clears flag constraints on every
non-SLTIU destination write before those transfers. The existing SLTIU guard
binding and constant-overlap rejection remain. An additional authored straight
path proves the stale-guard issue also existed without a loop: baseline accepts
that invalid fixture and the corrected rule rejects it.

Five retained integration tests cover the valid unchanged-flag loops, writes in
the body and delay slot, an external loop-body entry, pointer/scale aliases,
and the straight-path stale boolean. Baseline and naive-rule failures are
retained under target/paper-mario/0212. Native valid indices zero/one and an
invalid index that remains on the zero-flag loop path equal pinned ares over
full register, PC, FPU and RAM checkpoint state. The first full workspace gate
exposed an older conservative test that required a fresh SLTIU on every loop
edge. Its NOP variant preserves both the original index and flag: a zero flag
loops without dispatching. It is now a positive case, with mutations that write
the index or flag and a separate unknown loop-body entry still rejected.
Independent review and full exact-tree validation remain required before
canonical integration.

The fresh pass at prototype `7c4e1aa26261054916fff6a12820c74b9b55d217` remains
OPEN/13, with 56,807 blocks and 162 inferred loads. Eight more blocks and two
indirect sites are discovered, but the blocker sites are unchanged. The
five-word dispatch at 80aac6f0 retains candidates; additional callee effects
prevent final closure. Three other affine sites have real address-taken entry
barriers under the current fallback model, which this change does not erase.
No native Paper Mario artifact is emitted or run.

Discovery took 58.089 seconds and solve 16.182 seconds while other control
solves ran concurrently. Optimized compilation took 167.361 seconds after
moving to another source checkout. These operational timings are not a
controlled performance comparison. Future private iterations should reuse
the same source path and validated oracle cache to avoid needless rebuilding.

Retained BK and F-Zero X maps report OPEN/234 and OPEN/157 respectively with
both the unchanged canonical debug compiler and this optimized candidate;
the complete reports compare equal. These are pre-existing map/version
compatibility results, not regressions introduced here or current successful
gameplay claims. The retained MM map remains CLOSED. Receipts are ignored at
target/paper-mario/0212/{controls,baseline-controls,control-comparison}.json.

Recovered test-profile experiments show the tradeoff: warm execution of the
same five expensive tests took 112.717 seconds at opt0 and 15.554 at opt1.
After applying this actual semantic change and adding the four flag tests,
build plus the same nine tests took 135.112 versus 171.083 seconds. Source
was restored byte-for-byte after that isolated experiment. Keep the current
test profile; the faster warm execution did not outweigh rebuilding here.
The receipts are under target/paper-mario/0211-test-profile/.
