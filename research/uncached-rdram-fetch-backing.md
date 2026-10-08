# Uncached CPU instruction fetch -> ordinary RDRAM backing read

Status: **PARTIAL**  
Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`  
Scope: VR4300 uncached instruction fetches, ordinary successful identity-mapped RDRAM word reads only.

## Question

Can Plaid turn an uncached CPU fetch from RDRAM into a trustworthy byte-origin witness rather than merely recording the physical address and fetched value?

## Result

Yes for a narrow candidate contract, but the actual reference instrumentation still needs to be built and run. The critical source-level result is negative: `RBusDevice::VR4300_UNCACHED` is **not** an instruction-fetch discriminator.

Pinned `ares/n64/cpu/memory.cpp` has both:

- `CPU::fetch`: cached -> I-cache, otherwise `busRead<Word>(paddr)`;
- `CPU::read`: cached -> D-cache, otherwise `busRead<Size>(paddr)`;
- `busRead`: `bus.read<Size>(..., RBusDevice::VR4300_UNCACHED)`.

Therefore an ordinary uncached data load can have the same requestor, physical address and returned word as a later instruction fetch. A latest/equal-value join can fabricate executable provenance.

The downstream source chain is synchronous in the pinned source:

1. `ares/n64/memory/bus.hpp`: RDRAM physical addresses route to `mi.readRdram<Size>`.
2. `ares/n64/mi/bus.hpp`: for normal low RDRAM, EBus test mode diverts `VR4300_UNCACHED` accesses to `ebusRead`; otherwise it calls `rdram.ram.read<Size>`.
3. `ares/n64/rdram/rdram.hpp`: `Writable::read` handles non-identity translation/degradation first; in identity mode it rejects `address >= size`; only then does it return `Memory::Writable::read<Size>(address)`.

The relevant upstream Git blob SHAs observed through GitHub are:

- `ares/n64/cpu/memory.cpp`: `f362ef67ab41ccf57330bbedd6f614e07a61dd17`
- `ares/n64/mi/bus.hpp`: `2d61fa47b6ae568390df421036df4ffefd23b4e5`
- `ares/n64/rdram/rdram.hpp`: `c718ec2e9b2a78610353562cbc81dd973b278ee2`

## Falsified joins

The following are unsound as sufficient evidence:

- physical address + fetched word;
- physical address + fetched word + `VR4300_UNCACHED` requestor;
- latest ordinary RDRAM read at the same address/value;
- inference from current RDRAM contents after the fetch;
- treating EBus/remapped/degraded/failed paths as if they were identity backing reads.

The first three fail because data loads share the ordinary uncached requestor/path. The latter paths are explicitly distinct in pinned MI/RDRAM source.

## Candidate observer contract

Use a research-only per-fetch causal context, not a retrospective equal-value search.

1. After CPU fetch devirtualization and reverse-endian physical-address adjustment, if `access.cache == false`, allocate unique `fetch_context_id` immediately before `busRead<Word>`.
2. Keep this ID active only for the synchronous call.
3. In the identity branch of `RDRAM::Writable::read<Size>`, after the successful backing read and only for `Size == Word`, `device == VR4300_UNCACHED`, `mapIdentity == true`, and in-bounds address, emit `{fetch_context_id, physical, value}` if an uncached-fetch context is active.
4. When `busRead<Word>` returns, certify a witness only if exactly one such read was observed under the context and `{physical,value}` equals `{adjusted_paddr,fetch_result}`.
5. Clear the context on completion. No candidate can survive into another fetch.
6. Do not enter this contract for cached fetches. Their provenance belongs to the I-cache fill/residency lineage already being researched separately.

This context is necessary because the RDRAM `device` field only says which bus requestor class performed the access, not whether the CPU access was an instruction fetch or a data load.

## Adversarial experiment

`spikes/025-ares-rdram-uncached-fetch/source_contract.py` executes a fail-closed model of the proposed join and an intentionally unsound latest/equal-value competitor. Eleven deterministic cases pass, including an equal-value data-read decoy that the naive join accepts but the context-scoped join rejects.

Commands executed:

```sh
python3 -m py_compile /tmp/uncached/source_contract.py /tmp/uncached/source_guard.py
python3 /tmp/uncached/source_contract.py > /tmp/uncached/result1.json
python3 /tmp/uncached/source_contract.py > /tmp/uncached/result2.json
cmp /tmp/uncached/result1.json /tmp/uncached/result2.json
sha256sum /tmp/uncached/source_contract.py /tmp/uncached/source_guard.py /tmp/uncached/result1.json
```

Observed hashes:

- model payload: `5f4b13c41013445fa54598bbd3583a35608f09a15a837d1366e09fff70ed894f`
- pretty result: `fc7550528df86db8caaee0421b31eb83f6f678f2145e0e498b9087a4ea0de299`
- `source_contract.py`: `333a03d35b0d32f6eca7fc57f244bc86bf1a18af62a8051d67054acc6454a131`
- `source_guard.py`: `bafe9add5c8f6282ce35f66080aa3b81050514b03da76f37ceefe2362088bdef`

The source guard checks the exact pinned revision and the required source fragments when a local `.refs/ares` exists.

## Limitation

The worker environment had no DNS access to `github.com`; `git clone` failed before a local Plaid/ares checkout existed. Consequently no fresh ares binary was compiled and no instrumentation-neutrality run was performed. The exact source was inspected at the pinned revision through the repository connector, and the observer contract was stress-tested independently, but that is not equivalent to executing the reference implementation.

A real reference run is still required before upgrading this result to `VALIDATED`. It should reuse the guest-executed physical-fetch fixture and assert baseline/instrumented state identity, repeat-exact trace output, a witness on KSEG1/uncached identity RDRAM, no ordinary-read witness on KSEG0 cached execution, rejection of an equal-value uncached data-load decoy, and no witness in EBus/remapped/OOB cases.

## Integration recommendation

**INVESTIGATE.** Add the scoped uncached-fetch context and successful identity ordinary-word read hook in a follow-up executable ares spike. Do not infer uncached instruction provenance from `VR4300_UNCACHED` or from equal address/value alone.
