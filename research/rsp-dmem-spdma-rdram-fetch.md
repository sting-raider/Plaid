# RSP DMEM -> reverse SP DMA -> RDRAM -> CPU fetch provenance

Status: **VALIDATED** for the bounded exact-pin interpreter fixture described here.

Date: 2026-10-09

Canonical Plaid base at claim time: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Research branch: `research/rsp-dmem-spdma-rdram-fetch-gpt56sol`

Validated research head: `94203baaaf70b2d45974e23b67b9a3b6326ec5e5`

Pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Primary CI receipt: GitHub Actions run `37916462499`, job `113773737435`, success.
Artifact: `rsp-dmem-spdma-rdram-fetch-evidence`, artifact ID `11608784816`, artifact ZIP SHA-256 `a295353b68c17817f534325ecfa0924d61d042fa71eb7e0a55c745eb1c9adc53`.

## Question

Can actual decoded RSP DMEM mutation byte origins be carried causally through an
actual reverse SP DMA (SP DMEM -> RDRAM) into a later uncached VR4300 instruction
fetch, while preserving same-value writer generations and partial-byte origin and
cutting the older lineage when a later equal CPU write replaces the RDRAM bytes?

The test deliberately does not accept matching address/value pairs as provenance.
It requires ordered measured storage effects plus a guarded exact-pin source link
for the reverse-DMA DMEM read -> RDRAM write operation.

## Hypothesis

For this controlled interpreter scope, a later uncached RDRAM instruction fetch can
inherit an RSP-store byte origin only when ordered evidence establishes:

1. the latest completed primitive RSP DMEM sink generation for each source byte;
2. the actual reverse SP-DMA RDRAM destination effects from the current descriptor;
3. the exact later `VR4300_UNCACHED` RDRAM read bracketed by the target CPU fetch.

Equal writes must still create distinct generations. A partial store must replace
only the bytes it actually writes. A later CPU write, even of identical bytes,
must replace the SP-DMA/RSP destination lineage.

## Exact pinned implementation link

The source guard checks the exact clean ares pin before any run is accepted. In
`ares/n64/rsp/dma.cpp`, the reverse path under `dma.busy.write` reads current DMEM
words into local `dataLo` / `dataHi` and immediately writes those exact locals to
RDRAM using `RBusDevice::SP_DMA`. It also checks the current/pending descriptor
promotion source shape. `ares/n64/rsp/io.cpp` is guarded for the `SP_WRITE_LENGTH`
start path. `ares/n64/cpu/memory.cpp` is guarded for explicit
`VR4300_UNCACHED` CPU read/write requestors and the uncached fetch bus read.

Guarded exact-pin source SHA-256 values:

- `ares/n64/rsp/dma.cpp`: `b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6`
- `ares/n64/rsp/io.cpp`: `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860`
- `ares/n64/cpu/memory.cpp`: `55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74`

Pinned Mupen64Plus and Gopher64 source were also inspected as independent source
corroboration for the reverse SP-memory -> RDRAM transfer direction. That agreement
is not treated as hardware truth or as a timing oracle.

## Instrumentation

The spike composes project-owned observation boundaries that record already
computed values only:

- decoded RSP instruction begin/end contexts;
- primitive completed RSP DMEM sinks;
- ordinary identity-mapped RDRAM scalar effects with requestor identity;
- CPU fetch begin/end boundaries.

No observer performs an additional guest memory read. The reverse-DMA source read
is not separately instrumented; its causal connection to the measured `SP_DMA`
RDRAM writes is therefore exact-pin source-guarded rather than dynamically joined
by a separate source-read event.

A subordinate assumption was falsified during development: scalar RSP `SW` is not
one sink event at the existing validated observer boundary. It appears as four
primitive byte sinks. The final replay intentionally preserves that primitive
contract. Two equal `SW` instructions therefore produce eight byte sink events in
two distinct instruction contexts rather than two synthetic word events.

## Fixture

All execution uses interpreter mode with deterministic entropy.

### Phase 1: decoded RSP SW -> reverse DMA -> executable CPU fetch

RSP executes `SW r2,0(r1)` with `r2 = 0x34081234`, producing the instruction
`ORI t0,zero,0x1234` in DMEM offsets 0..3. Reverse SP DMA copies eight bytes from
DMEM offset 0 to RDRAM `0x6000`. The CPU fetches from uncached KSEG1 backing
`0x6000` and executes the word, producing `t0 = 0x1234`.

Measured relevant events:

- RSP byte sinks ordinals 2..5, context 1, offsets 0..3, values
  `34 08 12 34`;
- `SP_DMA` word writes ordinals 9 and 10 to `0x6000` / `0x6004`;
- target fetch begin ordinal 11;
- exact `VR4300_UNCACHED` RDRAM read ordinal 12, value `0x34081234`;
- target fetch end ordinal 13.

The four fetched-byte roots replay to the four measured RSP sinks.

### Phase 2: equal RSP writers remain distinct generations

DMEM already contains `0x34081234`. RSP executes the same `SW` twice with the same
payload. The first writer context is 14 with byte sinks 15..18. The second writer
context is 22 with byte sinks 23..26. Their `(offset,width,value)` signatures are
identical, but their context identities are not.

