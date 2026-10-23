# Structural native coroutine jumps

Prepared base: b096f76d7f705f50c1aafcc5ccd312d610a4e208 (ADR-0260).
Reconciled validation base: 0966a8bcf031e2ce8aed4f5672773e6ec8ff5cd9.
Claim: complete a0-relative word save/restore bodies for sp, ra, s0-s7,
fp and f20-f31 can use caller-owned native continuations, without executing
guest instructions at run time. Before: Mario Party 2 USA VI 2, fault 5,
PC 80092e70. ADR-0262 records the production decision.

The recognizer accepts only canonical transfer order, distinct aligned
nonnegative offsets and exact return/result tails (25/26 words, or a
29-word restore with zero coerced to one). Instruction-byte verification
still guards the recognized leaf. Other shapes use ordinary checked lowering.
The builtin save lives in each lowered caller, including shared indirect
calls. The guest buffer remains real writable guest memory. An authored ra/sp edit can create a new native stack, entering an already-lowered
function. A directly authored initial buffer is also accepted only when its ra
is a compiled function entry and ra/sp are aligned. An unrecorded interior
continuation is never guessed. This refinement followed a local MP2 probe:
the first process buffer was directly initialized (entry/stack plus zeros),
while only the scheduler buffer had a preceding recognized save. Such edits have no static closed target proof, so the feature
requires residual dispatch; strict lowering refuses instead of claiming
native completeness. Builds without recognized routines retain their prior
function set; the coroutine entry hook is a faulting stub in those builds.

Host contexts belong to one libultra thread and share its baton. A saved
continuation resumes after setjmp, never after longjmp. An unchanged live
buffer can be restored repeatedly, including across multiple context handoffs.
A live saved frame keeps its context parked on an outgoing jump; a context
with no live save frame exits and releases its frames. The owning frame leaving invalidates the host continuation. Frames
carry their context and overlay index. Unwind walks the shared intrusive
list but removes only the owning context's discarded frames. The resumed
caller restores its full text pins after any narrowed call continuation.
The scheduler mutex is released before every builtin longjmp. Retargeting a
parked buffer to a compiled entry detaches only that saved handle. Other live
handles retain their stack. A stack losing its last handle retires on its own
host thread, releases its pins and acknowledges before replacement execution.

Deterministic verification (`python runtime/test_coroutines.py`):

- Creation with edited ra/sp from a returned template, sleep/yield, scheduler
  resumption, exit without setjmp, self-unwind through two lowered frames,
  and an indirect save selected from mutable RAM match pinned ares
  9408cb43d4948fc3ea6e152a307a34348df3fe04. Compare every 64-bit GPR/FPR,
  PC, HI, LO, FCC, FCSR and 64 KiB of RAM. The image is loaded at 80000000
  and native COP0 boot Status is explicitly declared.
- Directly authored creation without a preceding save also matches all 64 KiB
  of RAM against ares, and retains the same scheduler/yield/exit result.
- Repeated live-buffer restores (including zero returned literally by the
  plain restore), every saved GPR/FPR and FR=0/FR=1 agree with ares snapshots.
- A stopped higher-priority SDK thread resumes twice while another thread
  changes coroutine stacks. Only its active context runs, and foreign
  suspended frames remain pinned. A separate ownership probe interleaves
  real frame registrations and verifies every overlay counter during unwind.
- A missing-unpin mutation leaves stable leaked text pins and deterministically
  faults 2 when the guest overwrites the discarded text. A resumed-function
  text write also faults 2. A second mutation removes the resume re-pin: it
  incorrectly accepts that write and exits zero, proving this regression
  catches narrowed pins left behind on resume.
- Wrong call link, unrecorded/expired buffers, unknown/returned entries,
  misaligned authored ra/sp, edited callee-saved fields, cross-thread restores,
  unsupported foreign/repeated creation edits, live SDK thread destruction/reuse and a
  stale template after thread-slot reuse fail closed. Resource-cap probes
  verify fault 13 at 256 contexts and 4096 distinct buffer records.
