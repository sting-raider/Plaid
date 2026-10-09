# BEV=1 exception root -> PIF backing composition

This bounded research fixture composes a real BEV=1 guest exception transfer with the existing exact-pinned-ares PIF-ROM active-fetch witness.

It uses only a synthetic 1,984-byte PIF image. No Nintendo firmware bytes are committed.

## Reproduce

With `.refs/ares` checked out at the revision in `refs.lock.toml`:

```sh
python3 -m py_compile experiments/bev1-exception-pif-root/model.py \
  experiments/bev1-exception-pif-root/run.py
python3 experiments/bev1-exception-pif-root/model.py
python3 experiments/bev1-exception-pif-root/model.py
python3 experiments/bev1-exception-pif-root/run.py
```

The model output must repeat byte-identically. The executable runner builds baseline and instrumented binaries from exact pinned ares, runs all five modes twice on the instrumented binary, checks baseline/instrumented guest-state neutrality, and writes `target/bev1-exception-pif-root/results.json`.

Validated CI receipt: run `38004246774`, job `114069254414`, artifact `11651185304`.

Expected hashes from that receipt:

- model result: `5c08b240f42b970105354d53206871f4deeaacf1ccc94cc9e7bfc9e177517d16`
- instrumented evidence: `014521b49d3fe5bda2433d5328624af8e0d2284320df6b341c3d85e2ac662bf0`
- full generated results JSON: `27ae59f4f372e19b5d62150be3895412a23351ba2c45eb0d30c09952b7341853`

See `research/bev1-exception-pif-root.md` for the result, limits and closed-world impact.
