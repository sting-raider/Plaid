# Limited successful CPU word stores

2026-10-08. Mupen pin `ba95bab92a76744753bfe61470823a4937850ab0`.

Hypothesis: a callback after a successful constant-address cached-RDRAM SW,
including return from its invalidation stub, can preserve CPU state while
capturing actual source/destination/value evidence distinct from cache invalidation.

Inspected `store_assemble`, `do_writestub`, x64 ABI argument definitions and
save/restore helpers. The generated callback is after the direct store and the
invalidation return address. It copies the value into ARG3 before assigning the
constant destination and source PC to ARG2/ARG1. The first build caught mistakenly
named HOST_ARG registers; corrected to the pinned ARG definitions. No reference
store semantics are changed. The sink advertises `cpu_sw_constant_rdram_x64`
only with `PLAID_TRACE_WRITES=1` on this host architecture.

Trace v0 adds `cpu_word_store_observed`; ProgramMap retains optional/defaulted
word-store observations with source, destination, value, import epoch and evidence.
Validators reject unaligned addresses or destinations outside 80000000..80800000.
Raw events always survive. Explicit physical overlap with a previously compiled
region adds Unknown executable-write evidence; data stores are not guessed to be
code. This does not issue a mutation or copy certificate.

Six original full-core fixtures agree across interpreter/traced/untraced dynarec
on every GPR, HI/LO and PC, with byte-identical traced reruns. Event counts with
the sensor are 43 (PI), 83 (replacement), 82 (uncached replacement), 82 (CPU
mutation), 34 (CPU copy), 48 (store/register stress). Mutation events correctly
identify A400008c -> 8000040c = 2410000b and A4000098 -> 800004c8 = 2412000d.
The stress fixture checks zero at 80000610 and 406 at 8000060c in a taken BNE
delay slot, with at least 29 nonzero GPRs preserved and the untaken effect absent.
Its initial fixture put the base LUI too early: reference allocation lost the
constant fact under pressure, so the limited sensor correctly did not fire.
Move the LUI immediately before stores to exercise its declared scope.

Stress data writes also invalidate compiled entry state. The current conservative
import epochs have no unique source identity for subsequent reused/restored
entries. All raw indirect events remain, with explicit uncorrelated blockers and
no cross-epoch attachment. This is a next modeling task, not permission to weaken
the join rule. Every full-core whole-ROM solver result remains OPEN.

Reproduce: `python scripts/test_mupen_session.py`. Rust regressions cover trace/
map roundtrips, invalid addresses, deterministic merge, data-vs-known-code overlap
and preservation of Unknown writes. Other addresses/store sizes, unaligned/TLB/
uncached stores, mode-dependent faults and CPU-copy provenance remain unsensed.
Dummy plugins and synthetic PIF-HLE setup still bound the full-core oracle scope.