Reverse DMA writes RDRAM at ordinals 30 and 31. The target fetch read is ordinal
33. All four fetched-byte roots replay to context 22, the later equal writer.
Value equality therefore does not collapse writer generation.

### Phase 3: partial byte origin survives composition

DMEM begins as `0x34081234`. RSP executes decoded `SB r2,3(r1)` with low byte
`0x56`, producing one primitive sink at ordinal 36 / context 35 / offset 3.
Reverse DMA writes `0x34081256` to RDRAM at ordinal 40. The CPU target fetch read
at ordinal 43 returns that word and executes `ORI t0,zero,0x1256`.

Replayed fetched-byte roots are exactly:

`[initial, initial, initial, rsp_sink]`

The untouched three bytes are not falsely attributed to the RSP `SB`.

### Phase 4: later equal CPU write cuts the RSP/DMA lineage

RSP first creates `0x34081234` through byte sinks 46..49 / context 45. Reverse SP
DMA writes the target RDRAM word at ordinal 53. The CPU then fetches a separate
uncached store fixture from `0x7000` and executes decoded `SW r9,0(r10)` to the
target `0x6300`. Its successful `VR4300_UNCACHED` RDRAM write is ordinal 58 and
writes the exact same value `0x34081234`.

The later target fetch begins at 59, reads RDRAM at 60, and ends at 61. All four
fetched-byte origins replay to the CPU write at 58, not to the older SP-DMA/RSP
chain. Equal payload does not preserve obsolete provenance.

## Neutrality and determinism

The runner builds an independent uninstrumented baseline and a generated sensor
build. It executes:

1. independent baseline;
2. generated sensor binary with callbacks disabled;
3. sensor enabled;
4. sensor enabled again.

All four reported machine states are equal. Enabled repeated history/stdout is
byte-identical. Machine SHA-256:

`dc81995a87277c60dbb94fb6fc908d7e8155cfb1d8a22e4b7aa9cc0f1cc18a8e`

The enabled stdout SHA-256 is:

`03cae42dda7b37aa9f4130c7f54af7104df86af5e0245888827e674a1596fdc1`

Source artifact hashes:

- driver: `d25bf60367c13801945c06f423ad7f609097a121bed1993284a57ba5a64d5a03`
- observer: `f444ae77c86367e33f9d2f853595ae8a7bd2352ebca3e86f1e2e44fe92c162bd`
- verifier: `e0cb5f87119be9aec5e9e02c7de9ad2269db4760b2af7e8743613f2e6bd6b95d`

Generated `results.json` SHA-256:

`f443d1c594e199e15aba2f805f630659f527cad3e2824f148ae83d870f2eb5d8`

## Adversarial replay

The strict replay verifier rejects all seven tested history corruptions:

- delete the latest equal RSP byte sink;
- move an SP-DMA destination;
- forge the partial RSP sink payload;
- move the post-DMA CPU overwrite;
- forge the target fetch-read payload;
- forge the target fetch physical bus address;
- orphan an RSP sink from its instruction context.

These are replay-verifier adversaries, not a claim that every possible trace
corruption has been enumerated.

## Reproduction

From a Plaid checkout with the exact pinned ares revision available under
`.refs/ares`:

```bash
python3 spikes/043-ares-rsp-dmem-spdma-rdram-fetch/run.py
```

CI reproduction is `.github/workflows/research-rsp-dmem-spdma-rdram-fetch.yml`.
Primary successful receipt: run `37916462499` at research head `94203baa...`.

## Result

**VALIDATED**, for this bounded exact-pin ares interpreter fixture.

Within this scope, actual decoded RSP DMEM writer generations can be composed
through completed reverse SP-DMA RDRAM effects into a later uncached CPU
instruction fetch without relying on payload equality. Primitive byte lineage is
preserved across equal writes and partial writes, and a later equal CPU write
correctly terminates the older destination lineage.

The integration-level consequence is that reverse SP DMA should be modeled as a
per-byte provenance transfer from the latest known SP-memory source generation to
new RDRAM destination generations at completed storage effects. A same-value write
must still create/replace generation identity. A request-register write or matching
address/value pair is insufficient proof of the transfer.

## Limitations and explicit non-claims

This does **not** prove:

- arbitrary reverse-DMA length/count/skip, row, wrap or overlap behavior;
- reverse DMA from IMEM rather than the tested DMEM source region;
- hardware timing, bus contention or hardware-exact FIFO semantics;
- RSP recompiler behavior;
- producer identity before the explicit initial DMEM snapshot;
- cached CPU destination writes, D-cache residency or delayed writeback;
- TLB-translated CPU overwrite paths;
- save/restore, reset or power-cycle generation identity;
- exhaustive executable lifetime or mutation completeness;
- whole-ROM reachability or a closed-world certificate;
- an N64-wide invariant merely because multiple emulators agree on source shape.

The reverse-DMA source read -> destination-write causal edge is guarded against the
exact pinned ares source. If that implementation shape changes, the source guard
must fail and the evidence must be re-established rather than silently reused.
