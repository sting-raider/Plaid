# Checked BREAK paths in callee effect proofs (ADR-0211)

Base: `2144c30fd152fc7dcf41c8edf8aaab4de69d14de`.

A remaining dispatch crosses a callee chain containing guarded divide-error
BREAK paths. The no-write summary rejected these words even though the native
artifact already aborts there, under ADR-0138. They cannot reach a normal
call continuation. This is a terminating path in the existing supported model,
not a proof that the BREAK branch is unreachable on actual hardware.

Use the existing solver BREAK predicate, which matches native lowering's
opcode/function pair. After checking the current mapped instruction source,
count and hash the exact word and stop traversing that path. A BREAK does not
establish a normal return. BREAK-only functions and BREAK in a delay slot still
reject; unsupported exception paths and all prior register/control/source
checks remain unchanged. Ordinary static scope still reports the BREAK-site
blocker; guarded scope retains the explicit BREAK assumption. No exception
handler or resumed execution is modeled, and no assumption is added or retired.

The authored integration regression is RED at the base and GREEN with this
change. Replacing BREAK with a required-register write rejects the proof.
A unit fixture checks the hashed terminating word, absence of a normal return,
and delay-slot refusal. The guarded integration fixture closes while ordinary
scope remains OPEN at the BREAK PC. The native non-aborting call loop equals
pinned ares over full register, PC, FPU and RAM checkpoint state. Its taken
BREAK variant reports native fault 9 at the exact source PC. These abort checks
are checks of the declared fault boundary, not full exception-handler fidelity.
Independent Luna review found no findings; it inspected the assertions and
adjacent solver/lowering paths but did not run tests.

The fresh ROM-only Paper Mario pass improves from OPEN/14 to OPEN/13, still
56,799 blocks and 162 inferred loads. The five-entry site at `80131e30` closes,
with no new blocker sites. Prototype production code at
`199711fec90d914a70ffb8aceb241cf58d4283b1` was built and probed; receipts remain
ignored under `target/paper-mario/0211/`. Native emission remains refused.

The new checkout initially lacked the pinned reference and then built a fresh
oracle cache. That cold discovery took 305.827 seconds. After bootstrap,
repeating discovery took 31.502 seconds and solve 9.955 seconds, with map and
solve files byte-identical to the cold pass. Prior milestone discovery/solve
took 25.614/16.224 seconds. These are operational single-run timings, not a
controlled compiler performance claim. Optimized incremental compilation took
64.850 seconds after changing the source checkout and reusing a target cache.
The exact final tree still requires the complete canonical local gate.
