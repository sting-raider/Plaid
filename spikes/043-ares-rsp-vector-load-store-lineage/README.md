# RSP vector load/store lane-lineage spike

Question: can RSP vector-register provenance be represented as one origin after
partial/equal-valued loads, or must it retain byte-lane generations through later
stores?

This fixture executes real decoded `LQV`, `LRV`, `SQV`, `SRV` and `MTC2`
instructions in exact pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, with the RSP recompiler disabled.
It deliberately includes equal-payload sources, an all-`0x44` no-content-diff
case, partial loads, aligned-down LRV/SRV spans, and a decoded MTC2 clobber.

Run:

```bash
python3 spikes/043-ares-rsp-vector-load-store-lineage/model.py
python3 spikes/043-ares-rsp-vector-load-store-lineage/source_guard.py .refs/ares
python3 spikes/043-ares-rsp-vector-load-store-lineage/run.py
```

Generated executables/reference material and `target/` outputs remain ignored.
No ROM or reference source is committed.

The executable fixture is intentionally uninstrumented. Effective read lanes are
derived from guarded exact-pin interpreter source and executed instruction
inputs, not from a completed-read callback. This distinction is retained in the
result and research note rather than being inflated into ultimate provenance.
