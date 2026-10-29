# Native mapped instruction-fetch exceptions

Prepared after ADR-0299 (`aacb2887`). The exact-tree gate and game controls
are retained under ignored target/receipts/native-refill-exact/ and
target/receipts/tlb-exception-controls/.

The pinned reference is ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
ADR-0299 and `ge-native-refill.md` retain the natural GoldenEye trace. A first
fetch miss runs the fast vector, whose invalid pair causes a general exception;
the demand pager eventually permits another fast refill and the engine fetch.
Installing the observed final mapping directly would skip guest behavior.

The candidate introduces an optional `tlb_exception_vectors` set of exact
`CodeAddress` identities. Each must be an aligned architectural vector, a real
entry with its own lowered block, and guest code rather than a host boundary.
Old maps omit the set and retain their previous behavior. Map merge preserves
the declarations and rejects conflicting source identities at one vector PC.
Natural first-fetch RAM vector loads seed discovery before its fixed point.
Their replayed source bytes are subject to the ordinary native text guards.

An actual mapped fetch that lacks a supported translation classifies miss versus
matching invalid page, establishes guest CP0 exception state, invokes the
declared lowered vector, and accepts only a checked ERET to the interrupted
fetch with the original Status restored. Native fragment dispatch still applies
the mapping, content and generation witnesses. Speculative callback lookup stays
pure: preparing another thread does not take an exception on the creator CPU.

This execution scope is deliberately bounded: ordinary aligned 32-bit kernel
fetches, at most eight consecutive handler executions, no nested native refill,
no redirected EPC/ErrorEPC, and no host call from an active handler. External
delay-slot fetches and mapped data-access exceptions are not implemented by this
scope. SDK event preemption cannot transfer the active synchronous exception to
another host thread. Unsupported cases refuse; there is no MIPS decoder or JIT.

The original synthetic pager uses Context.BadVPN to read a page table, installs
an invalid pair, enters the general vector to update the PTE and invalidate its
temporary entry, refills again, then executes source-bound mapped native code.
Bare-kernel and SDK-owned Status variants match pinned ares in GPR/FPR, HI/LO,
PC, RAM, CP0 staging/exception state and all 32 TLB entries. Mutations remove the
actual-fetch boundary, misclassify invalid as miss, corrupt mapped source bytes,
and remove the source verifier. Each is detected. Atomic refusal tests cover
unknown prerequisites and nested/redirecting scopes.

## Random and host boundaries

Pinned ares samples Random on reads and TLBWR. Wired values 0..31 select from
Wired..31; values 32..63 select six bits, and TLBWR ignores indices above 31.
Wired=31 still consumes a sample when a stream is supplied. This is the pinned
reference's sampling model, not a claim about an instruction-clock Random
counter. Native startup selects its own deterministic stream (seed/sequence
zero); no claim is made that it reproduces the reference's unrelated preboot
entropy consumers or its observed GoldenEye replacement indices.

The small PCG sampler is adapted from the pinned ares `ares/ares/random.hpp`
under ISC. Its complete copyright/permission/disclaimer notice is included in
`cop0.h` and emitted C. No interpreter, CPU loop or instruction decoder is
reused. `runtime/test_random.py` checks every Wired value, 8192 reads/TLBWR
samples and complete resulting machine state with matching explicit reference
seeds. Sampling/range/ignored-index mutations are detected.

Context, Wired and XContext are global CPU state. The post-IPL receipt now
captures their actual values. A bounded traversal of a fixed guest host-boundary
implementation checks both branch arms, delay slots, direct calls and tails,
and retains all source words used to prove which global CP0 registers it cannot
write on its declared normal ABI paths. Unknown control flow kills the facts.
The host wrapper checks and pins those words; writes kill the corresponding
known bits. Context restore preserves surviving global facts and never
resurrects unknown ones. A mapped leaf stays inside its guarded source extent.
A mapped copy may borrow one unique fixed proof only when every dependency is
byte checked and is a physical alias through the callee's pinned TLB entry.
Different mapping owners, modified dependencies and active dependency writes
refuse. Synthetic multipart comparisons and mutations verify these obligations.
Normal SDK division, queue and PI-manager domains have explicit argument guards.
Queue guards admit empty/full nonblocking returns before checking the division
domain; the empty receive is compared with pinned ares and mutation checked.
Runtime capacity is checked after blocking before host division or writes.
A zero-capacity nonblocking send returns full before division, as the SDK does;
the retained synthetic covers this probe separately from unsafe division.

Cause.IP comes from the runtime's existing pending-event model through an
explicit callback. Exception delivery overwrites ExcCode/CE and establishes BD;
a nested architectural state transition still requires the prior BD/EPC facts.
The exception-state contract now compares both explicit Cause and live-IP
variants against real ares faulting instructions (120 cases, five mutations).
This retains the event model's existing limits rather than claiming raw RCP
interrupt fidelity.

## Iteration evidence

The first vector-enabled GoldenEye run stopped at VI 0, fault 12, PC `7f000bd0`
(previously VI 0, fault 3, transfer PC `80805d58`). Startup provenance and source
effect proofs now retain the required global CP0 facts. The guest fast vector
installs its invalid PTE pair and the retry enters the general handler. Allowing
that synchronous handler to mask IE/EXL advances to VI 1, fault 1, PC `808101e4`.
The handler loads its current-thread pointer from guest SDK state; the host
scheduler has not published that pointer, so the following store targets VA 20.
This is a new scheduler-state obligation, not a completed engine mapping. The
next change must discover and verify the SDK binding generally rather than
hardcode the observed address. No Rare/Nintendo logo or title claim is made.

Ignored receipts and PNGs are under
`target/receipts/tlb-exception-controls/ge-vector-boundary/`,
`ge-provenance/`, `ge-cp0-history/`, `ge-pager-prefix/` and `ge-pager-status/`.
The early framebuffer address is not yet an initialized VI image.

Object caching now separates generated CPU source from external RSP ABI header
dependencies, and limits RSP compilation to four jobs as CPU compilation does.
A synthetic CPU-header-edit measurement changed from 0.0697s (unnecessary GCC
rebuild) to 0.0190s (cache hit), retaining the identical object; changing the RSP
ABI still rebuilds. These are cache-contract timings, not whole-game speedups.
