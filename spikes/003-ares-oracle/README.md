# Pinned ares CPU oracle spike

Hypothesis: the pinned core can run a bounded headless interpreter harness for
cartridge fetch, LLD/SCD and address-error delay-slot state, filling demonstrated
gaps in the Mupen pin without changing CPU instruction semantics.

Pin: `9408cb43d4948fc3ea6e152a307a34348df3fe04`. The reference license includes
ISC core, BSD SLJIT and the upstream notices. Build separately under ignored
target/; no reference implementation is copied into Rust or a native artifact.

Cases: original cartridge integer/control fixture, LLD/SCD RAM fixture,
unaligned LW, and unaligned LW in a taken branch's delay slot. Guest state and
identity-mapped initialized RAM are supplied explicitly; boot and rendering are
outside this harness. Core interpreter option disables CPU/RSP recompilation.

Reproduce with the pinned ares and prepared Mupen checkouts:

```text
python spikes/003-ares-oracle/run.py
```

Linux needs GCC/G++ with C++20 and NASM for the separate Mupen comparison.
Windows launches WSL Ubuntu. Outputs, notices, build manifests and states are
under ignored `target/ares-oracle-spike/`. No firmware is executed or supplied.

## Verdict: VALIDATED

### Evidence

- Four original capability fixtures pass full GPR/HI/LO checks and explicit
  PC/memory/exception assertions; every result is byte-identical on repetition.
- Cartridge code at B0001000 executes JALR and its delay slot, returns, and
  preserves link/target values. This is fetched through the reference bus.
- LLD/DADDIU/SCD changes `123456789abcdef0` to `123456789abcdef1`, returns success
  in r4 and sets LLAddr to physical address >> 4 (`0x200`).
- Unaligned LW raises AdEL=4 with the expected BadVAddr, EPC and boot exception
  vector. The taken branch delay-slot variant sets BD=1 and EPC to the branch.
- All eight existing integer/control fixtures match the pinned Mupen pure,
  untraced/traced dynarec and repeat in every GPR, HI/LO and PC. They cover ordinary
  and custom JALR links, pagespan JR/JALR/direct branches, likely annulment and
  register pressure. ares CPU/RSP recompiler flags are asserted disabled.

### Constraints and surprises

- Guest registers, initialized identity-mapped RAM and initial PC are explicitly
  supplied. The shared SP bootstrap's final r25/r10 values are supplied for the
  eight comparisons. Boot, interrupt/event equivalence, rendering, FPU, TLB and
  RSP execution are outside this acceptance scope. No whole homebrew suite runs.
- The non-Vulkan build needs an exact generated guard around one renderer load
  call in System::run, and omits UI resource assets. CPU/RSP/memory instruction
  sources remain unchanged. The harness supplies hidden-RAM backing normally
  owned by the Vulkan renderer; otherwise CPU RAM writes dereference null.
- ROM writes intentionally do nothing; fixture bytes must populate the frontend
  pak before cartridge connection. Explicit zeroed registers remove the core's
  initial stack value from the comparison state.
- The ISC core and BSD SLJIT compile separately with upstream LICENSE preserved.
  SLJIT is linked by the core's build structure but guest recompilation is disabled.
  This research executable is an emulator oracle, not a Plaid native artifact.

### Recommendation

Use this bounded oracle for semantic checks and extend coverage deliberately.
Add a separate raw instruction-fetch observer and cartridge source model before
attempting broader discovery. Keep the existing whole-ROM gate OPEN; these finite
state comparisons establish neither executable closure nor general CPU accuracy.
