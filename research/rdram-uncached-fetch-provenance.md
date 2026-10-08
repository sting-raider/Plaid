# ares direct uncached instruction-fetch provenance from ordinary RDRAM reads

Date: 2026-10-08

Result: **VALIDATED for the bounded tested scope**

Integration recommendation: **ADOPT** the event/join contract below as a narrow provenance primitive. Do not generalize it to cached fetches, translated/degraded RDRAM, EBUS, or other memory sources without source-specific backing evidence.

## Question

Can a direct uncached VR4300 instruction fetch from identity-mapped RDRAM be tied to the exact ordinary successful `RDRAM::Writable::read<Word>` transaction that supplied it, rather than inferred from physical address, value equality, or current RAM contents?

The falsifiable hypothesis was that, in pinned ares with CPU/RSP recompilers disabled, an explicit fetch boundary plus one capture-wide monotonic ordinal is enough to join the synchronous path

```text
CPU::fetch(noncache)
  -> CPU::busRead<Word>
  -> Bus::read<Word>
  -> MI::readRdram<Word>
  -> RDRAM::Writable::read<Word>
  -> Memory::Writable::read<Word>
```

provided the ordinary RDRAM event is emitted only after a successful in-range identity-mapped backing read, and the join uses the post-endian bus address and returned value. The experiment tried to falsify this with equal-valued data reads, cached fetches, reverse-endian lane selection, successful translated RDRAM, degraded translated RDRAM, out-of-range identity reads, missing mappings, and EBUS test mode.

## Recovered prior work

This lane intentionally recovered the completed scalar-RDRAM observer from `research/cpu-copy-rdram-gpt56sol` / `spikes/020-ares-cpu-copy-transactions` rather than creating a competing transaction sensor. That work had already executed a callback immediately after successful identity-mapped scalar backing reads and shown that ordinary KSEG1 CPU loads/stores can expose real backing transactions.

The new uncertainty was narrower: whether one such transaction can be identified as the transaction for a particular *instruction fetch* when ordinary data reads use the same uncached requestor and can return the same value.

## Exact reference and source path

Pinned ares revision:

```text
9408cb43d4948fc3ea6e152a307a34348df3fe04
```

Relevant behavior at that revision:

- `ares/n64/cpu/memory.cpp::CPU::fetch` starts from `access.paddr`, applies `reverseEndianPaddr<Word>` when the CPU context is little-endian, sends cached fetches to `icache.fetch`, and sends uncached fetches to `busRead<Word>`.
- `ares/n64/memory/bus.hpp::Bus::read` routes the RDRAM physical range to `MI::readRdram`.
- `ares/n64/mi/bus.hpp::MI::readRdram` normally routes ordinary RDRAM addresses to `rdram.ram.read`, but VR4300 uncached traffic in EBUS test mode instead routes to `rdram.ram.ebusRead`.
- `ares/n64/rdram/rdram.hpp::RDRAM::Writable::read` has materially different paths:
  - non-identity mapping translates to a backing chip, reads that backing address, then can degrade bits according to CCI;
  - identity mapping rejects addresses at/after RAM size before reading backing memory;
  - only the successful identity path reaches `Memory::Writable::read<Size>(address)` directly;
  - `ebusRead` reads hidden-RAM nibbles, not ordinary RDRAM backing bytes.

That distinction is why this result is intentionally an **identity ordinary-read** witness, not a generic "RDRAM-looking address" witness.

## Instrumentation and join rule

`spikes/025-ares-rdram-uncached-fetch/run.py` generates instrumented copies of the pinned ares headers/TUs while requiring the pinned checkout itself to remain exact and clean.

Two research callbacks share one host-side monotonic ordinal:

1. **Scalar RDRAM event**: inserted after the actual successful identity `Memory::Writable::read<Size>` and before returning its value. It records ordinal, CPU PC, direction, backing address, width, requestor and returned value.
2. **CPU fetch boundary**: brackets the actual cache/bus access inside `CPU::fetch` after address validation and endian-lane adjustment. It records ordinal, vaddr, raw translated paddr, post-endian bus paddr, cache flag and final fetched word.

For this bounded experiment, a fetch receives an ordinary-RDRAM origin witness only if all of the following hold:

