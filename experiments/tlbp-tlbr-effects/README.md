# TLBP/TLBR translation-state effects

Question: can interpreted VR4300 `TLBP` and `TLBR` be treated as translation observers that never need a translation-context generation?

Result: **no for TLBR** in exact pinned ares. `TLBR` does not replace a TLB entry or invalidate ares's translation caches, but it copies EntryHi into staged CP0 state. Because ares matches non-global mappings against the current staged EntryHi ASID, TLBR can change mapped-VA reachability without any installed-entry mutation. `TLBP` only changed Index/probe state in the bounded dynamic matrix.

Pinned references:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

The C++ fixture executes real ares interpreter opcodes (`TLBP=0x42000008`, `TLBR=0x42000001`) with recompilers disabled. It snapshots all 32 TLB entries, ares's four-entry TLB lookup cache and `devirtualizeCache` around each instruction.

Cases:

1. successful `TLBP` with equal mappings at slots 9 and 17;
2. failed `TLBP` with misleading prior Index state;
3. `TLBR` ASID `0x22 -> 0x55`, making a non-global VA become translatable;
4. reverse `TLBR` ASID `0x55 -> 10`, making the same VA become untranslatable;
5. same-value `TLBR`;
6. out-of-range `TLBR` Index 63.

`model.py` then runs 20,000 deterministic adversarial histories. It distinguishes **TLB-entry mapping generations** from **translation-context generations**. Treating any CP0 delta as an entry write fabricates entry generations; tracking only entry writes misses TLBR ASID context changes.

`source_guard.py` additionally records a reference-model divergence: pinned ares consults active EntryHi ASID during mapped loads/stores, while pinned Mupen's inspected legacy fast-LUT translation path contains no active-ASID predicate. Pinned n64-systemtest source explicitly includes ASID-dependent TLB use tests. This is why the durable note does not convert emulator behavior into an unqualified hardware invariant.

Reproduce after exact refs exist under `.refs/`:

```bash
python3 -m py_compile experiments/tlbp-tlbr-effects/{run.py,source_guard.py,model.py}
python3 experiments/tlbp-tlbr-effects/model.py
python3 experiments/tlbp-tlbr-effects/source_guard.py
python3 experiments/tlbp-tlbr-effects/run.py
sha256sum target/ares-tlbp-tlbr-effects/results.json
```

Expected exact-pin result JSON SHA-256: `d72a9ff4876eb18ab46f0bad95d1cb701c8cc1fe20366278243731ae9a3924c3`.

No ROM, firmware, or copyrighted game asset is required or committed.
