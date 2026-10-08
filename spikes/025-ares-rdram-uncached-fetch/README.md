# Ordinary uncached RDRAM instruction-fetch witness

## Verdict: PARTIAL

Hypothesis: in pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, an uncached VR4300 instruction fetch from successful identity-mapped RDRAM can be joined to the exact ordinary single-word backing read if, and only if, the backing observer is scoped by an explicit instruction-fetch context. Address/value/requestor matching alone is not sufficient.

The exact pinned source supports the candidate synchronous chain:

`CPU::fetch` -> `busRead<Word>` -> `Bus::read<Word>` -> `MI::readRdram<Word>` -> `RDRAM::Writable::read<Word>` -> return to `CPU::fetch`.

`CPU::fetch` sends uncached instructions through `busRead<Word>`, but `CPU::read` sends uncached data loads through the same helper. Both therefore reach RDRAM as `RBusDevice::VR4300_UNCACHED`. This disproves the tempting inference that requestor + physical address + returned word identifies an instruction backing read.

`MI::readRdram` also diverts uncached accesses to `ebusRead` while EBus test mode is active. `RDRAM::Writable::read` handles remapped/degraded accesses before its identity path and returns zero for identity out-of-bounds accesses. A sound identity-only executable-byte witness must therefore be emitted after the successful `Memory::Writable::read<Size>(address)` in the identity branch, not at bus intent or from the requestor enum.

## Proposed bounded witness contract

For an uncached `CPU::fetch`, allocate a monotonically unique fetch-context ID after devirtualization/endian address adjustment and immediately before `busRead<Word>`. While that context is active, a successful identity-mapped, in-bounds `RDRAM::Writable::read<Word>` with `VR4300_UNCACHED` may emit one candidate `{context_id, physical, word}`. When `busRead<Word>` returns, certify only if exactly one candidate exists and its context ID, physical address and word equal the fetch result. Clear the context on every completion. Cached fetches do not enter this contract.

Fail closed on no read, multiple reads, address/value mismatch, remapped/degraded paths, EBus mode, out-of-bounds access, or any context mismatch. A later existing fetch observation may carry the certified witness forward, but must not reconstruct it by searching earlier equal-value RAM events.

## Deterministic adversarial model

Run:

```sh
python3 -m py_compile spikes/025-ares-rdram-uncached-fetch/source_contract.py \
  spikes/025-ares-rdram-uncached-fetch/source_guard.py
python3 spikes/025-ares-rdram-uncached-fetch/source_contract.py
```

The model passes 11 cases:

- exact identity uncached fetch;
- equal-value ordinary data-read decoy rejection;
- cached-fetch rejection;
- remapped-path rejection;
- EBus-path rejection;
- identity out-of-bounds rejection;
- wrong-address equal-value rejection;
- returned-word mismatch rejection;
- multiple-read ambiguity rejection;
- stale-candidate non-reuse;
- post-endian-adjustment physical-address binding.

Tested twice with byte-identical output. Payload SHA-256: `5f4b13c41013445fa54598bbd3583a35608f09a15a837d1366e09fff70ed894f`. Captured pretty-JSON output SHA-256: `fc7550528df86db8caaee0421b31eb83f6f678f2145e0e498b9087a4ea0de299`. Tested `source_contract.py` SHA-256: `333a03d35b0d32f6eca7fc57f244bc86bf1a18af62a8051d67054acc6454a131`. `source_guard.py` SHA-256: `bafe9add5c8f6282ce35f66080aa3b81050514b03da76f37ceefe2362088bdef`.

When a pinned ares checkout is available, also run:

```sh
python3 spikes/025-ares-rdram-uncached-fetch/source_guard.py .refs/ares
```

## Missing reference execution

This worker sandbox could not resolve `github.com`, so it could not clone/build the pinned ares checkout. The source guard is syntax-checked but was not executed against a local checkout here. The adversarial model validates the *join contract*, not instrumentation neutrality or actual ares callback chronology.

A follow-up reference run should extend the existing spike-005 physical-fetch fixture or spike-015 cache-outcome fixture with a research-only context around the uncached `busRead<Word>` and a post-success identity ordinary-read callback. It must compare baseline vs instrumented plain/traced/repeated complete state and demonstrate that the final spike-015 uncached fetch at physical `0x4000` obtains its backing witness while cached fetches and injected same-value data reads do not.

Do not integrate this as a general RDRAM provenance claim. It covers only ordinary uncached CPU instruction fetches on the successful identity-mapped RDRAM path. Cached fills, remapped/degraded RDRAM, CPU copies/stores, SP/PIF and reset/restore lifetimes remain separate obligations.
