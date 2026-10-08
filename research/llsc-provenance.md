# VR4300 LL/SC executable-mutation provenance

Date: 2026-10-08

Result: **PARTIAL**

Worker claim: `gpt56sol-llsc-provenance-20261008`

## Falsifiable hypothesis

A successful SC/SCD can be represented as a conditional executable-memory mutation only when the actual successful store boundary is observed. A failed reservation/fault/write must emit no mutation. Cached success must remain a cache-resident mutation until a verified D-cache writeback reaches backing memory, while an uncached identity-RDRAM success may be joined to the completed backing write.

The adversarial half of the hypothesis was that the pinned reference implementations might disagree on reservation state strongly enough that Plaid must not derive hardware reservation semantics from one emulator or from apparent emulator consensus.

## Exact pinned sources inspected

All revisions are from `refs.lock.toml`.

### ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`

- `ares/n64/cpu/interpreter-ipu.cpp`
  - `LL`: after a successful read, writes `scc.ll = access.paddr >> 4` and `scc.llbit = 1`.
  - `LLD`: same physical-granule LLAddr update and reservation set.
  - `SC`: if `scc.llbit` is set, assigns `rt = write<Word>(...)`; otherwise `rt = 0`. There is no `scc.llbit = 0` in the instruction.
  - `SCD`: same shape for `write<Dual>` and likewise no reservation clear in the instruction.
- `ares/n64/cpu/interpreter-scc.cpp`
  - `ERET` performs the pipeline return and explicitly clears `scc.llbit = 0` while leaving the LLAddr register distinct.
- `ares/n64/cpu/recompiler-ipu.cpp`
  - the cached fast LL path stores physical `paddr >> 4` to `SccLl` and sets `SccLlbit`;
  - conditional Word/Dual stores read `SccLlbit` to select whether cached data changes and to write the success result. No conditional-store reservation clear was found in the inspected fast path. Slow paths fall back to the interpreter.
- `ares/n64/cpu/memory.cpp`
  - CPU `write(...)` returns failure before mutation on failed devirtualization/access;
  - cacheable accesses mutate D-cache residency first;
  - uncached accesses route to the bus and return success after the bus write.
- `ares/n64/rdram/rdram.hpp`
  - identity-mapped in-range ordinary writes update actual RDRAM storage; translated/degraded/nonidentity paths are separate and remain outside this result.

Important source-level finding: at this pin, ares records LLAddr correctly but does not visibly consume `scc.ll` to qualify SC/SCD and does not clear `scc.llbit` on a successful SC/SCD in the interpreter. The inspected cached recompiler path also consumes `SccLlbit` without an observed clear.

### Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`

- `src/device/r4300/mips_instructions.def`
  - `LL`: successful aligned read sets the result and `r4300->llbit = 1`; no CP0 LLAddr update appears in LL.
  - `SC`: if `llbit` is set and `r4300_write_aligned_word` succeeds, it clears `r4300->llbit = 0` and writes success `1` to the target GPR; if no reservation, it writes `0`.
  - `ERET`: the pinned source explicitly executes `r4300->llbit = 0` before interrupt recheck.
  - CP0 LLAddr is writable through MTC0 handling, but code search at the exact pin found no LL/LLD path updating `CP0_LLADDR_REG`.

Important source-level finding: Mupen disagrees with the pinned LLAddr oracle even before subtle reservation lifetime questions; its LL/LLD source path at this pin does not publish physical LLAddr.

### Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

- `src/device/cpu_instructions.rs`
  - LL/LLD translate first, set `device.cpu.llbit = true`, and write `COP0_LLADDR_REG = phys_address >> 4`.
  - SC/SCD test `llbit`, translate the store, return on translation error, then clear `device.cpu.llbit = false` before the data write on the successful path.
- `src/device/cop0.rs`
  - `eret` selects EPC/ErrorEPC, updates status, sets exception pipeline state, and clears `device.cpu.llbit = false`.

Gopher64 therefore agrees with ares on LLAddr publication and with Mupen on clearing the reservation after a successful conditional store.

### n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

`src/tests/arithmetic/ll_sc.rs` is an independent hardware-directed oracle source. At this exact pin it asserts:

- LL sign extension and `LLAddr == physical_address >> 4`;
- LLD data and the same physical LLAddr rule;
- ordinary same-address SC/SCD succeeds and mutates memory;
- after LL/LLD followed by ERET, SC/SCD must fail, memory must remain unchanged, and LLAddr must remain nonzero;
- two distinct TLB virtual aliases mapped to the same physical page may execute LL through the first alias and SC through the second; SC must succeed and LLAddr must reflect the physical address.

This exact file does **not** include a repeated-SC-without-new-LL test or an SC-to-a-different-physical-reservation-granule test. Those two behaviors therefore remain unproven by this pinned oracle in this worker.

## Executable adversarial experiment

Artifact: `experiments/llsc-provenance/llsc_contract.py`

