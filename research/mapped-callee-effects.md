# Mapped callee source effects (ADR-0215)

## Hypothesis and counterexample

The inherited candidate resolved raw linked callees but accumulated authorized
slots globally. Its red synthetic test was correct: after one valid raw call,
a later call naming an unrelated placed analysis address, or a fallthrough into
that storage, could borrow the earlier authority. A placed PC is an analysis
representation, not an architectural executable binding.

Each queued path now carries its active binding. Nested calls restore their
caller's context, and mapped sequential/branch reads stay within that binding's
text. Explicit transfers may resolve another unique declared linked text or
fixed code; prior calls grant no persistent access. Tests retain both leak
forms, mapped-text escape and repeated legitimate raw calls.

## General proof and verifier

Resolution joins the exact map index, image/generation, unique linked text slot,
matching declared load, text extent, placed block and ROM source. All alternatives
are counted before eligibility filtering. Source offsets and raw/linked/placed
identities join the enclosing certificate hash, including identity placements.
A canonical non-return JR requires the existing current tail-cell certificate:
exact cell word, target list and evidence, followed by bounded no-write proofs
through every target. Cell words and every traversed instruction join the hash;
actual canonical return PCs are separate from arbitrary data words. Shared read
and depth limits reject rather than guess. This is a register-effect proof only;
normal return/global native binding gates retain their independent obligations.

Fresh CFG maps previously received load declarations after all analysis. New
optional source-context entry points validate image slots once at the public
boundary and install declarations/evidence before every proof round, including
address-taken, added-slot and layout rediscovery. Existing public APIs keep their
no-context behavior. Context carries the complete evidence set for independently
declared and inferred sources; an absent referenced source record rejects. The
CLI includes both supplied-load and inferred-overlay records. The pre-existing
explicit caller-slot source scope remains available without a new declaration;
it cannot authorize another alternate. A full-gate regression caught and retained
that compatibility distinction before acceptance. No observed DMA mappings are invented. Tail-cell analysis
precedes table analysis; final producer verification remains in place.

No rule names a game, guest symbol, source layout, address or table extent.
All committed tests are authored synthetic programs. No runtime MIPS execution,
ABI exception, assumed SDK boundary or new compatibility assumption is added.
Mapping generations, active native frames, text and source-cell guards are intact.

## Evidence and limits

Canonical main 8645d1c freshly discovers 56,813 blocks and solves scoped OPEN/11.
The candidate discovers 56,851 blocks and solves OPEN/9 with 162 loads. Two
previous blockers disappear and no new site appears. Other predecessor paths,
save/restore, stack-cell provenance and pointer relations remain open; no native
Paper Mario artifact/run is accepted.

Baseline discovery/solve: 26.975/16.510 s; initial candidate: 27.778/17.000 s.
These runs include concurrent work and do not establish a speed improvement.
The analysis remains bounded and source validation avoids whole-image hashing
inside each register-effect query. Final exact-source measurements are retained
in the receipt rather than substituted with these initial observations.

Authored native slot/bridge programs compare complete captured CPU/PC/RAM state
against ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 (ISC). Positive
bridge and affine loops match; clobbering/unknown-target/wrong-stride controls
refuse closure/lowering. Existing mapped-runtime contracts cover mapping/write
revocation, active pins and source-cell protection. No reference code is copied.
Pinned interpreter-ipu.cpp J/JAL/JR/LW semantics were inspected locally.

Four mutations are killed by semantic failures, with source restored afterward:
placed-source permission bypass, omitted binding hash, ignored callee GPR writes,
and dropped discovery load context. Additional tests reject stale cell/target,
changed source/generation, duplicate bindings, data tails and unrelated returns.

Ignored receipts are under target/paper-mario/0215-recovery/: baseline/ and
map.json/solve.json, regressions.json, fresh-controls.json, mutations.json,
effect-trace.log and gate/result.json. Retained maps stay byte-identical; baseline
and candidate solver responses match for SM64/MM/F-Zero X/OoT/BK. Some historical
certificates predate current proof hashes and reject identically on canonical
main; refreshed F-Zero X/BK controls compare newly generated maps as well. These
comparisons establish no regression, not a new visible game acceptance.

The exact-source gate is format, strict locked workspace/all-target Clippy,
locked workspace tests, CLI contracts, runtime contracts (including pinned ares)
and the pinned boot adapter. Progress data and README are unchanged. The branch
is prepared for primary-integrator review only; no push or main write is made.
