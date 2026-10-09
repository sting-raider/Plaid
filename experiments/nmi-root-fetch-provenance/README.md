# NMI root transfer versus executed PIF bytes

Status: in progress on isolated research branch.

This experiment composes two previously separate Plaid findings:

1. exact pinned ares external NMI transfers the CPU to `0xffffffffbfc00000` and leaves `nmiPending` asserted; and
2. an uncached CPU fetch can receive a PIF-ROM byte-origin witness only from the actual in-context PIF ROM backing read.

The falsifiable question is whether the architectural root transfer itself is enough to claim execution/provenance of the root bytes. The adversarial cases intentionally preserve the same architectural root PC while varying whether any fetch occurs and whether a returned equal payload actually came from PIF ROM.

`model.py` rejects root-address-only, persistent-pending, stale/foreign-read, equal SI-latch, wrong-context and wrong-offset histories. `run.py` builds baseline and generated-observer variants of exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, uses its supplied NTSC PIF ROM only as a local ignored input, and compares baseline/observer architectural state plus repeated observer output.

Run after fetching the pinned ares checkout into `.refs/ares`:

```sh
python3 -m py_compile experiments/nmi-root-fetch-provenance/{model.py,run.py}
python3 experiments/nmi-root-fetch-provenance/model.py
python3 experiments/nmi-root-fetch-provenance/run.py
```

No firmware bytes, binaries, traces or reference source modifications are committed. This fixture does not establish physical reset-button timing, hardware NMI latch semantics, root reachability for every declared scope, or a whole-ROM certificate.
