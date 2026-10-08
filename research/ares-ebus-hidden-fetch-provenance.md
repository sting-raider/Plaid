# ares MI EBUS-test hidden-RAM instruction-fetch provenance

Date: 2026-10-08

Result: **PARTIAL**

Integration recommendation: **PRIMARY-INTEGRATOR-REVIEW**. Preserve this source as a derived/transformed provenance class, or keep it unknown. Do not coerce it into ordinary four-byte `ByteOrigin` copy provenance.

## Question

Can an uncached VR4300 instruction fetch routed through MI EBUS-test mode in pinned ares be tied to concrete hidden-RAM backing state strongly enough to identify the fetched instruction's origin?

The falsifiable hypothesis was that a fetch-scoped completed hidden-memory read would expose the exact backing bytes that supplied the word. That hypothesis is only partly correct. The routing is source-specific and the transform is deterministic, but the result is **not** a four-byte copy from hidden memory: a Word read is synthesized from four bits spread across two hidden-storage bytes.

## Exact reference and recovered evidence

Pinned ares revision:

```text
9408cb43d4948fc3ea6e152a307a34348df3fe04
```

This lane recovered, rather than duplicated, the full-reference execution fixture from `research/rdram-uncached-fetch-provenance.md` / `spikes/025-ares-rdram-uncached-fetch/`. Its Phase 8 already executes one real interpreter instruction fetch after enabling MI EBUS-test mode through the public MI mode register. Ordinary RDRAM at the same request address holds an ORI, hidden state is forced to zero, and the CPU instead fetches/executes a zero/NOP through the EBUS route. That exact-pin run (`37801666243`) proved the CPU path can reach EBUS state and, critically, that the existing ordinary-RDRAM transaction witness correctly stays silent. It did **not** expose hidden backing provenance.

The new spike is `spikes/034-ares-ebus-hidden-fetch/` on branch `research/ebus-hidden-fetch-gpt56sol`.

## Pinned-source route

At the exact pin:

1. `ares/n64/cpu/memory.cpp::CPU::fetch` sends an uncached fetch to `busRead<Word>(paddr)` after any reverse-endian lane adjustment. Cached fetches instead call `icache.fetch`.
2. `ares/n64/mi/bus.hpp::MI::readRdram` diverts scalar traffic to `rdram.ram.ebusRead<Size>(address)` only when `io.ebusTestMode` is true **and** the requester is `VR4300_UNCACHED`. Ordinary RDRAM otherwise uses `rdram.ram.read`.
3. Cached burst RDRAM access while EBUS mode is active does not use the hidden scalar path; `MI::readRdramBurst` calls `ebusFreeze()`.
4. `ares/n64/rdram/rdram.hpp::RDRAM::Writable::ebusRead<Word>` resolves the request to `mapped`, then computes `self.hidden.nibble(mapped & ~3)`.
5. `ares/n64/rdram/hidden.hpp::HiddenRAM::nibble` addresses hidden storage at `data[address >> 1]` and returns:

```text
((raw0 & 3) << 2) | (raw1 & 3)
```

For a Word EBUS read, that 4-bit integer is returned as the 32-bit fetched value. There are no four contiguous hidden bytes equal to the four instruction bytes.

The exact CI payload recorded these source SHA-256 values:

```text
ares/n64/cpu/memory.cpp   55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74
ares/n64/mi/bus.hpp       f59d20c5d7d8d0ef53032af320f1c96b9343971bb513668b749ca6cda8c4d372
ares/n64/rdram/rdram.hpp  6a77c2fa0bbb320ff6b2855ea6379541a67096bed6b91cc6cd2697584112b1cf
ares/n64/rdram/hidden.hpp 5bdf8ccf0568dfc353334486aefa5ad222a585f9fd337dae2dc03d2f5bc84023
```

## Executed experiment

