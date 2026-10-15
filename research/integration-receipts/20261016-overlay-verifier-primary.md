# ADR-0172: native relocated-byte verifier generation

Milestone 5; base `3e6ef1e147532b1fa1624a6d3175a372ad7d73e3`.
Claim: issue #4 comment 6202599095.

`plaid_lower::overlay::verifier` emits C that validates a freshly loaded
overlay's entire relocated file and zeroed BSS. It uses the parsed relocation
sites and compile-time instruction fields; no guest decoder is emitted.
Expected bytes are patched in bounded temporary storage, never guest RAM.
The caller gets failure for an invalid base, insufficient RAM, allocation
failure or any mismatch. Numeric section IDs permit multiple verifiers in
one translation unit. Registration after data/BSS mutation is deliberately
not accepted by this initial-entry contract.

The synthetic fixture exercises MIPS32/26/HI16/LO16 at five RAM bases,
including signed-low carry, reused and interleaved high halves, segmented
pointers, data-only files, every-byte corruption and allocation failure.
Explicit arithmetic assertions supplement comparison against the existing
Rust relocation model. `runtime/test_overlays.py` compiles generated C with
`-std=c11 -O2 -Wall -Wextra -Werror` and runs these checks; the canonical
runtime suite invokes it. Generated C and executables stay under `target/`.

Required final gate: fmt, strict locked workspace/all-target Clippy, locked
workspace tests, CLI tests, runtime tests, spike096, progress record/check,
and diff review. The issue #4 closeout records final PASS/CAS. No RSP changes:
spike097/098 retained evidence remains sufficient; no new capture or rebuild.
No reference source was copied and no ROM/map/capture/game-derived output is
part of this change. Shared-checkout indexing changes remain separate.

This lands one compiler component, not complete overlay support. The fixed
lowerer and runtime entry dispatch do not yet call it. Next compose native
overlay functions with verified bindings, generation invalidation, relocated
calls/returns and ares execution differentials. No milestone becomes CLOSED;
OoT's fixed-code blockers, title and audio campaign remain open.
