# Spike 034: ares EBUS hidden-RAM fetch provenance

This spike tests the pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` hidden-RAM transform used by MI EBUS-test uncached VR4300 reads and a fail-closed fetch-witness reducer.

It deliberately does **not** treat the EBUS result as a four-byte copy. At the pinned revision, `RDRAM::Writable::ebusRead<Word>` calls `HiddenRAM::nibble(mapped & ~3)`. `HiddenRAM::nibble` reads two hidden storage bytes and constructs a value as `((raw0 & 3) << 2) | (raw1 & 3)`. Thus a fetched 32-bit word has only four source bits in this model.

`probe.cpp` includes the exact pinned `ares/n64/rdram/hidden.hpp` against minimal type/memory stubs. It exhausts all 65,536 pairs of raw hidden bytes, verifies the 16-value output space, exercises ordinary `HiddenRAM::update<Word>` and EBUS `ebusScatter<Word>`, and checks address-to-hidden-storage separation.

`run.py` source-guards the exact CPU fetch, MI EBUS route, RDRAM EBUS transform and HiddenRAM formula, builds/runs the probe twice, and runs adversarial reducer cases. A qualifying fetch witness is typed `derived_hidden_bits`; cached/EBUS-off, wrong-address, malformed-transform, ambiguous in-scope hidden events and out-of-scope events fail closed.

Reproduce from a Plaid checkout with `.refs/ares` at the pinned revision:

```sh
python3 -m py_compile spikes/034-ares-ebus-hidden-fetch/run.py
python3 spikes/034-ares-ebus-hidden-fetch/run.py
sha256sum target/ares-ebus-hidden-fetch-spike/results.json
```

The branch workflow `.github/workflows/research-ebus-hidden-fetch.yml` clones the exact pinned ares revision before running the same commands.

Limit: this validates the exact pinned-ares transform and a conservative witness contract. It is not a physical-N64 hardware proof. Pinned Gopher64 and Mupen expose the MI EBUS mode bit but do not provide an independently matching hidden-RAM fetch implementation in the inspected source paths.
