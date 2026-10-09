# Translated RDRAM backing -> CPU fetch causal join

Status: **VALIDATED**

This note records a bounded pinned-ares experiment. It does not claim an N64-wide invariant or hardware validation.

## Revisions

- Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- Research branch: `research/translated-fetch-join-gpt56sol`
- Executed experiment commit: `d0551033969cc3fabb95a8b11f64de09daaaaa0c`
- Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- GitHub Actions run: `37915727306`
- GitHub Actions job: `113771358010`
- Uploaded result artifact: `11608958516` (`translated-fetch-join-results`)

## Question

Can one successful uncached VR4300 instruction fetch through ares' non-identity RDRAM mapping be causally joined to both:

1. the exact translated raw backing word, and
2. the post-CCI word actually returned to the CPU,

without mistaking equal-valued request-address backing, unrelated reads, missing mappings, or EBUS/HiddenRAM for provenance?

The additional adversarial question is whether a degraded fetch demonstrates that raw backing bytes and executable instruction identity must remain separate facts.

## Hypothesis

Within this controlled pinned-ares interpreter scope, an explicit CPU fetch begin/end interval can contain exactly one eligible completed translated scalar `Word` read. The witness is accepted only when:

- the fetch is uncached;
- the completed RDRAM read is inside that fetch interval in one monotonic event ledger;
- the read request equals the **post-endian bus paddr**, not merely the pre-endian translated paddr;
- the read was performed as `VR4300_UNCACHED`;
- the RDRAM operation is a completed four-byte translated ordinary-backing read;
- the post-CCI delivered word equals the fetch-completion value; and
- exactly one such read is eligible.

The witness must preserve mapped backing identity/raw bytes separately from the delivered word. Ambiguous or unsupported cases must fail closed.

## Upstream source path

At the exact ares pin, non-identity scalar RDRAM reads first `translate(address)`, then read `Memory::Writable` at the mapped address, then pass that raw value through `degrade(...)` before returning the delivered value.

`RDRAM::Writable::degrade` returns:

- the raw value when `cci >= ccHigh`;
- zero when `cci <= ccLow`;
- a partially degraded value between the thresholds.

The CPU fetch path separately applies reverse-endian physical-address adjustment for a `Word` before an uncached `busRead<Word>(paddr)`. Therefore a correct causal join needs the actual post-endian bus request address.

## Instrumentation

`spikes/043-ares-translated-fetch-join/` combines two previously validated research primitives in a generated exact-pin ares shadow:

- explicit CPU fetch begin/end boundaries; and
- successful translated scalar-RDRAM completion events carrying request paddr, mapped backing paddr, chip, raw word, delivered word, CCI and thresholds.

Both event classes increment one shared monotonic ordinal. No production Plaid file or canonical upstream checkout is modified.

Instrumentation neutrality is checked by running:

1. a baseline build without the new sensor;
2. the sensor build with callbacks disabled;
3. the sensor build with callbacks enabled; and
4. an identical enabled repeat.

Semantic fixture facts and terminal state must match across all four runs, and both traced runs must be byte-identical.

## Fixture

The driver executes six synthetic phases with CPU/RSP recompilers disabled and deterministic entropy enabled.

### 1. Reliable translated fetch

Request paddr `0x000000` maps to backing `0x00200000`, chip 1. Both request-address backing and mapped backing deliberately contain `0x34091234` (`ORI t1, zero, 0x1234`). This makes equal payload useless as an origin discriminator.

Expected CPU result: `t1 = 0x1234`.

### 2. Equal-valued out-of-context read

A translated data read returning the same word is performed immediately before an equal-valued instruction fetch. The global history therefore contains multiple equal-payload candidates, but only one read is temporally nested inside the fetch boundary.

### 3. Deliberately degraded executable fetch

Mapped backing contains `0x340a5678` (`ORI t2, zero, 0x5678`). Chip state is forced to `cci=8`, `ccLow=8`, `ccHigh=16`, for which pinned ares returns zero.

Expected result: raw backing `0x340a5678`, delivered fetch word `0x00000000`, CPU `t2 = 0`.

### 4. Missing translated mapping

CPU address translation succeeds but no RDRAM chip mapping exists. The fetch returns zero and there is no successful translated ordinary-backing completion event.

### 5. EBUS negative control

MI EBUS test mode fetches HiddenRAM rather than ordinary RDRAM backing. A CPU fetch boundary exists, but the translated ordinary-backing observer must not fabricate a witness.

### 6. Reverse-endian request remapping

The pre-endian translated paddr is `0`, but a little-endian `Word` fetch changes the actual bus request to `4`, which maps to backing `0x00200004` containing `0x340b1357` (`ORI t3, zero, 0x1357`).

Expected CPU result: `t3 = 0x1357`.

## Exact command

```bash
python3 spikes/043-ares-translated-fetch-join/run.py
```

The branch workflow fetches and checks out exact ares pin `9408cb43d4948fc3ea6e152a307a34348df3fe04` before running the command.

## Deterministic observations

GitHub Actions run `37915727306` completed successfully.