The harness encodes only the exact source transitions above, keeps the n64-systemtest obligations separate, and searches short LL/SC/ERET sequences for reference divergence. It also asserts the provenance contract for failed, cached, and uncached writes.

Reproduction:

```sh
python3 -m py_compile experiments/llsc-provenance/llsc_contract.py
python3 experiments/llsc-provenance/llsc_contract.py
```

Tested harness SHA-256:

`d3d94d86e59afce5bdcd1b78c54c6a2233cf4edfe8a77f74e8603628c5055dec`

Captured stdout SHA-256:

`5d5e0e0fb612e59ee35618972ee9511033178d5d2b35148941a3a17b76811855`

Canonical JSON body SHA-256 reported by the harness:

`2b76d9d77e2d556d13a56385190f30e32c54110a25b6f783f4851e942638fc70`

### Counterexample 1: LLAddr

The shortest reference divergence is a single LL. The ares/Gopher source models expose `physical >> 4`; the Mupen model leaves LLAddr at its prior value. This is directly relevant to Plaid because a tracer that uses Mupen's LLAddr state as a physical reservation provenance field would silently lose information required by the pinned system test.

### Counterexample 2: successful SC leaves different future reservation state

For:

```text
LL A
SC A <- 0x11111111
SC A <- 0x22222222
```

the source-derived models produce:

- ares: first SC succeeds, reservation remains set, second SC succeeds, final A = `0x22222222`;
- Mupen: first SC succeeds and clears reservation, second SC fails, final A = `0x11111111`;
- Gopher64: same one-success/one-failure shape as Mupen.

The pinned n64-systemtest file does not settle this repeated-SC case, so this is a **reference disagreement**, not a claim that ares is necessarily wrong on physical hardware. It is enough to reject ares-only reservation semantics as a proof basis.

### Counterexample 3: virtual address is the wrong identity

The pinned system test deliberately uses two different TLB virtual addresses for the same physical page and requires LL through one / SC through the other to succeed. Any Plaid certificate that binds the conditional store to the original guest virtual address would therefore reject a valid case. Reservation/provenance identity must be physical-backing aware.

## Provenance consequence

LL/SC should not be special-cased by trusting the architectural success GPR alone. The safe event boundary is the actual completed mutation:

1. If SC/SCD does not perform a successful write, emit no executable mutation.
2. If the successful store is cacheable, record a versioned D-cache resident byte/lane mutation; do not claim RDRAM changed yet.
3. Promote to backing mutation only when a verified D-cache writeback transaction reaches the corresponding physical bytes.
4. If the successful store is uncached identity RDRAM, it can be paired with the completed ordinary backing write and may create an immediate backing mutation generation.
5. ERET terminates the reservation, but does not itself erase LLAddr. A later failed SC must not create a mutation.
6. Virtual aliases cannot be used as mutation/reservation identity. Use translated physical backing plus the normal mapping-generation/lifetime rules.
7. Do not infer repeated-SC or different-physical-SC hardware rules from the pinned ares implementation or from emulator consensus. Those semantics are not required to observe actual successful mutations anyway.

This meshes with the completed cache/RDRAM work: current RAM bytes are not enough to explain a cached store, and a successful conditional store to a dirty cache line is not yet a backing write.

## What this disproves

- `SC opcode observed => executable bytes mutated` is unsound.
- `SC success flag alone => RDRAM bytes mutated now` is unsound for cached stores.
- `LL/SC reservation identity == guest virtual address` is contradicted by the pinned TLB-alias system test.
- `ares reservation state is safe as an N64-wide invariant` is unsupported because the exact pinned references already disagree after successful SC.
- `all mature references agree on LLAddr` is false at the pinned revisions.

## Limitations / remaining unknown

- No fresh physical-N64 execution was performed in this worker. n64-systemtest is used as an independent hardware-directed oracle source, not claimed as a hardware run from this session.
- The local environment could not clone the pinned repositories because outbound Git DNS failed, so no newly instrumented full ares/Mupen/Gopher build was executed. Exact pinned source was inspected through GitHub, and the deterministic contract harness was executed locally.
- Repeated SC without a new LL and SC to a different physical reservation granule remain unresolved hardware questions for the exact pinned test corpus.
- External-agent invalidation of a reservation by RCP/DMA writes, cache coherence interactions, interrupts other than the explicit ERET path, reset/save-state restore, TLB remap between LL and SC, reverse-endian modes, exception timing, and multi-core-style coherence are outside this experiment.
- SCD can affect eight bytes and still needs the same exact byte-span/mask/lane coverage being researched for general 64-bit stores.
- This experiment does not implement production trace schema or ProgramMap mutation generations.

## Recommendation

`ADOPT` the provenance rule: SC/SCD may contribute executable mutation provenance only at an observed successful cache/backing mutation boundary, with physical-backing identity and cache lineage. `INVESTIGATE` exact hardware reservation lifetime/address-match semantics separately if Plaid later needs to model LL/SC success itself rather than merely observe the resulting successful mutation.
