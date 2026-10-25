# SDK thread dispatch identification

Worker `thread-dispatch-contract-b249f29a`, prepared base
`f5c625630e2f62105a5f759986dcbdf8092c8d3c`; ADR-0272.
Recovered the uncommitted candidate from `t3-570c56c3`, whose last durable
evidence was over three hours old; its worktree is preserved. No child agents.
README is integrator-owned and untouched.

## Diagnosis and reference boundary

User-supplied Rogue Squadron USA Rev1, SHA256
`4813551d01d3a3474df3a51f84c31059cd2a9d1eeae7885dda51a88ee6b9f88d`.
An independent visible, silent 30-second request on the ADR-0271 artifact
reproduces VI 0, fault 12, PC `80025bf4`, RA `80025bb0`, with no SDK host
threads, framebuffer, graphics/audio tasks or PI transfers. Its elapsed
startup is 15.922 seconds on this machine; different GPU startup conditions
make that unsuitable for a throughput comparison.

The failing instruction is MTC0 Status at `__osDispatchThread + 0x54`.
This routine starts at `80025ba0`, pops the highest-priority runnable thread,
sets its state to running, intersects saved CPU IM with the global mask,
restores GPRs/LO/HI/EPC, conditionally restores FCSR/FPRs, intersects saved MI
with the global mask, writes the MI clear/set command and ERETs at `80025d20`.
`__osEnqueueAndYield` starts at `80025a38`; it saves the return continuation
and callee-saved state, reconstructs inhibited IM/MI bits and enqueues before
dispatch. `osCreateThread` at `80025180` initializes the standard OSThread
layout, Status `ff03`, MI `3f`, FCSR `01000800`, argument, entry, cleanup and
stack-minus-16. `osStartThread` at `8002bae0` handles stopped/waiting queues
and dispatches or yields according to priority. These addresses are diagnostic
evidence only; production identification has no game address or ROM hash.

The SDK family is differently compiled/scheduled relative to the pinned
n64sym variants. For example its dispatcher is `0x184` bytes versus the
nearby global-mask SDK `0x180` profiles, and its `0xd0` create uses different
global-reference/call offsets from n64sym's `0xd0` variants. This establishes
SDK-equivalent semantics, not an exact SDK release or compiler version.

Read-only references, verified at the lockfile revisions:

- n64sym `ccf4600f3389f1a84bde23339225cf372fdf7712`,
  `src/builtin_signatures.sig`: named SDK variants and relocation metadata;
  MIT, Copyright (c) 2017-2020 shygoo.
- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`,
  `ares/n64/cpu/interpreter-scc.cpp`: ERET selects EPC/ErrorEPC, clears
  EXL/ERL and LLbit, and polls interrupts; ISC.
- N64ModernRuntime `cdf5abbd5026fef5c364c676e4667c45e42b6863`,
  `ultramodern/src/threads.cpp` and `threadqueue.cpp`: public SDK APIs,
  host contexts and scheduling; repository COPYING is GPLv3. This is a
  behavioral comparison, not an oracle for every queue-ordering detail.

No upstream source or SDK/game instruction bodies are copied into production
or tests. Only normalized digests, extents and relocation/call metadata are
retained. Synthetic tests use project-authored miniature bodies. The existing
native scheduler and independently checked Status algebra remain the execution
contract; this work does not enable arbitrary guest dispatcher/ERET execution.

## Identification and verification

The candidate authenticates complete instruction bodies after normalizing
reviewed scalar data references, external calls, and function-relative internal
absolute jumps. Every external call must reach the authenticated named peer.
Repeated global references must agree; distinct globals may not alias. Duplicate
peers/globals refuse rather than choose an SDK copy. All 64 MI clear/set table
entries are checked. Missing text, holes, executable slots and changed internal
edges refuse. Public runtime declarations continue through the existing
ambiguity reconciliation and Status ABI verifier.

The SDK helper profiles establish dependencies; they do not add raw internal
dispatcher functions to the runtime API. Public create/start/stop/destroy,
priority and message functions use the existing host-thread scheduler.

Recognizing create exposes one previously hidden closure obligation at
`80007464`: its entry argument is loaded from a game-owned structure after a
conditional queue initialization. The existing bounded callback proof cannot
prove that load. It is not a reason to discard the SDK identification or
invent a constant target. ADR-0272 explicitly lists an unproven direct
`osCreateThread` argument as a residual transfer. Only that API's `a2` is
admitted, only with an unknown value, and only in residual mode. Known missing
targets, forwarded callbacks and other APIs/registers still refuse. Strict
mode is unchanged. Lowering exposes the existing emitted function set through
`plaid_enter`, preserving linked overlay binding/text checks and fault 3 for
anything outside that set. This creates no additional code roots or guest
instruction execution path. The manifest remains `native_complete: false`.

Recognizing the thread family first advances the game to `osGetThreadPri(NULL)`
at `8002a90c`, VI 0/fault 1, with a live host SDK thread. The unbound six-word
getter reads the guest running-thread global, which the host scheduler does
not maintain. A normalized full-body getter profile binds the existing runtime
getter; its shared global must agree with the authenticated SDK family. The
runtime contract checks both explicit-thread and current-thread priority.

## Acceptance receipt

The runtime test now observes all eleven O32 saved GPRs across real priority
preemption and a blocked receive, in addition to Status/IM/MI, priority and
queue memory. It checks current-thread and explicit-thread priority. Mutating
the generated native entry guard makes the same unknown-target refusal
assertion fail (mutant reaches a time-limit stop with fault 0); source is
restored. Strict-mode refusal and an ordinary emitted native worker are both
checked.

A bounded follow-up tested message-call saved-register summaries in the table
walk. Its positive/negative unit and runtime preservation tests passed, but it
did not recover the PI switch. The speculative production summary and its
unit test were removed; the useful scheduler register observations remain.
No table target is invented from an address or a snapshot.

The later stop is the SDK PI-manager message switch at `8002a2e4`, computed
target `8002a2ec`, with `s6 = 80000cb0`. Its seven ROM table words name
`8002a3cc,8002a2ec,8002a320,8002a3dc,8002a3dc,8002a354,8002a390`.
There is no decoded-code overlap at the table. Discovery has no candidates
for this site or decoded block at the selected case. The held base crosses
calls and a loop; the existing bounded all-path analysis has no surviving
witness. This remains an explicit native-only residual refusal, not a
scheduler/Status guard to bypass. No VI, graphics/audio task or PI transfer
is reached; the VI framebuffer register has been initialized to `00000280`.
The host scheduler has five live SDK thread records. Early window captures
race process teardown and show desktop pixels; they are not game frames.
No title/menu is reached, so there is no menu to drive with Start/A.

Ignored inputs, logs and receipts live under
`target/receipts/rs-thread-dispatch/`. Requested controls and the final
frozen-tree gate are recorded there and in the issue #4 closeout. The retained
ROM-content-verified load declarations are compiler inputs, not closure proof;
CPU/RSP C is regenerated from the final implementation and object reuse is
source/compiler/dependency/flag-hash checked. Every game window is visible and
SDL_AUDIODRIVER=dummy. Shared references and shim DLLs remain read-only; the
oracle is a private copy with verified pin, driver and recipe hashes. No
protected junction is recursively removed, and no ROM/assets/saves/screenshots
are committed.


Final-code Rogue Squadron request: 30 seconds, visible and silent; terminates
in 1.344 seconds with VI 0/fault 3/PC 8002a2e4/RA 8002a0cc, five SDK thread
records, framebuffer register 00000280 and zero graphics/audio/PI counts.
The retained-input pipeline takes 56.766 seconds with verified object reuse.
Before, the independent ADR-0271 request stopped at VI 0/fault 12/80025bf4
with no host threads (15.922-second cold window startup). These are different
stop points/startup conditions, not a game-speed benchmark. Final identification
has 25 functions; the build has zero residual blockers and 20 listed sites.

A matched compile-only comparison uses the same 2,280 native entries, unchanged
function bodies/boot payloads/compiler/flags and a sequential isolated pair:
direct entry cases 76.094 seconds, shared native function lookup 74.375 seconds.
No material compile speedup is established by this single pair. Reuse avoids a
second native entry implementation/table when the coroutine lookup is active;
the dominant remaining C compilation cost is outside this bounded change.
Exact commands, source hashes, counts and timings: lookup-timings.json. This
comparison changes only dispatch representation, not the SDK getter or map.
The generated source and object files remain ignored.
