# ERL / ErrorEPC ERET hardware contract

This bounded experiment resolves the semantic disagreement left open by
`research/eret-target-provenance-gpt56sol`.

It combines three independent evidence classes:

1. NEC VR4300 User's Manual `U10504EJ7V0UM00`: the ERET instruction description
   specifies that ERL=1 selects ErrorEPC and clears ERL; section 6.3.12 describes
   ErrorEPC as read/write. The VR4300 CP0 hazard table also lists ERET as consuming
   `EPC or ErrorEPC`.
2. Exact pinned source comparison: ares and Gopher64 implement that selector;
   pinned Mupen pure interpreter instead logs `error in ERET` and stops. The
   disagreement is preserved as a reference limitation, not averaged away.
3. Exact pinned `n64-systemtest` contains `ErrorEPCNoMasking`, which writes several
   64-bit values and expects exact readback. This independently supports guest
   programmability of ErrorEPC.

`driver.cpp` executes real pinned-ares guest DMTC0, hazard NOPs and ERET through
`CPU::instruction()`, then executes a marker at the selected return target.
`model.py` attacks capture-only/value-only closure policies with same-value writes,
unknown restore state, and guest overwrites of NMI-captured ErrorEPC.

Reproduce after checking out the four pins in `refs.lock.toml`:

```bash
python3 -m py_compile experiments/eret-errorepc-hardware/{model.py,run.py,source_guard.py}
python3 experiments/eret-errorepc-hardware/model.py
python3 experiments/eret-errorepc-hardware/source_guard.py \
  --ares .refs/ares --gopher64 .refs/gopher64 \
  --mupen .refs/mupen64plus-core --systemtest .refs/n64-systemtest \
  --out target/eret-errorepc-hardware/source_guard.json
python3 experiments/eret-errorepc-hardware/run.py
```

No reference source is modified. The ares build is the existing separate research
oracle path and both recompilers remain disabled.
