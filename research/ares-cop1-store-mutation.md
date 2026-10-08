# ares VR4300 SWC1/SDC1 executable-byte mutation semantics

Status: **VALIDATED** for the bounded pinned-ares semantics and executable matrix below. Cross-reference transaction topology is **PARTIAL**: ares, Mupen64Plus, and Gopher64 agree on the architectural store surface but do not expose the same number of implementation-level backing writes for `SDC1`.

Plaid base inspected: `codex/executable-discovery` at `5a24b9ccf3064d96f2f0d50fd3df1e50ee6d4862`.

Research branch: `research/cop1-store-mutation-gpt56sol`.

Executable experiment: `spikes/035-ares-cop1-stores/`.

Pinned references:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`;
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`;
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`;
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`.

## Question and hypothesis

The integrated 64-bit integer-store work explicitly left COP1 stores uncovered. The bounded question was whether `SWC1` and `SDC1` can mutate executable bytes through a path that integer-store-only sensing would miss, and exactly how FR mode, cacheability, alignment, TLB failure, and CU1 gating affect that mutation in pinned ares.

Starting hypothesis:

1. `SWC1`/`SDC1` are distinct executable mutation sources even though they reuse the ordinary CPU memory-write machinery after extracting raw FPR bits;
2. uncached identity-RDRAM stores synchronously change backing, while cached stores initially change only D-cache-resident bytes and dirty state;
3. FR=0 odd-register selection aliases the architectural even/odd pair, while FR=1 selects the named FPR independently;
4. CU1-disabled, misaligned, and failed-translation stores do not mutate backing or dirty D-cache state;
5. observing only integer store opcodes is therefore unsound for executable immutability.

All five are validated for the pinned ares scope.

## Pinned ares source map

### COP1 handlers and FR selection

`ares/n64/cpu/interpreter-fpu.cpp`:

- `SWC1` first checks `Status.CU1`; if disabled it immediately raises coprocessor-1 unusable. Otherwise it calls `write<Word>(effective_address, FT(u32))`.
- `SDC1` has the same CU1 gate, then calls `write<Dual>(effective_address, FT(u64))`.
- `fgr_t<s32>` implements FR=0 odd-register selection through the high 32-bit half of the even FPR pair and FR=0 even-register selection through the low half. FR=1 selects the named FPR.
- `fgr_t<s64>` aliases odd to even in FR=0 and selects the named FPR in FR=1.
- the unsigned `u32`/`u64` accessors reuse those signed raw-register views; no floating arithmetic or conversion is performed by the store.

For the deterministic seed used by the spike:

- raw `f0 = 0x1122334455667788`;
- raw `f1 = 0x99aabbccddeeff00`.

The resulting adversarial cases include:

- FR=0 `SWC1 f0` -> `0x55667788`;
- FR=0 `SWC1 f1` -> `0x11223344`;
- FR=0 `SDC1 f0` and `SDC1 f1` -> `0x1122334455667788`;
- FR=1 `SWC1 f1` -> `0xddeeff00`;
- FR=1 `SDC1 f1` -> `0x99aabbccddeeff00`.

`spikes/035-ares-cop1-stores/model.py` independently models those rules and runs 100,000 deterministic randomized FPR-selection cases. Result:

```text
PASS: COP1 FR payload-selection model and 100000 adversarial register cases
model_sha256=3c5075ecc450af75d167dd3a225943c410e6dcc1e0f4c4877604f08f353aa285
```

### Translation, cache, and backing paths

`ares/n64/cpu/memory.cpp`:

- aligned/address checks and translation occur before the concrete cache/bus write;
- cached writes route to `dcache.write<Size>`;
- uncached writes route to `busWrite<Size>`;
- little-endian CPU context applies a physical-lane transform before the concrete cache/bus access.

`ares/n64/cpu/dcache.cpp`:

- a cacheable `Word`/`Dual` write mutates the resident line and sets dirty bits;
- backing RDRAM does not change synchronously at the store checkpoint;
- later writeback is a separate backing event.

`ares/n64/memory/bus.hpp` and `ares/n64/mi/bus.hpp`:

- uncached RDRAM `SWC1` reaches `MI::writeRdram<Word>`;
- uncached RDRAM `SDC1` reaches `MI::writeRdram<Dual>` and, for ordinary RDRAM mode, one `rdram.ram.write<Dual>` call in this implementation.

This is an implementation transaction shape, not a hardware atomicity proof.

