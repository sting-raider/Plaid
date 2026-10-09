# Spike 044: exact ares TLBWR mapping generations

This bounded spike tests whether VR4300 `TLBWR` replacement identity can be reconstructed soundly from ordinary architectural snapshots, CP0 Index, or payload equality.

The exact pinned ares source contract is guarded at `9408cb43d4948fc3ea6e152a307a34348df3fe04`. The fixture executes real interpreter opcode `0x42000006` with recompilers disabled.

Cases:

- `Wired=31`, CP0 Index=7, target payload also present in slot 7: the first `TLBWR` must mutate only slot 31 and leave Index unchanged.
- a second `Wired=31` write of the exact same entry: the instruction still executes and clears the devirtualization cache, but pre/post TLB snapshots are identical.
- `Wired=30`, 32 unique writes: every concrete changed slot must be 30 or 31 while CP0 Index remains unrelated.
- `model.py` stress-tests snapshot-diff, CP0-Index and payload-match inference rules with deterministic adversaries.

Reproduce after checking out the exact ares pin under `.refs/ares`:

```sh
python3 -m py_compile spikes/044-ares-tlbwr-mapping-generation/{run.py,source_guard.py,model.py}
python3 spikes/044-ares-tlbwr-mapping-generation/model.py
python3 spikes/044-ares-tlbwr-mapping-generation/source_guard.py
python3 spikes/044-ares-tlbwr-mapping-generation/run.py
sha256sum target/ares-tlbwr-mapping-generation/results.json
```

No upstream source is patched or instrumented. Exact slot identity for the deterministic same-value case follows from `Wired=31` plus the guarded pinned-source `getControlRandom()`/`TLBWR` contract; the deliberately unchanged snapshot is the counterexample.
