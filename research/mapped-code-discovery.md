# Replay-authenticated mapped instruction discovery (ADR-0236, partial)

Prepared base: 20b8ddf78765c9313996d8e5dee9fde0a3466db1.
Hypothesis: the pinned reset replay can authenticate a first mapped fetch and
its produced physical RAM extent, then supply unchanged virtual instructions
through the existing native TLB content/generation/frame binding. No runtime
MIPS interpreter, decoder or JIT is added.

## Contract and implementation

The analysis adapter observes the game's own TLBWI and reads synchronized TLB
entries without issuing guest TLB or bus accesses. It requires a unique global,
valid, sign-extended 32-bit virtual mapping into identity-backed RDRAM. The
produced extent stays within the selected even/odd half; every 4 KiB boundary
and the final byte are rechecked against competing entries. Produced bytes,
including observed reset/IPL writes before game entry, must cover the entire
captured instruction. Unsupported producers, incomplete words, nonidentity RAM,
ambiguous/ASID mappings, stale instruction-cache lines and fetch/RAM mismatch
refuse. Ordinary KSEG0 snapshots retain their previous post-entry producer rule.

The new ares_tlb declaration names a virtual link, first-fetch entry, physical
RAM source, text bound and whole-ROM source (offset zero). Composition reruns
reset from the supplied ROM and checks virtual/physical identity and exact
extent, rather than accepting a saved RAM file. Bytes stay unchanged in synthetic
analysis storage: J/JAL retain their virtual-PC region. Discovery now follows
mapped direct and register tail transfers as well as calls, preserving guest
targets and rechecking the existing slot contract in the solver.

Lowering uses the ADR-0205 native executable binding and adds the captured
physical source to its descriptor. The live mapping must cover every 4 KiB
boundary with one entry and contiguous physical bytes. Full content, mapping
generation, active frame pins, remap/clear preflight and protected-write checks
remain in force. Ordinary ares_boot declarations reject mapped captures; invalid
physical fields, including the unbound sentinel, cannot pass mapped layout
validation. No mapping/source assumption is silently converted to proof.

Pinned ares source inspected at 9408cb43d4948fc3ea6e152a307a34348df3fe04:
ares/n64/cpu/tlb.cpp, cpu.hpp and interpreter-scc.cpp (ISC). It is an
analysis/test oracle only. No upstream guest semantic implementation is copied
into Plaid's native artifact, and no game addresses/constants enter production.

## Synthetic evidence

scripts/test_ares_boot.py executes synthetic MTC0/TLBWI code in pinned ares,
then observes the first virtual fetch of CPU-produced instructions. Exact-entry
replay returns identical physical bytes. Non-global and invalid variants do not
supply executable images. The retained ordinary cache, partial-producer,
source/alias, completed-DMA occupant and replay tests remain mandatory.
Python harvest tests cover declaration identity, no duplicate append, range,
physical alignment, missing/empty/partial data and entry mutations. Rust tests
cover capture hashing/ranges, mapped register-tail discovery without guest
address rewriting, and physical-sentinel/source/entry layout rejection.

runtime/test_tlb_execution.py retains its complete native/pinned-ares state and
RAM comparison, plus atomic remap/clear, generation, active frame, data-cell and
byte-tamper controls. An additional constrained physical descriptor executes the
same native program, then refuses an equal-content copy at another RAM address.
Removing only the physical comparison from an ignored generated copy triggers
the new assertion (native exit 3221226505, harness rc 1). Restored code passes.
Evidence: target/mapped-0236/{mutation.log,tlb-restored.log,ares-final.log,
mapped-core.log}; the complete final gate reruns these retained contracts.

## ROM pipelines and limits

Both normal commands use user-local ROMs and --rt64 --seconds 60. GoldenEye's
previous no-source target is now decoded from a first-fetch virtual image whose
physical source is the observed IPL RAM window. Blocks increase 348 -> 3716.
Ordinary/residual results are OPEN 341/331 (10 residual sites). New blockers are
106 invalid table entries, 85 unresolved direct targets, 78 unmapped targets,
34 indirect targets, 16 table obligations, seven callbacks, three scope effects
and two unsupported-instruction obligations. These are newly exposed frontiers,
not a completed native game. The one old unmapped boot transfer is resolved.