`probe.cpp` includes the **actual pinned** `ares/n64/rdram/hidden.hpp` against minimal project-owned type/memory stubs. `run.py` first checks the exact ares commit and clean tree, source-guards the CPU/MI/RDRAM/HiddenRAM route above, builds the probe, executes it twice byte-identically, then runs a fail-closed provenance reducer.

Exact GitHub Actions run:

```text
run:                    37850895769
head:                   36171b2b6f0ba00452efcf0d12e1d22d30bd10dd
result artifact:         11582295181 (ebus-hidden-fetch-results)
artifact zip digest:     sha256:aa0e1bcc248b523b08f90877627988997684e56f41bb03f174e4860d33fbb6e9
results.json SHA-256:    a2af65975b92181b649d6490f5f405652e7e7fe8c754e75406b6f50972dc6479
probe.cpp SHA-256:      e54123460de91e96d743cceb7dd9eccf2f9ff5664396bf6a30331e06a934b056
```

The job checked out exact pinned ares, syntax-checked the runner, compiled and executed the exact-header transform matrix, reran it deterministically, hashed the result and retained `results.json` as an Actions artifact.

### Exhaustive hidden-byte matrix

The experiment enumerated all 65,536 possible pairs `(raw0, raw1)` for the two hidden-storage bytes consumed by one `HiddenRAM::nibble` operation.

Observed:

```text
input byte pairs:          65,536
possible returned values:  16
pairs per returned value:  4,096
source storage bytes:      2
relevant bits per byte:    2
returned-value entropy:    4 bits
```

Every pair matched `((raw0 & 3) << 2) | (raw1 & 3)`.

This disproves the tempting model `fetch word <- four hidden bytes`. The precise pinned-ares statement is instead:

```text
fetch Word value
  <- deterministic transform
  <- low two bits of hidden[offset + 0]
     plus low two bits of hidden[offset + 1]
```

where `offset = mapped_paddr >> 1` after `ebusRead` aligns the Word request with `mapped & ~3`.

### Mutation transform checks

The same exact header was executed through both hidden-state update mechanisms relevant to Word writes:

- ordinary `HiddenRAM::update<Word>` can produce only EBUS Word results `{0, 3, 12, 15}` because it records two source bits from the ordinary RDRAM Word payload (bits 16 and 0) into the hidden representation;
- `HiddenRAM::ebusScatter<Word>` can produce all 16 possible EBUS Word results.

Therefore executable EBUS state has a mutation lineage distinct from current ordinary RDRAM payload bytes. A provenance implementation that snapshots only RDRAM contents is unsound for this source class.

### Fail-closed reducer

The spike models the event Plaid would need from a completed hidden read. A fetch receives a `derived_hidden_bits` witness only when:

- the fetch is uncached;
- EBUS routing is active for that fetch;
- exactly one hidden-read event occurs inside the explicit fetch begin/end interval;
- it is a Word event;
- request physical address matches the fetch's actual bus paddr;
- delivered value matches the fetch result;
- delivered value rechecks against the captured raw hidden bytes and transform.

The witness records request paddr, mapped paddr, the two hidden storage offsets, masks `{0x3,0x3}`, the transform expression and delivered value. It does **not** claim byte-copy provenance.

One positive case and seven adversarial cases ran. The reducer rejected cached/EBUS-off routing, wrong request address, mismatched delivered value, malformed raw hidden inputs, an event outside the fetch interval and an ambiguous interval containing two hidden reads. An equal-valued decoy outside the causal interval cannot steal the witness.

## Important counterexample: hidden backing is external to ordinary RDRAM serialization

Pinned ares does not own `HiddenRAM::data` as part of `RDRAM::Writable`. `ares/n64/vulkan/vulkan.cpp` sets it to paraLLEl-RDP's `begin_read_hidden_rdram()` storage when that backend is active, and sets it to `nullptr` when Vulkan/RDP support is unavailable. `RDRAM::serialize` serializes ordinary `ram`, mapping state and chip state but contains no explicit `HiddenRAM` serialization.

