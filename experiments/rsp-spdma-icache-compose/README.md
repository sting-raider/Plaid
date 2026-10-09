# RSP -> reverse SP DMA -> I-cache composition

This experiment composes two previously established Plaid research contracts without turning payload equality into provenance:

1. decoded RSP DMEM writer generations can flow through completed reverse SP DMA RDRAM effects; and
2. an eligible identity-RDRAM I-cache fill captures backing generations into a distinct resident cache generation, which a later hit uses until the resident lifetime is invalidated/replaced.

`model.py` builds one deterministic 24-event history and independently replays it with explicit per-byte storage generations, ultimate roots and resident generations. It also corrupts seven histories and requires all seven to fail closed. Two intentionally unsound policies are measured as counterexamples: attributing a hit from *current* RDRAM, and resurrecting provenance from the latest equal cache tuple after a restore.

`source_guard.py` requires the exact `ares` revision pinned by `refs.lock.toml` and checks the source seams used by the composition: reverse SP DMA DMEM reads followed by `SP_DMA` RDRAM writes, cached CPU fetch selection, I-cache miss/fill/read, the `VR4300_ICACHE` burst requestor, and MI's RDRAM burst delegation.

## Reproduce

```bash
python3 -m py_compile \
  experiments/rsp-spdma-icache-compose/model.py \
  experiments/rsp-spdma-icache-compose/source_guard.py

python3 experiments/rsp-spdma-icache-compose/source_guard.py --ares .refs/ares
python3 experiments/rsp-spdma-icache-compose/model.py > /tmp/run1.json
python3 experiments/rsp-spdma-icache-compose/model.py > /tmp/run2.json
cmp /tmp/run1.json /tmp/run2.json
sha256sum /tmp/run1.json
```

This is a causal proof-composition experiment, not a new emulator execution or a hardware timing claim. The primitive execution receipts remain in the prior research branches; this artifact attacks whether those independently validated facts can be composed without losing writer/resident identity.
