# MTC0 EntryHi ASID translation-context experiment

This bounded experiment asks whether an interpreted VR4300 `MTC0 EntryHi` can change the executable backing selected by already-installed non-global TLB entries without mutating any installed TLB entry.

Exact Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.
Exact ares pin: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

The fixture installs three non-global 4 KiB mappings for VA `0x4000` with ASIDs `0x11`, `0x22`, and `0x33`, backed by physical pages `0x1000`, `0x3000`, and `0x5000`. ASIDs `0x11` and `0x33` deliberately contain the same instruction bytes at different physical pages. A fourth global mapping at VA `0x8000` is the ASID-insensitive control.

Every context transition is performed by actual interpreted opcode `0x40885000` (`MTC0 t0,EntryHi`) with recompilers disabled. The fixture serializes every installed TLB entry before the matrix and rejects any change after each `MTC0`. It then executes one instruction through the mapped VA and records the physical address selected by the real TLB path plus the resulting GPR value.

Adversaries:

- ASID switch with no installed-entry mutation but different executable backing;
- equal instruction payload at a different backing page;
- identical repeated EntryHi write whose pre/post CP0 value is unchanged;
- global mapping under two distinct active ASIDs;
- unmatched ASID that must TLB-miss before execution.

`model.py` separately stress-tests a deliberately unsound reducer that caches VA->PA identity until a TLB entry write occurs. It also counts same-value EntryHi writes that are invisible to state-diff inference.

Reproduce after fetching exact pinned ares into `.refs/ares`:

```sh
python3 -m py_compile experiments/mtc0-entryhi-asid/{run.py,source_guard.py,model.py}
python3 experiments/mtc0-entryhi-asid/model.py
python3 experiments/mtc0-entryhi-asid/source_guard.py
python3 experiments/mtc0-entryhi-asid/run.py
sha256sum target/ares-mtc0-entryhi-asid/results.json
```

This is a mapping/context provenance experiment, not a proof of TLB reachability for arbitrary ROMs or a hardware timing characterization.