The prior headless Phase-8 fixture intentionally supplied a synthetic hidden buffer so the path could be exercised deterministically. Consequently, the new result does **not** establish real-backend save/load/reset lifetime identity for hidden state. Any production witness must bind hidden backing to an explicit capture epoch/source identity; it may not assume ordinary RDRAM serialization proves hidden-state continuity.

## Independent-oracle check

Pinned Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7` and pinned Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0` both expose the MI EBUS mode bit in their inspected MI controller code. In the searched pinned sources, neither provides an independently matching hidden-RAM fetch transform. Pinned `n64-systemtest` has no `ebus` test in the searched tree.

Therefore this result is a **pinned-ares oracle contract**, not a proved N64 hardware invariant.

## What is safe to adopt

1. **Keep EBUS hidden state as a separate source class.** Ordinary RDRAM address/value equality cannot establish EBUS instruction origin.
2. **Represent derivation, not fake bytes.** For the tested Word path, the source is two hidden storage bytes plus bit masks and the explicit transform. If Plaid's evidence model cannot represent transformed origins yet, leave the source unknown and closure OPEN.
3. **Join only inside an explicit fetch context.** Requester/address/value coincidence is insufficient; require the completed source operation within the fetch boundary and reject ambiguity.
4. **Use the actual mapped hidden address.** Nonidentity RDRAM mapping can alter `mapped`; request paddr alone is not the backing identity.
5. **Track hidden-state mutation/lifetime separately.** Ordinary writes update hidden state through `update`, EBUS writes through `ebusScatter`, and backend/reset/save/load boundaries require their own epoch semantics.
6. **Do not generalize ares into hardware truth.** Independent hardware/reference confirmation is still missing.

## Remaining gaps

- The new spike executes the exact pinned `HiddenRAM` implementation and source-guards the full CPU-to-EBUS route, but does not add a hidden-read callback to a full ares build. The earlier exact full-reference fixture proves the CPU reaches EBUS mode but only by supplying a deterministic synthetic hidden buffer.
- Real paraLLEl-RDP hidden backing ownership, mutation chronology, reset/power behavior and save/load identity were not instrumented.
- Nonidentity/translating EBUS fetches were source-inspected but not executed end-to-end here.
- Reverse-endian EBUS instruction fetch was not executed.
- Byte/Half/Dual EBUS operations were not exhaustively characterized; the executable Word path is the bounded result.
- No independent implementation or hardware system test corroborates ares's exact hidden transform.
- This says where one **observed** EBUS Word value can derive from in pinned ares. It does not prove reachability, indirect-target closure, executable lifetimes or closed-world completeness.

## Verdict

**PARTIAL.** The original byte-origin hypothesis is rejected as stated: a pinned-ares EBUS Word instruction is not copied from four hidden backing bytes. The narrower transformation-provenance claim is validated by exact pinned source plus an exhaustive execution of the exact `HiddenRAM` implementation. Plaid should either model this as `derived_hidden_bits`-style provenance with explicit hidden-state lifetime/epoch evidence or keep the origin unresolved. Promoting it to normal `ByteOrigin` would manufacture provenance that does not exist.

## Primary integration reproduction (2026-10-09)

Retained original fixture from `fe15ab6` without the worker workflow. Local WSL
reproduction exhausts all 65,536 hidden-byte pairs and passes seven negative
reducer cases. Canonical-LF source hashing reproduces result SHA-256
`a2af65975b92181b649d6490f5f405652e7e7fe8c754e75406b6f50972dc6479`.
The runner now dispatches through WSL on Windows and checks the pinned checkout
with the repository's line-ending policy. This remains a compiled exact-header
probe plus source guards and a synthetic reducer, not an actual CPU hidden-read
observer. Preserve the PARTIAL verdict and derived-bits/unknown boundary.
