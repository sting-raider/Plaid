# Watch exception roots (VR4300)

Bounded research fixture for Plaid whole-ROM exception-root closure.

The hardware contract is taken from the **VR4300 User's Manual**, document
`U10504EJ7V0UM00`, 7th edition, sections 6.3.8 and 6.4.17. In particular:

- WatchLo bits 31:3 select a physical 8-byte block; R/W enable load/store traps.
- WatchHi bits 35:32 are compatibility storage and are not valid physical-address
  bits on VR4300.
- a matching enabled load/store raises Watch through the common exception vector;
  `CACHE` never does.
- EXL postpones Watch.
- WatchLo/WatchHi are undefined after reset, so software must initialize them.

This directory deliberately separates three questions:

1. `model.py` encodes the bounded hardware-root/certificate obligations and attacks
   them with reset-unknown, same-value-generation, lane-alias, CACHE, BEV and EXL
   forgeries.
2. `source_guard.py` checks exact `refs.lock.toml` pins. At the audited ares pin,
   WatchLo is guest writable and serialized and `Exception::watchAddress()` maps
   to ExcCode 23, but no N64 execution call site references that wrapper. The
   other guarded references expose/register Watch state without supplying an
   independent Watch trigger/test in the audited paths.
3. `run.py` builds unmodified pinned ares through `spikes/003-ares-oracle/run.py`.
   The guest executes `MTC0 $t0,$18`, hazard NOPs, then a matching or adversarial
   `LW`/`SW`. Results are executed twice and must be byte-identical.

The purpose is **not** to bless any emulator omission as hardware truth. A hardware
manual/reference disagreement is a closure blocker unless stronger evidence
resolves it.

## Reproduce

Populate `.refs/` at the exact revisions in `refs.lock.toml`, then run:

```sh
python3 experiments/watch-exception-roots-gpt56sol/model.py
python3 experiments/watch-exception-roots-gpt56sol/source_guard.py
python3 -m py_compile \
  experiments/watch-exception-roots-gpt56sol/model.py \
  experiments/watch-exception-roots-gpt56sol/source_guard.py \
  experiments/watch-exception-roots-gpt56sol/run.py
python3 experiments/watch-exception-roots-gpt56sol/run.py
sha256sum target/ares-watch-exception-roots/results.json
sha256sum target/ares-watch-exception-roots/source_guard.json
```

The branch-only workflow `.github/workflows/research-watch-exception-roots.yml`
performs the exact-pin checkout, model, guards, build, execution, hashing and
artifact upload from a clean Ubuntu runner.
