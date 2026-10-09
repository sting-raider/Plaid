# Pinned ares maskable-interrupt root experiment

This experiment asks one bounded whole-ROM-root question left open by `research/ares-exception-vectors.md`: when does a pending maskable VR4300 interrupt actually redirect execution, and which executable root does it select?

Hypothesis: at exact pinned ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`, architectural interrupt entry occurs at the instruction boundary iff `(Cause.IP & Status.IM) != 0`, `IE=1`, `EXL=0`, and `ERL=0`. Entry selects the ordinary general vector `base + 0x180`, with BEV choosing `0xffffffff80000000` or `0xffffffffbfc00200`. A pending bit that is masked or globally suppressed is not executable-root reachability evidence.

`driver.cpp` places `ADDIU $s0,$zero,0x1234` at the interrupted uncached-RDRAM PC. Taken entry must leave `$s0` unchanged and set PC/EPC/EXL/Cause consistently with interrupt entry. Every suppressed case must execute that instruction and preserve sentinel EPC/Cause/BD state. `run.py` exercises all eight individual pending bits plus matched-multiple, masked, disjoint-mask, IE-off, EXL, ERL, no-pending and zero-mask cases under both BEV bases; every case is executed twice and must produce byte-identical JSON.

`source_guard.py` binds the experiment to the exact ares and Gopher64 pins from `refs.lock.toml` and checks their independent pending/mask/IE/EXL/ERL and `+0x180` root contracts before execution.

Reproduce after fetching the pinned refs into `.refs/ares` and `.refs/gopher64`:

```bash
python3 experiments/ares-interrupt-roots-gpt56sol/source_guard.py
python3 -m py_compile experiments/ares-interrupt-roots-gpt56sol/run.py
python3 experiments/ares-interrupt-roots-gpt56sol/run.py
```

The fixture deliberately does not claim device-specific interrupt reachability, interrupt timing equivalence, NMI/reset behavior, handler-byte provenance, or whole-ROM closure. It establishes only the bounded architectural gate/root contract needed before those broader obligations can be expressed correctly.
