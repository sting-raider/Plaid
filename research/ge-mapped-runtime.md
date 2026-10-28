# Guarded mapped runtime boundaries

Worker: ge-closure-r3-e11a43ae. Base: ADR-0286. User-local commercial
inputs, maps, replay outputs, executables and framebuffer PNGs stay ignored
under target/. No child agents, README edits, RT64 changes or reference copying.

## Claim

A runtime callback's virtual pointer selects an independently guarded native
source entry. A host implementation of mapped guest code needs its complete
declared guest source verified and pinned before host effects. Address-taken
discovery must stop at the declared host entry instead of decoding that body.

The prepared f06c5d21/29d70e06/a4d3ad64 candidates are semantic inputs only;
their parent history is not merged. Production acceptance requires independent
reconciliation, synthetic source/identity and native-effect verification, the
complete exact-tree gate and all eight visible silent controls.

## Contract

Callback discovery expands a proven virtual pointer into its supplied source
entries. Solver admission requires validated slot metadata and every declared
callback source entry decoded; one available alternate cannot close another
missing identity. Native dispatch checks the
actual mapping, content and generation. No observed pointer becomes an
exhaustive indirect target proof.

RuntimeFunction gains an optional source_size, populated from an existing
runtime declaration's size. Old fixed runtime declarations remain readable.
Reference-map-only null sizes remain unknown, as verified by the CLI fixture;
they cannot satisfy a mapped host source extent.
Mapped host entries require a nonempty aligned extent wholly inside their own
supplied executable source. The native binder compares that entire range;
host entry wrappers pin it across every host effect. Direct calls across source
boundaries must bind their destination before entering the wrapper. ABI
substitution remains the existing explicit runtime assumption.

## Measurements and verification

The independently reproduced ADR-0286 expanded baseline has 227 engine pages,
49,305 blocks and 59 residual blockers: 43 delay slots, eight decoded runtime
bodies, seven callbacks and one TLBWR. Its discover/solve receipt is
79.110/4.734 seconds with concurrent validation; it is not a speed baseline.

On those unchanged sources, the candidate has 49,241 blocks and 44 residual
blockers: 43 independent delay slots and one TLBWR. All seven callback and eight
decoded-host-body blockers disappear; 64 blocks of declared host implementation
are no longer rooted as guest bodies. Discovery/solve take 25.828/4.719 seconds.
The runs had different concurrent workloads; no speedup is claimed. Reproduce
with the ordinary discover/solve commands and the same loads/id declarations;
ignored before/after maps and timings are target/ge-expanded-prefix and
target/ge-mapped-runtime-after. Source expansion is not included in 59 -> 44.

The mapped callbacks fixture checks single and multiple supplied identities
against pinned ares, comparing every GPR/FPR, PC, HI/LO, FCSR and output RAM.
Entry/interior corruption, missing mappings and non-entry pointers refuse before
effects. Removing the generated source check defeats the interior refusal.
A new deleted-alternate fixture is red against the prepared callback policy
and green when every source entry is required; it asserts the specific callback
obligation even when other map checks also detect the altered graph. Red/green
logs are target/mapped-callback-missing-identity-{red,green}.log.

Mapped host calls have direct/indirect full-state oracle comparisons, missing/
zero/misaligned/oversized source extents, and entry/interior corruption, absent
mapping and active source write/remap refusals before host effects. Removing
the host wrapper pin makes the protected-write case incorrectly succeed; the
retained mutation detects this. Core extent tests additionally check wrong image,
wrong generation, both source boundaries, data beyond text and deleted bytes.

Canonical acceptance requires fmt/clippy/workspace/CLI/runtime/progress and all
eight silent visible controls on the exact final tree. Their commands, tree IDs,
timings, stop JSONs and RDRAM-derived PNGs are under
target/receipts/ge-mapped-runtime. Control C, headers, compiler and retained
object/executable hashes must agree before reuse. No shim rebuild is required.

The isolated clean-main MM control reached VI 1797/fault 0/PC 00000000 in
30 seconds (31.500 seconds including stop/readback). Its sources were regenerated
by a fresh compiler built from clean main 17d41fbc and exactly match the retained
control sources and runtime. The earlier 1612-VI observation did not reproduce.

Pinned ares 9408cb43 remains a separately built ISC/SLJIT oracle. No reference
implementation body is copied, and no runtime MIPS interpreter/JIT is added.
Cross-source delay instructions and refill/Random/Wired/exception delivery
remain independent obligations; no GoldenEye executable, VI, logo or title
claim follows from mapped runtime closure alone.