## Independent reference/source checks

### Mupen64Plus Core

At `ba95bab92a76744753bfe61470823a4937850ab0`:

- `mips_instructions.def` checks COP1 usability before `SWC1`/`SDC1` memory writes;
- `SWC1` sources the value through `r4300_cp1_regs_simple` and calls `r4300_write_aligned_word`;
- `SDC1` sources through `r4300_cp1_regs_double` and calls `r4300_write_aligned_dword`;
- `cp1.c::set_fpr_pointers` encodes the same FR=0 pair aliasing: single-precision odd/even indices select opposite 32-bit halves of the even pair, while double-precision odd/even indices point at the same even pair;
- `r4300_write_aligned_dword` ultimately performs two ordered `mem_write32` calls, one at `address+0` and one at `address+4`.

Thus Mupen corroborates the architectural payload selection and mutation surface, while exposing a different implementation-level `SDC1` write decomposition from ares.

### Gopher64

At `e96debac941a26ba4961e5145056c0821d3a56f7`, `src/device/cop1.rs`:

- both stores gate on CU1 before translation;
- `SWC1` translates a write address, retrieves the single FPR payload, and performs one `data_write`;
- `SDC1` retrieves the double payload and performs two 32-bit `data_write` calls at `phys_address` and `phys_address + 4`;
- `get_fpr_double` pairs even/odd 32-bit registers when FR=0 and uses the named 64-bit register when FR=1.

Again, the semantic 8-byte store agrees while the implementation-level transaction topology differs from ares.

### n64-systemtest hardware-oriented evidence

Pinned n64-systemtest contains FR-mode tests showing the architectural even/odd pairing behavior in half-register mode and COP1-unusable tests specifically covering `SWC1` and `SDC1` when CU1 is disabled. These support the register-selection and CU1 expectations, but they do not prove the exact ares cache/backing chronology or the simultaneous CU1-disabled-plus-misaligned precedence case.

## Executable experiment

`driver.cpp` links against an exact checkout of pinned ares using the existing Plaid ares-oracle build helper. CPU and RSP recompilers are disabled. No ares CPU/FPU/memory instrumentation is inserted; the harness invokes the real interpreter handlers and observes raw RDRAM, normal guest aliases, exception state, and D-cache dirty state.

`run.py` executes every logical case twice and rejects nondeterministic output. The final matrix contains **192 logical cases / 384 process executions**:

- 2 opcodes: `SWC1`, `SDC1`;
- 2 FR modes;
- 4 FPR indices, covering two even/odd pairs;
- 2 endian contexts;
- successful uncached and cached stores;
- aligned unmapped-TLB failures;
- misaligned failures;
- CU1-disabled aligned stores;
- CU1-disabled plus misaligned adversarial stores.