- the fetch is uncached;
- exactly one scalar read event lies strictly between that fetch's begin/end events;
- the scalar event is a 4-byte read;
- requestor is `VR4300_UNCACHED`;
- scalar backing address equals the fetch's **post-endian bus paddr**;
- scalar returned value equals the fetch result.

Zero matches or multiple matches fail closed. A matching read before or after the fetch boundary is not eligible even when its address/value happen to match.

## Adversarial fixture

All instructions/data are synthetic; no ROM or firmware asset is needed. The CPU and RSP recompilers are disabled.

1. **Equal-value data-read decoy**: KSEG1 fetches `LW t0,0(s0)` and then a zero/NOP. The `LW` itself reads zero from a separate KSEG1 data address immediately before the zero-valued second instruction fetch.
2. **Cached KSEG0 fetch**: executes a known `ORI`; must not receive an ordinary scalar-read witness.
3. **Reverse-endian direct fetch**: raw translated paddr `0x7000` must actually fetch word lane `0x7004` and execute the `ORI` stored there.
4. **Successful non-identity translation**: bus paddr zero maps to chip-one backing `0x200000`, returns a known `ORI`, but remains outside the identity witness policy.
5. **Identity out-of-range**: paddr equals 8 MiB RAM size, returns zero/NOP without a backing read.
6. **Non-identity missing mapping**: returns zero/NOP and raises the RI error acknowledgement, without a backing read.
7. **Successful translated + degraded**: backing contains the known `ORI`, but CCI is set to `ccLow`, so the returned instruction degrades to zero/NOP. It must not be mistaken for identity backing provenance.
8. **MI EBUS test mode**: enabled through the public MI mode-register write path; uncached fetch reads a deterministic zero/NOP from hidden RAM via `ebusRead`, bypassing `RDRAM::Writable::read`.

## Observed evidence

Final successful GitHub Actions run:

```text
run:        37801666243
source:     08fc4f5a0f563e2501751d93e67ed9d9f6809a7b
result SHA: 9580733c7af1b3ced1f5c38594e2e6fd123f79ba85b900d8d2205dcb5dd9c684
```

The job checked out the exact pinned ares revision, syntax-checked the runner, built an unmodified-reference baseline plus the generated instrumented core, executed the matrix, repeated the traced execution byte-for-byte, and hashed `target/ares-rdram-uncached-fetch-spike/results.json`.

### Direct fetch and equal-value decoy

The only Phase-1 scalar events were:

```text
ordinal 2: paddr 0x6000, value 0x8e080000  (first instruction backing read)
ordinal 4: paddr 0x1000, value 0x00000000  (ordinary LW data read decoy)
ordinal 6: paddr 0x6004, value 0x00000000  (second instruction backing read)
```

Both direct instruction fetches received unique witnesses: ordinal 2 for `0x6000`, ordinal 6 for `0x6004`. The runner additionally asserts that the zero-valued data-read decoy at ordinal 4 occurs before the second fetch's begin event. Therefore `VR4300_UNCACHED + equal value` is not sufficient evidence; the fetch boundary/ordinal is doing real disambiguation work.

### Reverse-endian fetch

Phase 3 observed:

```text
raw translated paddr: 0x7000
post-endian bus paddr: 0x7004
fetched value:          0x340a5678
scalar witness ordinal: 11 at backing address 0x7004
```

The instruction executed and set `t2 = 0x5678`. Joining on raw translated paddr `0x7000` would therefore be wrong for this context; the witness must key the actual post-endian bus address.

### Fail-closed cases

The remaining fetch pairs behaved as follows:

- Phase 2 cached fetch: fetched `0x340b1357`, **no scalar event**, no witness.
- Phase 4 successful translated RDRAM: fetched `0x34091234`, **no eligible scalar event**, no witness.
- Phase 5 identity OOB: fetched zero, **no scalar event**, no witness.
- Phase 6 missing translated mapping: fetched zero, **no scalar event**, no witness.
- Phase 7 successful translated/degraded read: fetched zero, **no scalar event**, no witness.
- Phase 8 EBUS test mode: fetched zero from hidden RAM, **no scalar event**, no witness.

This is the desired asymmetry: lack of a qualifying event means "origin not proven by this primitive," not "probably current RAM."

