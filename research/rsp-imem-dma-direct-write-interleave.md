# RSP IMEM DMA/direct-write interleaving

Date: 2026-10-09

Status: **VALIDATED (bounded pinned-ares component scope)**

## Question

Can a multi-row RDRAM -> RSP IMEM SP-DMA be treated as one atomic installed-microcode residency generation when a CPU-originated direct IMEM write occurs between completed DMA rows?

## Result

No. For exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, one count row is executed per `RSP::dmaTransferStep()`. When `current.count` remains, the engine decrements the count, advances/skip-adjusts the DRAM address, queues the next row and returns. `RSP::writeWord` independently writes the IMEM word selected by the CPU SP-memory window.

The exact executable component fixture interleaved that real direct-write sink between two real DMA row steps. A CPU write to bytes in the already completed first row survived final completion of the same DMA transfer. A CPU write to the future second-row destination was later superseded by that row. The same rule held across the IMEM `0xff8 -> 0x000` wrap boundary.

Therefore a stable SP-DMA descriptor is useful as a **transfer identity**, as required by ADR-0059, but it is not a resident executable generation. Resident IMEM provenance must remain latest-writer sensitive at byte granularity (or an exactly equivalent representation) throughout the transfer. Transfer completion may group the row events but must not retag all row destinations as if no interleaving writer had occurred.

A same-value direct write was also executed after the first row. Its before/after/final word value remained `0x11111111`; content comparison cannot recover that successful mutation revision. This matches the broader mutation-revision principle already used for D-cache lineage in ADR-0067.

## Exact inputs

- Plaid integration base inspected before claiming: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- ares pin from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Research branch: `research/rsp-imem-interleave-gpt56sol`
- Code-tested branch head: `8d2b64ffaf043cf5b10f73a855b55feceb5630b6`
- Prior inputs reviewed read-only: `research/rsp-imem-provenance.md`, `research/sp-dma-lifecycle.md`, `spikes/018-ares-rsp-imem-provenance/`, `spikes/034-ares-sp-dma-lifecycle/`

No ROM, firmware or copyrighted game asset is used.

## Exact source contract

The source guard binds the inspected pinned files:

- `ares/n64/rsp/dma.cpp` SHA-256 `b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6`
- `ares/n64/rsp/io.cpp` SHA-256 `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860`

Relevant source behavior:

1. `dmaTransferStep()` performs every 8-byte fragment in the current row.
2. If `dma.current.count` is nonzero, it decrements the count, adds skip, calls `dmaQueue(...)`, and returns without ending the current descriptor.
3. `RSP::writeWord` independently routes CPU SP-memory writes with bank bit 12 to `imem.write<Word>`.
4. `pbusAddress` is `n12`, so row progression wraps modulo the 4 KiB bank.

`RSP::main()` calls `dmaStep(...)` after each halted chunk or RSP instruction, and the DMA row step itself returns after rescheduling. This is source evidence for non-atomic row processing. The experiment below deliberately exercises the storage ordering directly; it does not claim a complete guest-scheduler reachability proof for every possible CPU instruction interleaving.

## Executed experiment

Durable fixture: `spikes/043-ares-rsp-imem-interleave/`.

The C++ driver reuses Plaid's existing untouched headless ares component builder, disables both recompilers, forces controlled identity RDRAM, and uses the real pinned `RSP::dmaTransferStep` plus `RSP::writeWord` paths. No ares instrumentation is generated or patched.

Cases:

1. **After completed row:** DMA row 0 installs 8 bytes at IMEM `0x200`; CPU directly overwrites word `0x200`; row 1 installs at `0x208`. The CPU word survives final DMA completion.
2. **Before later row:** after row 0, CPU writes word `0x208`; row 1 later replaces it with its RDRAM payload.
3. **Same value:** after row 0, CPU writes the already resident `0x11111111` back to word `0x200`; before/after contents are equal even though the sink call occurred.
4. **Wrap:** row 0 installs at `0xff8`; CPU writes both `0xff8` and future wrapped row `0x000`; row 1 wraps to `0x000`, replacing only the future-row write while the `0xff8` CPU overwrite survives.
5. **Non-overlap:** CPU word `0x300` remains unchanged by completion of the unrelated transfer.

The executable is run twice and its complete JSON stdout must be byte-identical.

Reproduce:

```bash
python3 spikes/043-ares-rsp-imem-interleave/model.py
python3 spikes/043-ares-rsp-imem-interleave/source_guard.py .refs/ares
python3 spikes/043-ares-rsp-imem-interleave/run.py
```