GitHub Actions run `37849165859`, job `113557497444`, branch commit `cee4d0dde1a5f0a5f4d92106106b92fc92dca50b`, checked out exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` and reported:

```text
PASS: 192 repeated pinned-ares SWC1/SDC1 cases
results_sha256=f85760603c11f51ede16e4a9d4b4965703c6a635e5b925401d8014494ab68e05
```

## Findings

### 1. COP1 stores are a real executable-mutation coverage gap

A policy that concludes executable memory is immutable after checking integer store opcodes is unsound. `SWC1` and `SDC1` can write arbitrary raw FPR bit patterns into the same cache/backing paths used by integer stores.

The right observation layer is the general concrete CPU memory-write/mutation path, with enough metadata to retain architectural cause where useful. Adding a growing opcode allowlist is the wrong abstraction.

### 2. FR mode changes byte provenance, not only floating-point interpretation

For provenance, `ft` is not a sufficient source identity by itself. In FR=0:

- odd `SWC1` sources the other 32-bit lane of the even/odd pair;
- odd `SDC1` aliases the same 64-bit value as the preceding even register.

In FR=1 the named FPR is independent. Therefore a source-byte witness for COP1 stores must include the effective FR mode and the architectural lane/pair selection, or normalize to the actual raw payload bytes before creating the mutation witness.

### 3. Cached and uncached chronology matches the general CPU-write model

For every successful uncached pinned-ares case:

- guest-visible target bytes changed to the independent model's payload;
- raw RDRAM backing changed synchronously;
- no D-cache dirty state was created.

For every successful cached case:

- the cached guest view changed;
- the D-cache line became dirty;
- raw RDRAM and the uncached backing alias remained unchanged at the immediate post-store checkpoint.

Therefore the COP1 instruction event is not itself a sufficient backing-provenance witness for cached stores. A later dirty-line writeback remains a separate chronological event.

### 4. Tested failure paths produce no backing/cache mutation

In the final matrix:

- aligned unmapped-TLB cases raised store-TLB failure and left raw backing unchanged with no dirty line;
- misaligned cases raised address-store failure and left raw backing unchanged with no dirty line;
- CU1-disabled cases raised coprocessor-unusable with CE=1 and left raw backing unchanged with no dirty line;
- CU1-disabled plus misaligned cases still took the COP1-unusable path in pinned ares because the handler checks CU1 before calling the memory helper.

The last precedence result is pinned-ares behavior, not claimed here as a separately hardware-validated VR4300 invariant.

### 5. Reference-level backing-write count is not an architectural invariant

Pinned ares carries `SDC1` as one `Dual` write down to one ordinary `rdram.ram.write<Dual>` call. Pinned Mupen64Plus and Gopher64 both decompose their `SDC1` implementation into two 32-bit writes.

Therefore Plaid must not treat "number of emulator callbacks" as proof of physical N64 transaction count or atomicity. For executable provenance, preserve the concrete observed callbacks of the selected oracle, but normalize semantic byte effects separately and require stronger evidence before promoting callback topology into a hardware invariant.

This is especially relevant to the current actual-backing-transaction blocker: an oracle's convenient function boundary is evidence about that oracle, not automatically about the R4300/RDRAM bus.

### 6. Two failed harness revisions exposed observer-state traps

The first exact-reference run failed because the harness assumed the little-endian guest byte view and raw RDRAM physical layout were identical. They are not; ares applies a size-dependent physical-lane transform to normal little-endian CPU accesses.

The second run failed because the harness compared a post-exception guest alias against a pre-exception alias. Exception entry recomputes CPU context, so the presentation of a later read can change even when memory did not mutate.

The final fault oracle therefore uses raw backing plus D-cache dirty state below the changed exception context. These failures are retained as useful instrumentation lessons rather than hidden as test cleanup.

## Plaid implication

For executable discovery/provenance, adopt a general CPU mutation event rather than integer-opcode sensing. It should be capable of representing at least:

- concrete destination byte range and cache/backing location;
- raw payload bytes;
- architectural cause (`SWC1`/`SDC1`) when available;
- effective FR mode / normalized FPR lane source if source provenance is required;
- cached resident mutation separately from later backing writeback;
- virtual/physical alias and endian context;
- chronological grouping without assuming that one architectural store equals one hardware or oracle callback.

## Limitations / remaining unknowns

- The executable matrix validates pinned ares, not real-hardware bus atomicity.
- Mupen/Gopher checks here are pinned source-oracle comparisons, not executable differential runs.
- n64-systemtest supports FR/CU1 architectural behavior but does not certify cache/backing chronology or every combined-fault precedence case used by the harness.
- The little-endian cases directly force ares CPU context to probe handler semantics; they are not a proof of every architecturally legal reverse-endian/TLB mode setup.
- This does not cover `LWC1`/`LDC1` provenance into FPRs, FPR-producing arithmetic/conversions, source-byte provenance across prior FPR history, RSP stores, DMA/copies, decompression, or I-cache visibility after the mutation.
- It does not prove whole-ROM executable closure.

## Recommendation

**ADOPT** the bounded result: include `SWC1`/`SDC1` in the general executable-mutation surface and place sensing below opcode-specific integer handlers. Preserve cache/backing chronology and normalize actual payload bytes rather than treating an FPR number as sufficient provenance.

**INVESTIGATE** any attempt to use emulator callback count as a hardware transaction proof. The pinned-reference `SDC1` decomposition disagreement is a concrete counterexample to that shortcut.

Do not merge this branch wholesale. The primary integrator should transplant the mutation-observation requirements and regression cases into the canonical instrumentation/verifier design.

Primary reproduction, 2026-10-09: the 100,000-case payload model and all 192
repeated actual ares handler cases pass on WSL Ubuntu x64 G++ 15.2. Model and
actual result digests reproduce the worker receipts exactly. The runner adds
Windows/WSL dispatch; no reference semantics or expectations change. Primary
local source inspection also confirms the Mupen/Gopher two-Word decomposition
against ares's Dual path. Only ares executes here; forced little-endian handler
contexts and combined-fault precedence retain the limits recorded above.
