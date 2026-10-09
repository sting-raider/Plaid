# RSP IMEM installation lifetime composition

Date: 2026-10-09

Status: **VALIDATED** for the bounded exact-pin ares experiment described here.

Canonical Plaid base selected before the claim: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.

Validated research-branch run commit: `9e236ca7551c3ba4b1346c9fa5b06dabb89523b6`.

Exact ares pin: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Question

Can one promoted SP-DMA read request plus its ordered completed IMEM sink effects define a bounded RSP executable-installation generation across count/skip rows and modulo-IMEM wrap without incorrectly absorbing interleaved CPU IMEM writes or merging byte-identical reloads?

## Hypothesis

A promoted current request can group only the concrete completed DMA IMEM sink events causally executed while that request is active. The grouping must not imply homogeneous ownership of the whole requested span. Same-value CPU writes create distinct writer generations, same-payload reloads create distinct request generations, and request handoff cannot depend on a BUSY falling edge.

## Baseline and instrumentation

Durable fixture: `spikes/043-ares-rsp-imem-install-lifetime-gpt56sol/`.

The generated ares shadow is guarded against the exact pin and exact source hashes:

- `ares/n64/rsp/dma.cpp`: `b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6`
- `ares/n64/rsp/io.cpp`: `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860`

The observer adds no RSP object fields. It records four ordered facts only after their corresponding exact-pin actions:

1. `pending -> current` request promotion;
2. completed DMA `imem.write<Dual>` sink;
3. final completion of the active read request before BUSY clear / possible immediate handoff;
4. completed CPU `imem.write<Word>` sink after the original recompiler invalidation.

The baseline binary is built without this observer shadow. A second sensor binary is run once with callbacks disabled and twice with callbacks enabled. CPU and RSP recompilers are disabled in the fixture.

## Fixture cases

1. **Count/skip plus same-value CPU interleave.** One read request has two 8-byte rows. After the first DMA sink at IMEM `0x200`, a CPU Word store rewrites bytes `0x204..0x207` with the same `0x11` payload already present. The second DMA row then lands at `0x208`. Final contents cannot reveal that the middle four bytes have a newer CPU writer generation.
2. **Byte-identical reload.** Two independently promoted requests copy byte-identical 16-byte payloads from different RDRAM addresses into the same IMEM addresses `0x300..0x30f`. The architectural IMEM hashes before and after the second load are equal, but request generations are distinct.
3. **Modulo-IMEM wrap.** One 16-byte request starts at IMEM `0xff8`; its two completed Dual sinks are owned by the same request and land at `0xff8..0xfff` then `0x000..0x007`.
4. **Immediate current-to-pending handoff.** A queued current request and one pending request complete/promote across consecutive transfer steps. The first request completion and second request promotion occur without requiring an externally observable BUSY-low sampling boundary.

## Replay verifier

`verify.py` reconstructs per-byte current writer ownership only from ordered completed effects. It fails closed unless:

- every promotion occurs with no active request and a strictly increasing request generation;
- every DMA sink belongs to the currently active promoted request;
- CPU sinks carry no DMA request identity;
- every completion matches the active request;
- the trace ends with no active request.

Three adversarial trace mutations are required to fail:

- a DMA sink forged onto the wrong active request;
- a reused request-generation ID;
- a missing final completion.

All three were rejected.

## Exact reproduction

```bash
python3 spikes/043-ares-rsp-imem-install-lifetime-gpt56sol/run.py
```

GitHub Actions execution used Ubuntu 24.04 and exact ares checkout `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Validated workflow run: `37915747585`, job `113771366097`.

The run compiled the verifier recipes, built both the uninstrumented and instrumented exact-pin ares fixtures, executed all fixture cases, replayed the trace, ran adversarial verifier mutations and uploaded the ignored evidence bundle.

## Deterministic observations

The successful run reported:

- architectural baseline state equals callback-disabled sensor state equals traced sensor state: `true`;
- repeated traced executions are byte-identical: `true`;
- completed promoted request generations: `[1, 2, 3, 4, 5, 6]`;
- ordered event count: `23`;
- rejected adversaries: `wrong-active-request`, `reused-request-id`, `missing-completion`;
- trace SHA-256: `52865df75cc12f954527166c19b2a1f300127ca69660bd4451fa3c2947223fcb`;
- manifest SHA-256: `94f64164891be736f96b97b92e02bf079896b3355996e27038c7318bb8674b89`;
- evidence artifact ID: `11609653501`;
- uploaded artifact archive SHA-256: `eadae7e52c99b302978fa33567b188130017ae208335bf630fcf77304c9eb6a9`.

Project-owned source receipts for the successful run:

- `driver.cpp`: `2abd8c225fa1ad8a59a8cfef5c252ac774a17ebac233fa054da9330ad8712206`;
- `prepare.py`: `7f4763062e1a44458b7dcc06c0b5f929001a490cff1a430ea428293f4f8d8e8a`;
- `verify.py`: `3c821827c314736d351fbd42bf339ea56ea18b408124ddef8e1ac11f61614e88`.

## Result

**VALIDATED.** Stable promoted-request identity is sufficient to group the *concrete ordered completed DMA IMEM sink fragments* belonging to one bounded SP-DMA read request, including count/skip rows and modulo-IMEM wrap. It is not sufficient to label the entire nominal destination span as a homogeneous DMA-owned executable lifetime.

The same-value CPU interleave is the useful counterexample to span/content inference: bytes `0x204..0x207` have a newer CPU writer generation even though their values do not change. Likewise, byte-identical same-address reloads are distinct executable writer generations despite equal final IMEM hashes. Request completion/promotion identity also must not be inferred from an externally sampled BUSY falling edge.

For a future ProgramMap/provenance model, an RSP microcode-installation object may safely contain one promoted request's ordered measured DMA effects, but current executable-byte ownership must remain effect/byte-span granular and supersedable by later CPU/RSP/DMA writer generations.

## Failed harness iteration

Workflow run `37915200230` was a false green caused by shell `python ... | tee` without `pipefail`; its underlying baseline build failed. The workflow was corrected to fail on the producer exit code and print compiler logs. Run `37915438674` then correctly exposed a C++ fixture name collision (`Event`), which was fixed by renaming the project-owned type. Neither failed run is evidence for the hypothesis. Only run `37915747585` is the validated receipt.

## Limitations / explicitly not proved

This result does **not** prove:

- whole-ROM or all-title RSP microcode completeness;
- hardware truth beyond the exact pinned ares model;
- provenance of the RDRAM source bytes before the observed DMA sinks;
- all possible CPU/SP write widths or aliases into IMEM;
- RSP-generated IMEM code through some other path not exercised here;
- save-state/reset/power-cycle generation boundaries;
- dynamic reachability or closed-world completeness of any resulting RSP executable generation;
- that payload equality or final-memory equality can ever substitute for causal writer identity.

The integration recommendation is to adopt the **request-container + exact-effect ownership rule**, not the experiment's generated observer implementation wholesale. The primary integrator should reimplement or compose that semantic rule with the canonical mutation/provenance event stream.