### Neutrality and determinism

The unmodified-reference baseline, generated observer build with callbacks disabled, and generated observer build with callbacks enabled produced identical recorded emulated facts/state. The traced run repeated byte-for-byte.

Final shared state included:

```text
exception:          0
Count:              57
I-cache hits:       0
I-cache misses:     1
RAM SHA-256:        f0eab799f096b0d9e71dcc826a663bffbd6dae2a60158ed1158c9341d9d12325
hidden RAM SHA-256: 03e8d3fab9e7119d24558ee3bf3f8b1623f6fd77b2e884cf424cf5aaa7e8dbb8
I-cache SHA-256:    931a18fc8cd64151718c4015af2a47f03d12bd94e0b0f00f2050f72d817dac9a
```

There was also an earlier successful six-case run (`37800297658`, source `4ff87667a56fbacd2f35590f279014fec7fed7bb`, result SHA `1c8e4f44eac58a575cd7aa412f16398c1ee34097974162148ea23f6d2851c4ef`). Two intermediate extension runs failed at compile time because the first EBUS fixture attempted to access private `MI::io`; the fixture was corrected to use the public `MI::writeWord` mode-register path (set bit 10, clear bit 9) before the final green run. Those failures did not produce semantic evidence and are not counted as passing results.

## Reproduce

From a checkout where `.refs/ares` is exactly the pinned revision:

```sh
python3 -m py_compile spikes/025-ares-rdram-uncached-fetch/run.py
python3 spikes/025-ares-rdram-uncached-fetch/run.py
sha256sum target/ares-rdram-uncached-fetch-spike/results.json
```

Expected final result hash for the recorded environment/run:

```text
9580733c7af1b3ced1f5c38594e2e6fd123f79ba85b900d8d2205dcb5dd9c684
```

## What is safe to adopt

1. **Instrument the completed backing operation, not an address-shaped proxy.** An ordinary identity RDRAM read event belongs after the successful `Memory::Writable::read`, with OOB/failure paths excluded.
2. **Give instruction fetches explicit causal context.** A fetch attempt/context ID or equivalent begin/end ordinal must delimit which backing transactions are eligible.
3. **Record the actual post-endian bus paddr.** Raw translated paddr is insufficient under reverse-endian contexts.
4. **Require an unambiguous transaction match.** For the word-fetch primitive: uncached fetch, exactly one matching 4-byte `VR4300_UNCACHED` scalar read inside the context, matching bus address and value. Otherwise fail closed.
5. **Do not infer origin from equality.** The Phase-1 zero-valued data read is a concrete counterexample to treating requestor/address-adjacent/value equality as causal provenance.
6. **Keep source classes separate.** Cached I-cache residency/fills, non-identity RDRAM translation/degradation, EBUS hidden RAM, SP/PIF/ROM and other sources need their own verified source-specific provenance events before they can produce byte-origin witnesses.

## Remaining gaps

This is deliberately not a general executable-origin proof.

- Execution used the ares interpreter path with both CPU/RSP recompilers disabled. That is appropriate for compiler-time oracle instrumentation, but no claim is made about ares recompiler instrumentation.
- Direct KSEG1 identity-RDRAM word fetches and one forced reverse-endian context were tested. TLB-mapped uncached fetches were not exercised.
- Non-identity translated/degraded RDRAM was only shown to fail closed; its actual backing/degradation lineage is still unresolved here.
- EBUS hidden-RAM reads were only shown to fail closed; this spike does not provide hidden-RAM origin provenance.
- RDRAM register-space fetches, reset/savestate epoch semantics, nested/reentrant capture behavior and long-run ordinal rollover/cost were not tested.
- This primitive says where an **observed** uncached instruction word came from. It does not prove exhaustive reachability, indirect-target closure, overlay lifetime, mutation history, or closed-world completeness.
- Cached instruction provenance still depends on the separate I-cache fill/residency/invalidation/writeback work; this result must not bypass that model.

Within those boundaries, the hypothesis is **VALIDATED**: an explicit fetch context joined to the exact successful ordinary identity-RDRAM backing read is strong enough to create a byte-origin witness for the tested direct uncached word fetches, and the constructed counterexamples do not fabricate witnesses.
