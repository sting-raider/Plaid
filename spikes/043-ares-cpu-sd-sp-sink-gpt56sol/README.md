# Exact-pinned ares integer `SD` to SP memory

This isolated spike asks one question: when interpreted VR4300 integer `SD` targets CPU-visible RSP DMEM or IMEM, what storage effect actually completes at the SP device boundary?

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Exact references:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

The ares source path is `CPU::SD -> write<Dual> -> Memory::IO::write<Dual> -> RSP::writeWord`. The executable fixture records the completed `RSP::writeWord` effect with the existing project-owned SP observer shadow. It tests DMEM and IMEM, changed-value and same-value successful stores, misalignment, and the 32-bit user-mode reserved-instruction case. Every observer-enabled/disabled process is repeated and architectural/storage state is compared for neutrality.

`run.py` also contains a bounded adversarial replay. In particular, a same-value successful store must still mint a writer generation even though a byte-difference census sees no changed byte. Forged opcode-only, wrong-half, invented-eight-byte, wrong-bank and fault-with-sink histories are rejected.

`crosscheck.py` independently guards the exact pinned source topology. At these revisions ares' RCP `Dual` adapter contains one `writeWord` call, while Gopher64 integer `sd` contains two `data_write` calls including `phys_address + 4`. That comparison is reference evidence only, not hardware truth.

Run after checking out the exact references into `.refs/ares` and `.refs/gopher64`:

```sh
python3 -m py_compile spikes/043-ares-cpu-sd-sp-sink-gpt56sol/run.py spikes/043-ares-cpu-sd-sp-sink-gpt56sol/crosscheck.py
python3 spikes/043-ares-cpu-sd-sp-sink-gpt56sol/crosscheck.py
python3 spikes/043-ares-cpu-sd-sp-sink-gpt56sol/run.py
```

Generated binaries/results stay under ignored `target/ares-cpu-sd-sp-sink-gpt56sol/`.
