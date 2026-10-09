# TLBP/TLBR translation-state effects

Question: do interpreted VR4300 `TLBP` and `TLBR` create translation-visible mapping mutations, or are their effects confined to CP0 observation/staging state?

Pinned references:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

The C++ fixture executes the real ares interpreter opcodes (`TLBP=0x42000008`, `TLBR=0x42000001`) with recompilers disabled. It snapshots all 32 TLB entries, primes and snapshots ares's four-entry TLB lookup cache, plants a sentinel in `devirtualizeCache`, and compares a known mapped translation before/after each operation.

Cases:

1. successful `TLBP` with two equal mappings at slots 9 and 17;
2. failed `TLBP` with misleading preexisting Index state;
3. `TLBR` whose selected entry differs from staged CP0 EntryHi/EntryLo/PageMask state;
4. same-value `TLBR` where staging already equals the selected entry;
5. out-of-range `TLBR` Index 63.

`model.py` separately adversarially demonstrates why treating any TLB-related CP0 delta as a mapping generation is unsound: probe/read operations can change Index or staging fields while the mapping array and translations remain identical.

Reproduce after exact refs exist under `.refs/`:

```bash
python3 -m py_compile experiments/tlbp-tlbr-effects/{run.py,source_guard.py,model.py}
python3 experiments/tlbp-tlbr-effects/model.py
python3 experiments/tlbp-tlbr-effects/source_guard.py
python3 experiments/tlbp-tlbr-effects/run.py
sha256sum target/ares-tlbp-tlbr-effects/results.json
```

The branch workflow clones both exact pins and runs the same commands. No ROM or firmware asset is required or committed.
