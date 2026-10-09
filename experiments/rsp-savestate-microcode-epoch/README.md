# RSP savestate microcode restore epoch

This bounded experiment composes two already-validated Plaid results:

1. synchronized pinned-ares savestate loads are provenance epoch boundaries for restored executable state; and
2. completed RDRAM -> RSP IMEM SP-DMA requests create distinct microcode installation/writer generations even when payloads are equal.

The fixture creates snapshot S0 after a real one-fragment SP-DMA install of image A into RSP IMEM and captures selected RSP execution state. It then installs different image B, restores S0, installs byte-identical image A again, performs a same-value direct CPU IMEM write, and restores S0 a second time.

The external install/writer counters intentionally live outside ares serialization. The second restore is the critical adversary: IMEM bytes and selected execution state are already equal to S0 before load, but deserialization is still the operation that installs the post-load state. A naive latest-equal-image rule returns installation generation 3, and a naive same-value latest-writer rule returns writer generation 4. Both are causally false for the restored state.

`source_guard.py` checks the exact `refs.lock.toml` ares pin and asserts that RSP serialization directly includes IMEM, pipeline state, DMA pending/current/busy/full/clock state, GPRs/PC and branch state, while synchronized system load powers then deserializes RDRAM/CPU/RSP and does not replay SP-DMA in `RSP::serialize`.

`model.py` independently rejects forged latest-generation, wrong-snapshot, wrong-epoch and mixed CPU/RSP epoch certificates, then runs 50,000 deterministic abandoned-future histories to attack value-based joining.

Reproduce with the exact ares pin available as `.refs/ares`:

```bash
python3 -m py_compile experiments/rsp-savestate-microcode-epoch/{source_guard.py,model.py,run.py}
python3 experiments/rsp-savestate-microcode-epoch/source_guard.py
python3 experiments/rsp-savestate-microcode-epoch/model.py
python3 experiments/rsp-savestate-microcode-epoch/run.py
sha256sum target/ares-rsp-savestate-microcode-epoch/results.json
```

This is compiler-time exploration/savestate evidence, not a physical N64 hardware savestate claim.
