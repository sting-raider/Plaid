# Actual consumption of installed RSP IMEM

Extend the existing RSP SW/LW/ADDU -> DMEM -> CPU LW -> IMEM SW chain with
one actual execution of the installed legal NOP. Full initial/final IMEM images
include the controlled host program seeds; explicit seed observations cut byte
ancestry even when the bits repeat. Existing instruction-prologue sensing uses
the fetched word once. The fixture selects single issue for the NOP so the
lookahead instruction cannot accidentally execute.

```sh
python spikes/060-rsp-installed-imem-fetch/run.py
python spikes/060-rsp-installed-imem-fetch/run.py --verify-existing
python scripts/test_rsp_definitions.py --execution --source target/rsp-installed-imem-fetch-primary/source.json
```

The unchanged-reference baseline, disabled sensor, enabled sensor and repeat
agree on all seventeen independent machine/timing/exception checkpoints, CPU
steps, reported state and full bank/RAM hashes. The independent complete census
expects97 events, six definitions and seventeen fetched instructions. It replays
the full4096-byte IMEM image/writers and compares every fetched word/byte parent.
Exactly one fetch retains the CPU install writer, which links back to the first
copy's original-clock RSP load/ADDU/store definitions. Other code roots remain
opaque. Default v0/v1/v2 fixture behavior stays unchanged.

This controlled v3 profile establishes discrete consumption, not a continuous
executable lifetime or complete mutation census. General inputs, DMA, asynchronous
writers, cache/TLB/reset/restore interleavings, hardware consensus and whole-ROM/
native closure remain OPEN; all corresponding certification flags remain false.
Sources/binaries/reference shadows stay ignored under target, with ISC notices.
