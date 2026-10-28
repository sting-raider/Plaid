# Independent native owners of identical physical text (ADR-0294)

## Contract

An authenticated mapped source may share physical words with fixed native text,
declared loads or immutable proof data. Binding still verifies its complete
source bytes and mapping. Existing protections are borrowed, not discarded.
Overlapping independently bound mapped sources remain refused.
Heap copies retain their existing protected-target refusal. Only protection
classes present in the compiler's immutable base map can be borrowed; unknown
runtime metadata refuses without changing an existing binding.

The lowerer emits a compressed immutable map of the original fixed protection
classes, with the same priority as the existing runtime protection builder.
The map needs no new state allocation. Revocation restores immutable proof
protection, marks base text revoked and invalidates affected fixed-load byte
witnesses. Both fixed and mapped native frames continue to pin their words.
Inactive aliases can revoke and then reverify; neither entry may execute changed
bytes. Immutable base proof data cannot become writable through a mapped alias.
Fixed text entered while an alias is bound also compares against its own
compiled words, retaining the alias tag on success. A mapped source's valid
bytes do not establish that a different fixed source is valid.

Writes preflight their complete physical range before changing any source
witness. A later proof/active-owner refusal cannot leave an earlier alias
revoked. The existing runtime source/content/generation and TLB mutation guards
remain in force. No interpreter, runtime decoder or guest JIT is added.

## Verifiers

One synthetic program runs the same three words through a mapped call and a
fixed call, adding20 to v0. It matches complete pinned-ares GPR/FPR/PC/HI/LO,
FCSR and output RAM. The original protection builder and compressed lookup
agree at every RAM word. Each frame owner independently refuses a write;
inactive revocation restores the fixed load tag and invalidates its witness.
Corrupt bytes refuse both entries. The retained parent compiler stops this same
program at fault3/PC800000d4 on its first mapped entry.

Additional runtime protocol units explicitly supply synthetic protection
metadata for base text, immutable proof data and a mixed two-word transaction.
They check frame pinning, full-state atomic refusal, mapping revocation, proof
restoration and corrupted revoked text. These are isolated metadata fixtures,
not claims that the oracle program inferred those proof classes. Removing the
whole-transaction preflight breaks the mixed-owner unit; removing source
verification breaks the main corruption test. Retained complete TLB execution,
mapping/clear, physical-source and generation contracts also pass.

The recovered candidate06486742 failed the retained heap-copy protected-target
test. The finished contract limits borrowing to mapped sources and preserves
that original test unchanged. Additional negatives cover undeclared protection
tags and mismatched fixed words while the mapped source remains valid. The
fixed entry must neither skip its own comparison nor erase the mapped tag.

## GoldenEye reduction and next fault

On the unchanged production frontier there are49,250 blocks, zero ordinary
blockers and five residual sites; native_complete remains false. All1678 fixed
protection overlaps that refused the first mapped source are now admitted with
both owners preserved. Source bytes still verify all288 guarded ranges.

The silent visible prototype advances from VI0/fault3/PC800004b4 to
VI0-1/fault2/PC80920a04, RA70201214. The lowered store is a byte write to800411c0
during decompression. The current rebuild records one host retrace tick; the retained prototype
records zero. Both have zero VI registers and no initialized framebuffer.
No graphics or audio tasks have
initialized. The remaining refusal is a source-lifetime obligation: the large
raw mapped source still pins guarded words outside the currently executing
function. Do not weaken that guard. Consider independently authenticated source
pages using the existing cross-source branch/continuation/delay contracts.
There is no logo/title claim.

## Receipts

Ignored producing artifacts are target/alias-focused.log,
target/alias-baseline-red.log, target/mapped-alias-contract and
target/receipts/ge-alias. The last directory retains native stop JSON, full
RDRAM, readback PNGs and final exact-tree gate/control/build receipts before
integration. The retained prototype wrapper took2.782s before fault; different diagnostic
workloads prevent interpreting that as execution speed. All control CPU/runtime
objects must be rebuilt because generated protection helpers changed. GCC15.2,
the pinned ISC oracle and RT64 binaries are retained; bridge/patches and README
are unchanged. MM's clean-main and latest control counts remain1797/1798VI in30s,
with no reproduced1612VI regression.
