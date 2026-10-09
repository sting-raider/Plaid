# KSU / X-bit exception-root composition

Worker: `gpt56sol-ksu-exception-root-compose-20261010`  
Base: `main` at `211176e7a489fecf8331d02915ee982cd279cb62`  
Research branch: `research/ksu-exception-root-compose-gpt56sol`  
Result: **PARTIAL**

## Question

When Plaid composes an executable-fetch fact with an exception-root fact, which VR4300 Status state must be part of the proof? In particular, do KSU plus UX/SX/KX change whether a virtual instruction fetch can reach a TLB refill root (`base+0x000` or `base+0x080`) versus faulting first to the general vector (`base+0x180`)?

This composes the previously validated exception-vector work in `research/ares-exception-vectors.md`; it does not replace that work.

## Exact references

From `refs.lock.toml`:

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

The CI source guard additionally pins the Git blob identities of the exact ares and Gopher64 files used by the argument.

## Executable experiment

Artifacts:

- `experiments/ares-ksu-exception-roots-gpt56sol/driver.cpp`
- `experiments/ares-ksu-exception-roots-gpt56sol/run.py`
- `experiments/ares-ksu-exception-roots-gpt56sol/source_guard.py`
- `experiments/ares-ksu-exception-roots-gpt56sol/proof_model.py`
- `.github/workflows/research-ksu-exception-roots.yml`

Validated GitHub Actions run:

- run: `38002963082`
- validated branch commit: `d78fb1f8e502e1e63dc6943aacdf16e6f44fcfe7`
- 23 cases, each run twice and required to be byte-identical
- result JSON SHA-256: `62d35b5e3806a938420a2f02a35af1371d1a29cab848fa7eeb0ebf6b8969d04a`
- uploaded artifact: `ksu-exception-root-results`, artifact id `11650255524`

Reproduction:

```sh
git clone https://github.com/ares-emulator/ares.git .refs/ares
git -C .refs/ares checkout --detach 9408cb43d4948fc3ea6e152a307a34348df3fe04
git clone https://github.com/gopher64/gopher64.git .refs/gopher64
git -C .refs/gopher64 checkout --detach e96debac941a26ba4961e5145056c0821d3a56f7
python3 experiments/ares-ksu-exception-roots-gpt56sol/source_guard.py
python3 experiments/ares-ksu-exception-roots-gpt56sol/proof_model.py
python3 experiments/ares-ksu-exception-roots-gpt56sol/run.py
sha256sum target/ares-ksu-exception-roots-gpt56sol/results.json
```

## Validated ordinary composition

For the exact pinned ares interpreter with EXL=ERL=0:

1. KSU selects kernel, supervisor, or user mode.
2. KX, SX, or UX respectively selects 32- versus 64-bit addressing for that effective mode.
3. Address canonicality and segment legality precede TLB-miss root selection.
4. A forbidden/unused or noncanonical instruction address raises AdEL and reaches `base+0x180`.
5. A mapped true TLB miss reaches `base+0x000` in a 32-bit context and `base+0x080` in a 64-bit context.
6. BEV changes the base but not that offset classification.
7. EXL/ERL force effective kernel mode; nested misses are already covered by the prior vector experiment as general-vector cases.

The executable matrix validated representative cases across:

- kernel/supervisor/user 32-bit low mapped regions -> `+0x000` true refill;
- supervisor 32-bit `sseg` -> `+0x000`;
- user access to supervisor-only 32-bit space -> AdEL `+0x180`;
- non-sign-extended 32-bit VA -> AdEL `+0x180`;
- kernel/supervisor/user 64-bit mapped regions -> `+0x080` XTLB refill;
- supervisor 64-bit `xsseg` / compatibility `csseg` -> `+0x080`;
- user accesses to those supervisor-only regions -> AdEL `+0x180`;
- BEV=0 and BEV=1 representatives.

The exact pinned n64-systemtest source independently contains a 45-case `Privilege: memory accesses` matrix covering the same kernel/supervisor/user 32/64-bit segment distinctions and expected `TLBL` versus `AdEL` outcomes. This is a test-ROM expectation corpus, not a new hardware execution performed by this worker.

## Adversarial reference disagreement: ares RDRAM fast path

Pinned ares `memory.cpp` performs this check before `switch(segment(vaddr))`:

```text
0xffffffff80000000 .. 0xffffffff83efffff -> direct cached RDRAM PhysAccess
```