## Deterministic observations

Exact ares produced:

- completed-row overwrite final words at `0x200..0x20f`: `AAAAAAAA 22222222 33333333 44444444`;
- future-row overwrite: intermediate `BBBBBBBB`, final `33333333`;
- same-value write: before = after = final = `11111111`;
- wrap intermediates: `CCCCCCCC` at `0xff8`, `DDDDDDDD` at `0x000`;
- wrap finals: `CCCCCCCC 66666666` at `0xff8`, then `77777777 88888888` at `0x000`;
- non-overlap control: `EEEEEEEE` remains at `0x300`.

This directly falsifies a completion rule that assigns every byte ever touched by a transfer back to that transfer's row origin.

## Adversarial replay model

`model.py` compares per-byte latest-writer replay against that deliberately unsound transfer-completion rule. It includes the four fixed provenance cases above and 5,000 deterministic randomized histories with 2-4 rows, ordinary/wrapped destinations, writes to completed/future/unrelated locations, and same-value writes.

Observed deterministic report:

- histories: `5000`
- naive bad histories: `2207`
- final surviving CPU bytes misclassified by the naive rule: `9848`
- same-value CPU writes generated: `2809`
- model SHA-256: `6a87876dfadfd480a64a28c32e96bd1bd0ae84050ece8827ad29bf21a39328f4`

Fixed naive misclassifications:

- completed-row overwrite: 4 bytes
- future-row overwrite later replaced by DMA: 0 bytes
- same-value completed-row overwrite: 4 bytes
- wrap case: 4 bytes

The model is an adversarial verifier test, not an N64 timing oracle.

## Reproducibility receipt

Authoritative exact-pin GitHub Actions run:

- run: `37915159620`
- job: `113769429159`
- runner image: Ubuntu 24.04.5, `20261004.327.1`
- code-tested head: `8d2b64ffaf043cf5b10f73a855b55feceb5630b6`
- result JSON SHA-256: `8b84302b5d005fc5bd75648bd6afcf670d7e7f6e8a4c927ec2353e07eccc0405`
- repeated reference stdout SHA-256: `144e6dcdbbc47aacd7a1a023ffbd88c8a53237b0865b79bcafa80fe735413ce8`
- model SHA-256: `6a87876dfadfd480a64a28c32e96bd1bd0ae84050ece8827ad29bf21a39328f4`
- artifact ID: `11609876658`
- artifact ZIP digest: `sha256:b984f7fa0719554db1c5372e9182c1efaf7131730fe9ca1c6f3980813e505abf`

All workflow steps completed successfully: exact pin checkout, source guards, syntax/model checks, compiled reference execution, repeated-output check, result hashing and artifact upload.

## Architectural consequence

For this bounded scope:

- keep one stable identity for the promoted/current SP-DMA request and group its count/skip rows under it;
- record each completed IMEM row/fragment as storage effects in chronology order;
- retain per-byte latest-writer mutation revisions through the transfer;
- a direct write after a byte's last DMA row remains the resident writer even after the parent transfer completes;
- a direct write before a later overlapping DMA row is superseded only when that row's actual sink occurs;
- same-value successful direct writes still advance writer identity/revision;
- wrap is normal modulo-bank ordering, not an atomic contiguous range;
- a microcode content hash may deduplicate proved bytes, but transfer ID or hash equality must not stand in for residency lifetime.

A higher-level "microcode installation" object may summarize a transfer only if it preserves the ordered constituent effects and the final mixed writer set. It cannot mean "all bytes touched by this DMA now share one generation."

## Limitations / what this does not prove

- This validates pinned ares component storage semantics and the provenance counterexample, not physical N64 timing.
- The direct CPU SP-memory sink is invoked through the real component API between row steps; a full guest CPU/RSP scheduler fixture proving every such interleaving is reachable was not executed here.
- The fixture uses controlled identity-mapped RDRAM and RDRAM -> IMEM direction only.
- It does not cover translated/degraded RDRAM, pending/FULL hardware policy, save/restore/reset/debugger epochs, byte/halfword CPU IMEM stores, reverse DMA, RSP producer lineage, or exhaustive microcode/task reachability.
- Dynamic/component observations do not prove closed-world completeness.

## Recommendation

**ADOPT** the negative invariant: SP-DMA transfer identity is not an atomic RSP executable residency generation. Preserve ordered per-byte writer revisions and compose a final installation/lifetime only from those effects. If production wants to claim actual CPU guest interleaving reachability rather than merely handle it safely when observed, run a separate scheduler-level fixture.
