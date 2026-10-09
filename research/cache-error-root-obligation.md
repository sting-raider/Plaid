# VR4300 cache-error executable-root obligation

Status: **REJECTED hypothesis / validated negative result**

Date: 2026-10-09

## Question

Does the absence of a cache-error exception transition in Plaid's pinned ares reference reveal a missing executable root that a whole-ROM certificate must keep unresolved, or is that absence correct for the actual Nintendo 64 CPU target?

## Exact scope and pins

- Plaid integration base used by this research branch: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core inspected at `ba95bab92a76744753bfe61470823a4937850ab0`
- hardware document: NEC VR4300/VR4305/VR4310 User's Manual `U10504EJ7V0UM00`, Appendix B.1.7 / Table B-1 (also CacheErr register description in Chapter 4)

## Falsifiable hypothesis

The initial hypothesis was that pinned ares was incomplete as an oracle for cache-error executable roots: it exposes CacheErr state but no cache-error exception entry, so Plaid would have to retain an unresolved cache-error root unless a stronger target-specific source proved that class impossible.

The first half of that hypothesis is **rejected** for the N64/VR4300 target. The stronger target-specific source exists: the VR4300 manual states that the processor does not implement cache errors/cache parity and that the cache-error exception does not occur. Therefore ares's lack of an architectural cache-error vector is consistent with the target hardware, not evidence of a missing root.

The fail-closed qualification remains important: emulator silence by itself is not a certificate. The exclusion is justified by explicit target-hardware evidence.

## Source findings

### VR4300 hardware manual

Appendix B.1.7 explains that the VR4300 has no cache parity check. Table B-1 marks the cache-error exception as not occurring on the VR4300. The Chapter 4 CacheErr description says the register exists for compatibility and is not used by hardware. This resolves the root question for a declared Nintendo 64 / NEC VR4300 execution scope.

This is deliberately narrower than a generic MIPS III statement. Other MIPS implementations can have a real cache-error vector, so Plaid must not globalize the exclusion beyond the target CPU contract.

### Pinned ares

At the exact pin, `ares/n64/cpu/exceptions.cpp` implements ordinary/TLB exception entry and NMI but contains no CacheErr/cache-error exception entry. `ares/n64/cpu/interpreter-scc.cpp` labels COP0 register 27 as `cache error (unused)` and resets its emulated value to hardware value zero on writes. ares also has an EMUX/homebrew diagnostic use of the storage field; that emulator extension routes through the ordinary EMUX exception, so a nonzero internal `cacheError.unused` value must not be mistaken for an architectural VR4300 cache-error exception.

### Pinned n64-systemtest

The exact pinned hardware-oriented source contains `CacheErrorMasking`. It writes all ones to COP0 register 27 and expects readback zero. This independently matches the guest-visible register behavior exercised against ares here. This worker did **not** execute n64-systemtest on physical N64 hardware, so the test source is corroboration rather than a new hardware run.

### Pinned Gopher64 and Mupen64Plus

At the exact Gopher64 pin, `COP0_CACHEERR_REG` is commented out in `src/device/cop0.rs`; it supplies no separate cache-error exception oracle. The Mupen pin exposes CacheErr naming in debugger metadata, but this investigation found no stronger cache-error-root evidence there and does not use Mupen silence as proof. Neither source is needed to establish the hardware exclusion.

## Executed experiment

`experiments/cache-error-root-obligation/driver.cpp` is compiled against the exact unmodified pinned ares using the existing headless builder from `spikes/003-ares-oracle/run.py`.

For BEV=0 and BEV=1, guest code executes:

1. `MTC0` of all ones to COP0 register 27 (`CacheErr`);
2. two hazard-separating NOPs;
3. `MFC0` from register 27;
4. two NOPs.

The runner asserts, twice byte-identically per BEV case:

- CacheErr storage remains zero;
- guest readback is zero;
- EXL and ERL remain clear;
- a preset Cause exception code, EPC and ErrorEPC remain unchanged;
- execution does not enter any ordinary/TLB/reset/cache-error candidate vector;
- exact pinned source guards match the ares exception/SCC files, n64-systemtest CacheErrorMasking assertion, and Gopher64's commented CacheErr register constant.

GitHub Actions run `37915306472`, job `113769916013`, at code head `e414fb4f0a780a553e219f53752d66e5a9724835` completed successfully. Evidence artifact `11609697131` has digest `sha256:bfd1169d72df96c7d72bb12ad22cdb360c6a9f78302813a880a30227e3635ea0`.

No ares implementation source is patched by the experiment.

## Adversarial certificate model

`model.py` encodes the minimum proof rule rather than silently deleting the class:

- target `NEC VR4300` + explicit manual evidence `cache-error exception does not occur` -> `EXCLUDED_BY_TARGET_HARDWARE`;
- remove the hardware fact while keeping the same emulator pins -> `UNRESOLVED`;
- change the target to generic MIPS III -> `UNRESOLVED`.

The model was executed locally before publication and in Actions twice with identical output required. The canonical compact report payload SHA-256 is `aa7acaef54e2cb9965aff90aee1bedef8d25e5890e31a8be831ee0500f3124e3`. Local `model.py` SHA-256 was `83c5f29fb5162565dda441d8208573b20b3c9f7868b2ceb28d45c49d09d12b87`.

This adversarial case prevents an unsafe future rule such as `reference emulator has no transition => root impossible`.

## Result

**REJECTED**: for the Nintendo 64's NEC VR4300, the missing cache-error transition in pinned ares is not an emulator incompleteness that requires a new executable root. The target CPU does not generate that exception class.

For a whole-ROM certificate, the useful proof obligation is therefore an explicit *exclusion record*, not a seeded handler root:

`cache_error_exception = excluded_by_target_hardware(VR4300, U10504EJ7V0UM00)`

That record should be independently reviewable and target-scoped. An omitted field or mere absence of dynamic observations must fail closed.

## Limitations / what this does not prove

- It does not prove arbitrary exception reachability or handler-byte provenance for the exception classes that do exist.
- It does not close reset, NMI, interrupt, watch, TLB-mode, boot/PIF/CIC or other whole-ROM root obligations.
- It does not execute a deliberate physical cache fault on N64 hardware; the manual says the VR4300 has no cache parity/error mechanism to trigger such a case.
- It does not generalize to VR4000/VR4200/VR4400 or generic MIPS III CPUs.
- ares's EMUX/homebrew diagnostic use of the CacheErr storage field is emulator-specific and must not be promoted to an N64 hardware exception root.
- n64-systemtest was source-checked at the exact pin but not run on physical hardware in this session.

## Integration recommendation

**ADOPT** the target-scoped negative obligation: a Nintendo 64/VR4300 closed-world certificate may exclude cache-error exception roots only by carrying explicit hardware evidence for that exclusion. Do not seed a fictitious VR4300 cache-error handler, and do not implement a generic `emulator did not observe/model it` waiver.

## Reproduction

```sh
python3 -m py_compile experiments/cache-error-root-obligation/run.py experiments/cache-error-root-obligation/model.py
python3 experiments/cache-error-root-obligation/model.py
python3 experiments/cache-error-root-obligation/run.py
sha256sum target/cache-error-root-obligation/results.json
```

The branch-only workflow `.github/workflows/research-cache-error-root.yml` fetches and checks out the exact pinned reference revisions before running those commands.
