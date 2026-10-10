# Reset HW2 -> NMI producer chronology

Bounded research experiment for the reset-button producer/latch gap left open by the existing NMI root work.

This experiment does **not** claim emulator delays or repeated-reset policy are N64 hardware truth. It source-guards exact pinned Mupen64Plus and Gopher64 revisions, executes a deterministic adversarial chronology model, and asks what facts can safely compose into Plaid's whole-ROM root proof.

## Reproduce

Create exact checkouts under `.refs-research/`:

```sh
mkdir -p .refs-research
# mupen64plus-core @ ba95bab92a76744753bfe61470823a4937850ab0
# gopher64 @ e96debac941a26ba4961e5145056c0821d3a56f7
python3 -m py_compile experiments/reset-hw2-nmi-producer/{source_guard.py,model.py}
PLAID_REFS=.refs-research python3 experiments/reset-hw2-nmi-producer/source_guard.py
python3 experiments/reset-hw2-nmi-producer/model.py
```

The branch-only workflow performs the exact checkouts, source guards, two byte-identical model executions, and artifact upload.

## Intended falsifiers

- repeated reset requests with equal type/count values;
- duplicate/stale event delivery;
- mismatched producer request identity;
- savestate restore of pending type/count rows without persisted producer identity;
- Gopher-style overwrite/coalescing of an already pending NMI slot;
- attempts to infer root identity from an equal pending value rather than a consumed causal event.

The only portable conclusion sought here is a proof obligation. Reference-specific timing/coalescing policy is preserved as disagreement.