The trace contains exactly 17 ordered events:

- 12 CPU fetch boundary events forming six begin/end pairs;
- 5 completed translated scalar-RDRAM read events.

Observed phase witnesses:

| Phase | translated paddr | bus request | mapped backing | raw | delivered | witness |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 reliable | `0x000000` | `0x000000` | `0x200000` | `0x34091234` | `0x34091234` | accepted |
| 2 equal-value decoy | `0x000000` | `0x000000` | `0x200000` | `0x34091234` | `0x34091234` | accepted only for in-fetch event |
| 3 degraded | `0x000000` | `0x000000` | `0x200000` | `0x340a5678` | `0x00000000` | accepted, transformed |
| 4 missing map | `0x000000` | `0x000000` | none | none | fetch `0` | none |
| 5 EBUS | `0x008000` | `0x008000` | ordinary backing not used | none | fetch `0` | none |
| 6 reverse endian | `0x000000` | `0x000004` | `0x200004` | `0x340b1357` | `0x340b1357` | accepted |

CPU-visible results were `t1=0x1234`, `t2=0`, `t3=0x1357`, with exception code zero.

Phase 2 had **three** global equal-value translated-read candidates, demonstrating that payload equality is not a causal provenance rule.

The degraded phase is the key counterexample: the backing word is a real nonzero MIPS instruction, but the CPU consumes zero/NOP. Raw backing bytes alone therefore cannot identify the instruction image consumed by the CPU on this modeled path.

## Adversarial replay checks

The verifier mutates the captured event history and requires fail-closed behavior:

- duplicate an otherwise eligible in-context read -> no witness;
- change the read request address -> no witness;
- substitute raw for delivered in the degraded event -> no witness;
- remove the degraded translated read -> no witness;
- add an unrelated in-context translated read -> the valid witness remains unique and is not stolen.

All checks passed.

## Neutrality and hashes

Baseline, observer-disabled, observer-enabled and repeated observer-enabled runs produced identical semantic fixture facts and terminal state. The two enabled traces were byte-identical.

Recorded hashes:

- driver SHA-256: `74a9da2a81ad6ad38067299d916136bfe0f59b033b9313342443411f8c3661f7`
- observer SHA-256: `879ed76c86adc763935ddf949069a0dd614480f8eb6565712eb2e6c983f9f0cb`
- original builder SHA-256: `e33d2b415fc2ceb65fecb4e43c3cd694c6a7717a7aeab6431690b9601d4394eb`
- patched builder SHA-256: `ef84007ae90134ba56f336fca5aedd58903e42d58d56d7ccbef1c2c4113655cc`
- traced JSON SHA-256: `0d5340d4f771878c62ab5b68e00128dfaa3362bf1f2961dcb59b10edbecf4615`
- `results.json` SHA-256: `8f2e38c57c6e417037382373087d9877f36a09706daf66ab022e454fac165947`
- `manifest.json` SHA-256: `d74814c142c13c75649835e32a7243d59d3e1b04ac28b13b8e22202f971a19e5`

Terminal RAM SHA-256 was `0f9384ad18baccf06a90ceeaa0ed5d0a5bc922e81fe586dc52de38d3c36bca63`; HiddenRAM SHA-256 was `bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8`.

## Result

**VALIDATED** for the controlled pinned-ares interpreter scope.

A successful uncached translated scalar-RDRAM fetch can be causally joined to its mapped raw backing word and its post-CCI delivered CPU instruction value using one ordered fetch/read context, without relying on matching payload values.

The experiment also validates the architectural distinction Plaid needs to retain:

- **backing origin**: mapped physical backing/chip and raw bytes;
- **delivery transform/result**: CCI state and the word actually delivered to the fetch;
- **fetch context**: guest virtual address, translated physical address, post-endian bus request and ordering.

For a transformed/degraded fetch, treating the raw backing bytes as the executable image consumed by the CPU is unsound. Until a certificate/ProgramMap representation can encode the transformation and delivered instruction identity, that path must remain unsupported/Unknown rather than silently certifying the raw word.

## Limitations / explicitly not proved

This experiment does **not** prove:

- that ares' CCI degradation model is hardware-accurate;
- an N64-wide executable-fetch invariant;
- exhaustive coverage of every CPU bus/device path;
- cached/I-cache translated backing provenance or burst-fill composition;
- D-cache behavior or writeback provenance;
- TLB mapping identity/lifetime or alias history;
- mutation completeness, DMA/copy provenance, overlays, decompression or relocation;
- executable lifetime boundaries;
- reachability or closed-world control-flow closure;
- that EBUS or missing-map paths are intrinsically unknowable, only that this ordinary-backing witness must not claim them.

## Integration recommendation

**ADOPT** the semantic contract, not the research patch wholesale:

1. preserve raw mapped backing identity separately from the post-transform delivered instruction value;
2. join translated backing reads to fetches by explicit ordered context and the actual post-endian bus request;
3. reject ambiguous/missing joins;
4. keep transformed/degraded executable fetches Unknown unless the executable-image/certificate model explicitly represents the transform and delivered bytes.
