# Spike 025: ordinary RDRAM reads for uncached CPU fetches

## Question

Can a direct uncached VR4300 instruction fetch from identity-mapped RDRAM be joined to the exact ordinary successful `RDRAM::Writable::read<Word>` transaction without confusing it with an ordinary CPU data read or with unsupported RAM paths?

The spike recovers the scalar RDRAM observer already executed by `spikes/020-ares-cpu-copy-transactions` and adds a research-only boundary around pinned ares `CPU::fetch`. Both callbacks share one host-side monotonic ordinal. The verifier accepts a fetch-origin witness only when exactly one successful identity scalar read occurs strictly between that fetch's begin/end events and matches the post-endian bus address, word width, uncached requestor and returned value.

## Adversarial matrix

1. KSEG1 `LW` followed by NOP: the data read and second instruction both return zero. The data-read decoy lies outside the second fetch boundary.
2. KSEG0 cached fetch: no ordinary scalar instruction-read witness is allowed.
3. Reverse-endian direct fetch: translated paddr `0x7000` actually reads word lane `0x7004`; the witness must use the post-endian bus address.
4. Successful non-identity RDRAM translation: executes a known `ORI`, but the identity-only scalar observer must remain silent.
5. Identity-mapped out-of-range RDRAM fetch: returns zero/NOP with no backing witness.
6. Non-identity missing mapping: returns zero/NOP with no backing witness.
7. Successful non-identity translated read with CCI at `ccLow`: the backing instruction is degraded to zero/NOP and remains outside the identity witness policy.
8. MI EBUS test mode: uncached CPU traffic bypasses `RDRAM::Writable::read`; a deterministic hidden-RAM zero/NOP must therefore produce no ordinary-RDRAM witness.

The baseline, instrumented-observer-disabled and instrumented-observer-enabled runs must end with identical emulated facts/state; traced execution is repeated byte-for-byte.

## Reproduce

```bash
# .refs/ares must be exactly 9408cb43d4948fc3ea6e152a307a34348df3fe04
python3 -m py_compile spikes/025-ares-rdram-uncached-fetch/run.py
python3 spikes/025-ares-rdram-uncached-fetch/run.py
sha256sum target/ares-rdram-uncached-fetch-spike/results.json
```

No ROM or firmware asset is required; the fixture writes synthetic instructions directly into the emulated RAM component.
