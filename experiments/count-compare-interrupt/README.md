# Count/Compare interrupt producer experiment

This branch-only experiment composes the already-validated maskable-interrupt root/gate with the VR4300 Count/Compare timer producer. It does **not** modify Plaid production code or any pinned reference implementation.

## Questions

1. Can normal Count progression latch timer pending/IP7 and thereby reach the existing `base+0x180` interrupt root when IE/IM7/EXL/ERL permit it?
2. Does a Compare write acknowledge a latched timer, including a same-value rewrite whose visible register value does not change?
3. Does a Count write acknowledge a latched timer?
4. How do Count rewrites affect the future Compare deadline, including wrap/equality cases?
5. Do exact pinned references agree strongly enough to promote Count-rewrite timing to a hardware/closure invariant?

## Evidence

`driver.cpp` builds against exact pinned ares through `spikes/003-ares-oracle/run.py`. Both CPU and RSP recompilers are disabled. It executes 16 scenarios twice each, including two real guest `MTC0` paths, and checks producer state plus the already-established interrupt root.

`source_guard.py` pins and source-guards exact ares, Gopher64, Mupen64Plus Core and n64-systemtest revisions from `refs.lock.toml`. It deliberately preserves a Count-write scheduling disagreement: ares uses its rewritten Count against fixed Compare, Mupen removes/recreates `COMPARE_INT` at Compare after queue translation, while Gopher64 translates every enabled event (including Compare) and therefore preserves the old relative Compare deadline.

`model.py` is an adversarial causal model, **not** a hardware oracle. It demonstrates why same-value Compare writes need ordered operation/generation identity and why a value-only `(Count, Compare)` snapshot cannot explain timer pending/acknowledgement history.

## Reproduce

With the exact refs checked out under `.refs/`:

```sh
python3 -m py_compile experiments/count-compare-interrupt/{source_guard.py,model.py,run.py}
python3 experiments/count-compare-interrupt/source_guard.py
python3 experiments/count-compare-interrupt/model.py
python3 experiments/count-compare-interrupt/run.py
sha256sum target/count-compare-interrupt/{source_guard.json,results.json,model.out}
```

The branch workflow `.github/workflows/research-count-compare-interrupt.yml` performs the same sequence from clean exact-pin clones and uploads the evidence payloads.