MK64 remains 40610 blocks, ordinary/residual OPEN 13/10 (three residual sites):
four missing targets, four direct edges and the ERET instruction/scope pair.
The first timed rerun takes 123.877 s and exits 1. A separate initial attempt hit the
Windows executable lock while another Plaid command still ran; it was retried
once those commands finished. This is not reported as an analysis result.

Both pipelines stop before lowering/build/native validation, so no window,
VI/frame/audio result or 60-second gameplay run exists. No new native-complete
artifact is emitted. ERET is not lowered in this partial: EPC/ErrorEPC, Status
EXL/ERL transitions, LL state and interrupt/event effects still need their own
native/pinned differential contract. ISA coverage stays 203/209; progress data
is unchanged. Existing BK/MM native regressions are not changed or repaired.

Ares-produced mapped slots do not yet acquire open-call observations: replay
site projection refuses them until it can compare the replayed image's source
identity in the observation pass. GoldenEye's next harvest records that refusal.
Contiguous produced RAM is a conservative candidate text extent, not a proven
code/data boundary. Native binding overlap with fixed executable protections
remains fail-closed; no acceptance of that overlap is claimed. Direct mapped ROM,
ASID-sensitive/wide mappings, later overlay lifetimes and exhaustive closure
remain open. The core-only boot evaluator still refuses unknown COP0 startup
state; the extended pinned reset replay is this milestone's harvesting path.

## Discovery controls and timing

Retained input declarations/runtime IDs regenerate byte-identical complete maps
against the ADR-0235 baselines:

| ROM | Blocks | ADR-0235 seconds | ADR-0236 seconds | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| BK | 81465 | 90.234 | 29.020 | b41011d9f0a7d626a49ca6cebfe0b042dd27c606cf69cec7efb427745b2b9467 |
| F-Zero X | 28119 | 25.157 | 4.802 | 92ef76696f942aa543b11f43bd073fb25137937cb7ab93039135e221d850c05f |
| MM | 214963 | 217.782 | 173.214 | a52eb0e427e338a178a99b82d1fd8e996ac203c94f48905317b1b734cefc0603 |

These are operational timings amid concurrent bisect/build work, not controlled
speedups. Startup producer invalidation clears its 8 MiB history only on an
identity-to-nonidentity transition, avoiding a full clear per bus write. Warm
release compilation after the tail-discovery change took 15.14 s. The retained
mapped replay reported 1.625 s (before the final boundary hardening). Final
pipeline and gate timings are recorded below after exact-tree validation.

Canonical gate: python X:/Plaid/target/paper-mario/0222/gate.py, with
GATE_TREE=X:/Plaid/target/cop0-0235 and GATE_OUT=X:/Plaid/target/mapped-0236-gate.
All five return codes must be zero; cargo test must really compile/run the full
workspace on the final tree. Gate JSON, complete logs and final commit/tree
identity remain ignored evidence. DECISIONS is appended as bytes to preserve
its existing CRLF representation and historical non-UTF-8 byte.

## Prepared-tree gate and review

The first complete five-step run returned zero throughout: fmt 1.2 s, Clippy
13.9 s, workspace tests 16.6 s, CLI 9.4 s, runtime 318.3 s (359.4 s summed).
Its test log contains 907 passing tests and one ignored. Subsequent review added
one layout rejection test and the missing-provenance negative for mapped tails,
and disallowed ordinary boot declarations from accepting mapped captures.
Focused mapped tests then pass (four unit and six integration tests). Those
hardenings require a fresh complete gate on the committed candidate before CAS.
The earlier gate is preserved as target/mapped-0236/initial-gate/; it is not
substituted for the final exact-tree gate. Review covered correctness, retained
fail-closed boundaries, byte/source trust, runtime overlap limitations, bounded
work and unchanged ordinary controls. No correctness objection remains within
the declared partial scope. README will receive the actual production commit
hash in a separately validated direct-child documentation landing.
