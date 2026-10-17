# Status/interrupt boundary: next acceptance experiment

BK remains address-taken OPEN at `80259d30`, an exact `__osGetSR` signature.
Its caller at `80246f70` tests `0x1000`. This note records source observations
and the next verification boundary; it does not admit the function or define
a guessed boot Status value.

## Sources and current evidence

The local references match `refs.lock.toml`: ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, n64sym
`ccf4600f3389f1a84bde23339225cf372fdf7712`, and N64ModernRuntime
`cdf5abbd5026fef5c364c676e4667c45e42b6863`.

- ares `ares/n64/cpu/interpreter-scc.cpp` defines the architectural Status
  fields, sign-extended MFC0 result, Status writes and ERET transitions.
  `cpu.hpp` names RCP as interrupt line 2; it therefore uses Status mask bit
  `0x0400`. `exceptions.cpp` sets EXL on exception entry and separately
  models NMI/ERL. `interpreter-fpu.cpp` checks CU1 before COP1 execution.
- The signature-matched local SDK observations distinguish PRENMI's mask
  `0x1000` from RCP. The observed PRENMI handler clears that bit in saved
  thread state. Its effects across current/queued threads still need a
  retained differential test.
- The simple `__osDisableInt` clears IE and returns the previous IE bit.
  `__osRestoreInt` ORs its argument into Status. The current runtime's IE
  assignment incorrectly disabled an already-enabled context for argument 0.
  ADR-0193 fixes that IE operation and retains the synthetic differential in
  `runtime/test_interrupts.py`; the broader Status model remains open.
- The observed global-mask `osSetIntMask` preserves IE, replaces CPU IM
  using the request and `__OSGlobalIntMask`, and writes the six effective MI
  enables. Its returned previous mask reconstructs inhibited logical bits;
  when effective MI enables are zero, its MI return contribution stays zero.
  n64sym includes variants with and without that global-mask dependency.
- N64ModernRuntime's `librecomp/src/ultra_translation.cpp` leaves these
  interrupt functions empty. It supplies no architectural Status oracle for
  Plaid; copying those stubs would not establish equivalence.

No local SDK bytes, disassembly, ROM-derived code or reference implementation
were copied into this note or a runtime implementation. Emulator sources are
reference behavior, and the SDK observations need retained synthetic checks.

## Required state boundaries

Live CPU Status, a thread's saved Status, logical interrupt preferences,
effective MI enables and pending device conditions are separate state. A
single global Boolean cannot represent them. Saving a disabled caller and
dispatching a different enabled thread must preserve each context's state.
The all-blocked host event pump also needs an explicit idle/dispatch policy;
it cannot accidentally inherit the last blocked caller's IE forever.

The boot context must acquire its supported Status policy from a verified
boot/runtime boundary. Thread creation and dispatch need the actual saved
Status semantics, including clearing EXL on return. Full Status observation
also makes FR and CU1 visible. The existing FR=0 scope and lazy COP1 behavior
must be accounted for before `__osGetSR` can return a complete word.

Identification currently uses signature data relocations to reject lookalike
functions, but its public match records retain only entry/name/size. A
global-mask implementation must preserve the verified binding and SDK variant
for each selected function, including separate SDK copies in disconnected
images. It must not search for a game's globals at runtime or use one address
for every matching copy.

Every event-producing path needs an explicit eligibility boundary. In
`runtime/plaid_rt.c`, `deliver_pending` currently gates posted events on IE
alone and handles due timers directly. PI DMA completion paths can send their
completion messages directly through `mq_send`. These paths need review
alongside SP/SI/AI/VI/DP posting; changing only `post()` would leave bypasses.

## Smallest verification sequence

1. Implemented in ADR-0193: retain a synthetic counterexample for `RestoreInt(0)` in enabled and
   disabled contexts, plus nested disable/restore and valid 0/1 arguments.
   Check the ABI return values, preserved registers, PC, RAM writes and
   exception result against a synthetic pinned-ares reference sequence.
2. Model mask changes with a verified per-copy global-mask binding. Test all
   six MI enables, each CPU IM bit, preserved IE, zero-effective-MI return,
   partial global inhibition and old SDK variants. Unknown variants/bindings
   must remain unresolved.
3. Differential-test thread create/save/dispatch and event eligibility with
   pending RCP and Count conditions. Cover masked arrival, later unmask,
   restore, preemption, explicit yield and the all-blocked pump. Device
   acknowledgment/coalescing and delivery ordering need their own assertions.
4. Verify the supported boot Status, PRENMI saved-state transition and CU1/FR
   observations. Only then add the exact `__osGetSR` runtime boundary and
   repeat normal BK discovery/solve/build. A masked-bit-only observation
   would require a separately verified compiler transformation; it does not
   justify inventing the rest of the return word.

No runtime Status change or new runtime declaration is included in ADR-0192.
BK native VI, fault/PC and audio remain unmeasured until solve closes and the
ordinary visible native validation actually runs.