But its own mode-specific segment helpers classify compatibility KSEG0 as unused in supervisor and user mode.

The executable fixture planted `ADDIU $v0,$zero,1` at physical RDRAM 0 and fetched from `0xffffffff80000000`. Exact pinned ares did this:

| case | declared segment result | actual pinned-ares result |
|---|---|---|
| kernel 32 | execute | execute |
| supervisor 32 | AdEL | **execute** |
| user 32 | AdEL | **execute** |
| supervisor 64 | AdEL | **execute** |
| user 64 | AdEL | **execute** |

All four privilege-attack cases set `$v0=1`, left EXL clear, and advanced PC by four. They were repeated byte-identically.

Boundary controls at `0xffffffff83f00000`, immediately beyond the fast-path window, produced AdEL / `base+0x180` in supervisor and user mode for both 32- and 64-bit contexts.

Therefore the discrepancy is specifically explained by implementation ordering in the pinned ares fast path, not by the broader segment helpers.

This worker does **not** promote either side of that discrepancy to hardware truth. The pinned n64-systemtest privilege matrix does not directly test supervisor/user `0xffffffff8000xxxx` inside this exact shortcut window, so the hardware answer for that precise adversarial address remains unresolved here.

## Gopher64 cannot arbitrate this lane

At its exact pin, Gopher64 `translate_address` special-cases KSEG address bits and otherwise enters TLB lookup without consulting KSU/UX/SX/KX. Its TLB-miss vector logic selects `0` or the default `0x180`, with no 64-bit `+0x080` XTLB choice.

It is therefore useful evidence of a reference limitation/disagreement, not an independent oracle for mode-sensitive roots.

## Failed hypothesis / harness correction

The first executable attempt assigned every ares TLB entry `{}` intending to create an empty TLB. That instead created VPN-zero entries which matched low addresses but were invalid, so `0x4000` correctly produced TLB-invalid `+0x180` rather than a true-miss refill.

The corrected fixture preserves deterministic reset TLB state, matching the previously validated exception-vector fixture, and clears only the lookup cache. This is another concrete example of the project's rule that a zero/equal value is not evidence of absence or provenance.

## Proof-system consequence

A root witness cannot be keyed only by numeric VA and numeric vector PC. The minimum causal context for this composition is:

- exact Status generation (not merely equal Status bits);
- effective privilege mode after EXL/ERL override;
- the mode-selected UX/SX/KX width;
- faulting VA and segment-legality classification;
- the TLB state/generation needed to distinguish true miss from matching-invalid/modification;
- BEV generation/base;
- resulting exception classification and root.

`proof_model.py` adversarially verifies the generation-binding rule. It rejects:

- reusing a root witness after a same-value Status rewrite;
- joining equal numeric roots from user and supervisor contexts without their generation;
- treating every 64-bit-context fault as XTLB refill when segment legality should produce AdEL;
- missing/UNKNOWN Status generation;
- nested EXL state being interpreted with the stored user KSU/UX state.

For the ares fast-RDRAM window, an ares execution observation alone is insufficient to discharge the segment-legality obligation. Plaid must either have stronger hardware/system-test evidence for that scope or keep the obligation OPEN.

## Closed-world impact

This closes the ordinary KSU/X-bit composition rule for representative mapped and forbidden regions at the pinned ares implementation and aligns it with the pinned n64-systemtest privilege expectation matrix. It also finds a concrete reason not to treat the pinned ares interpreter as hardware truth for all privileged instruction-fetch addresses.

A whole-ROM certificate that observes only `{VA, fetched bytes, exception vector}` can be unsound because:

- the same VA can be legal or illegal under distinct Status generations;
- the same true-miss VA can select `+0x000` or `+0x080` depending on mode-selected address width;
- equal numeric roots do not identify equal causal contexts;
- reference fast paths can bypass architectural checks.

## Remaining gap

Run a focused hardware/system-test case for supervisor and user instruction fetch or data access inside `0xffffffff80000000..0xffffffff83efffff`, with 32- and 64-bit addressing modes, and compare against the exact pinned references. Until that is done, hardware truth for the ares shortcut window remains OPEN.

## Integration recommendation

Do not integrate an emulator-specific fast-path rule. Integrate the **certificate obligation** instead:

- mode/root composition must be bound to exact Status and TLB generations;
- segment legality must be proven before a true-miss root is accepted;
- UNKNOWN/missing mode provenance keeps closure OPEN;
- reference disagreement in the ares fast-RDRAM window must remain explicit.
