# Cache-error executable-root obligation experiment

This experiment tests a deliberately narrow whole-ROM certificate question: may a Nintendo 64 / NEC VR4300 scope exclude a cache-error executable root, or must emulator silence leave that root unresolved?

The experiment has two parts:

1. `run.py` builds and executes the exact Plaid-pinned ares revision with the interpreter path. Guest code writes all ones to COP0 register 27 (`CacheErr`) using `MTC0`, waits through CP0 hazards, reads it back with `MFC0`, and checks that neither BEV setting enters an exception root. The runner also guards exact pinned ares, n64-systemtest and Gopher64 source facts.
2. `model.py` is an adversarial certificate reducer. It permits exclusion only when evidence is explicitly scoped to the NEC VR4300 hardware rule that the cache-error exception does not occur. Removing that hardware evidence, or changing the target to generic MIPS III, leaves the obligation unresolved.

The hardware rule comes from NEC VR4300 User's Manual `U10504EJ7V0UM00`, Appendix B.1.7 / Table B-1: VR4300 has no cache parity and its cache-error exception does not occur. This is target-hardware evidence, not an inference from emulator behavior.

## Reproduce

With `.refs/ares`, `.refs/n64-systemtest`, and `.refs/gopher64` checked out at the revisions in `refs.lock.toml`:

```sh
python3 -m py_compile experiments/cache-error-root-obligation/run.py experiments/cache-error-root-obligation/model.py
python3 experiments/cache-error-root-obligation/model.py
python3 experiments/cache-error-root-obligation/run.py
sha256sum target/cache-error-root-obligation/results.json
```

`run.py` does not patch the pinned ares sources. It reuses `spikes/003-ares-oracle/run.py` only as the existing headless exact-pin build helper.

## Fail-closed rule

`no cache-error transition observed in emulator` is insufficient evidence by itself. The accepted exclusion is `target == NEC VR4300` plus the explicit hardware property that this exception class cannot occur. A future target CPU or a broader generic-MIPS scope must reopen the root obligation.