- A parked process whose saved ra is retargeted to a compiled cleanup entry
  releases its last continuation and text pins. The replacement overwrites
  the discarded text and exits to the scheduler; all RAM matches ares.
- Recognizer unit tests flip every word of all supported tails and reject
  wrong bases, swapped transfer order and overlapping offsets.

Limits: fixed-text word-layout leaf routines only; copied buffers and other
layouts are not modeled. Abandoned parked stacks retain their pins and host
threads because the compiler has no guest buffer-liveness proof. They are
not silently reclaimed. Records are retained (linear lookup, 4096 distinct
addresses); contexts are capped at 256, with 64 MiB host stacks. Destroying
or reusing an SDK thread with live jump stacks or an active coroutine entry
is refused. Normal coroutine
entry return faults. The verified host is Windows x86-64 / MinGW GCC 15.2;
other host ABI/unwind mechanisms are not certified by this receipt.

No ROM or assets, runtime decoder, interpreter, JIT, new package dependency,
or reference code was added. GCC's builtin contract was checked at
https://gcc.gnu.org/onlinedocs/gcc/Nonlocal-Gotos.html: five intptr_t words,
longjmp value one, and the jump in a descendant helper. Pinned ares supplies
only the build-time differential oracle.

Validation measurements before canonical reconciliation: fmt 1.110 s,
Clippy 0.297 s, workspace tests 25.671 s and CLI 4.125 s; the first complete
runtime gate on the refined production code took 355.172 s. The final gate
is repeated after canonical reconciliation and the retirement refinement.
A clean initial MP2 pipeline took 767.234 s; the later cached pipeline took
about 243 s (02:58:41-03:02:44), with unchanged compiler flags and the new
coroutine semantics intentionally differing. These are wall times under
shared machine load, not a controlled compiler speedup claim. To avoid paging
on this 16 GiB host, later validation limits C compiler pools to two jobs;
the full cargo path is passed explicitly and each run gets a fresh temporary
directory to avoid PID-reuse collisions left by canceled analysis helpers.

Observed MP2 progression: original VI 2 / fault 5 / PC 80092e70; recognized
handoff initially exposed an unrecorded initial buffer; reusable scheduler
and retargeted cleanup continuations were then verified as general patterns.
The latest native run reaches VI 8, three audio tasks and 17 PI DMAs, stopping
with fault 8 at 80102800 (the overlay identity/binding guard). No guard was
weakened. The residual build still has zero blockers and eight residual sites.

Reconciled validation uses exact canonical base
0966a8bcf031e2ce8aed4f5672773e6ec8ff5cd9. Every game window remained visible;
SDL_AUDIODRIVER=dummy applied to every native run. The controls ran for
30 seconds with `python scripts/native.py <local-rom> --rt64 --seconds 30`.
A local wrapper supplies the full Cargo path, isolated temporary directories
and two compile workers; guest/runtime options and compiler flags are unchanged.
The pipeline times include analysis, cached builds and the native run.

| Game | VI | Fault | PC | Pipeline seconds |
|---|---:|---:|---|---:|
| Mario Party 2 | 8 | 8 | 80102800 | 290.922 |
| Banjo-Kazooie | 1795 | 0 | 00000000 | 196.703 |
| Majora's Mask | 1797 | 0 | 00000000 | 548.422 |
| Star Fox 64 | 1794 | 0 | 00000000 | 81.875 |
| Ocarina of Time | 1798 | 0 | 00000000 | 1069.032 |

Local acceptance on the resulting tree:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py` (includes the retained coroutine/ares and mutation contracts)
- `python tools/progress.py --check`

All must pass before exact-head CAS. The commit must be a direct child of
the validated canonical base; refetch/reconcile/retest on any main drift.
The integration SHA and final command timings are posted in issue #4.
Remaining MP2 work: authenticate/bind the executable overlay at 80102800,
without weakening the text identity or active-overlay guards. Residual entry
coverage is still explicit; this is not a fully native completeness claim.
