# RSP executable savestate restore epoch

Date: 2026-10-10

Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Result: **VALIDATED for the bounded exact-pinned-ares synchronized restore composition described below.**

## Question

Plaid already had two independently validated facts:

1. a synchronized compiler-time ares savestate load is a provenance epoch boundary for restored CPU mapping/context/I-cache state; and
2. a promoted SP-DMA request can establish one exact RSP IMEM microcode-installation lifetime whose identity must not be reconstructed from payload equality, BUSY edges, or later register values.

The remaining seam was whether those rules also have to compose across RSP executable state. Specifically: can loading an older synchronized snapshot directly resurrect an older RSP IMEM image and execution state without replaying the SP-DMA/direct-write events that originally established those bytes, while an external provenance sidecar still contains newer abandoned-future writer/install generations?

## Hypothesis

Yes. Post-load RSP executable state must be rooted in a snapshot-qualified restore epoch unless trustworthy writer/install histories are themselves serialized and restored from that snapshot. Current IMEM bytes, content hashes, destination addresses, current DMA descriptors, or the latest matching external install/writer generation are not sufficient to reconnect causality across load.

The exact-reference experiment validates this bounded hypothesis.

## Prior evidence composed

This lane intentionally starts at the seam between completed work rather than re-proving the primitives:

- `research/ares-savestate-tlb-cache-epoch.md`: synchronized ares load can recreate an older CPU TLB mapping, EntryHi/ASID context and resident I-cache line without replaying the live mapping/context/fill operations; therefore a restore epoch is required.
- `research/rsp-microcode-installation-lifetime.md`: an exact promoted SP-DMA descriptor can own a complete RDRAM -> RSP IMEM installation, equal-payload installs remain distinct generations, and overlapping direct IMEM writes terminate the prior exact image lifetime even when values match.

## Exact pinned source contract

`experiments/rsp-savestate-microcode-epoch/source_guard.py` checks `refs.lock.toml`, requires exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, and hashes the two serialization sources used by the proof.

At that pin, `ares/n64/rsp/serialization.cpp::RSP::serialize` directly serializes:

- DMEM and IMEM;
- pipeline address/instruction/clocks and dependency state;
- DMA `pending` and `current` descriptors, BUSY/FULL read/write state and DMA clock;
- GPRs and `ipu.pc`;
- branch PC/next-PC/state;
- VPU state.

The DMA descriptor serializer also includes `originPc` and `originCpu`. The same source contains no `dmaTransferStart`, `dmaTransferStep`, or `imem.write` replay call.

At the same pin, `ares/n64/system/serialization.cpp::System::unserialize` validates the snapshot, invokes `power(false)` for synchronized states, then deserializes system state. The system serialization order includes RDRAM, then CPU, then RSP.

Source hashes from the successful exact-pin run:

- RSP serialization SHA-256: `57122028dd41ceae32d51c906e9a307fdb0e0c8070103e8e8c56307fccaaf4b1`
- N64 system serialization SHA-256: `284dde684315884a5ae5cfb7e5a9ce2e2d3e261a8cecaab508cd18a339425744`

This establishes that synchronized load can install RSP executable/machine state directly. It does **not** by itself prove every possible mid-DMA continuation behavior; the executable fixture below targets completed IMEM installation plus selected execution state.

## Executable experiment

Artifacts live under `experiments/rsp-savestate-microcode-epoch/`.

The fixture disables CPU and RSP recompilers, uses identity-mapped RDRAM, and creates external research counters deliberately outside ares serialization.

### Phase 1: visibly different rollback

1. A real one-fragment RDRAM -> RSP IMEM SP-DMA installs image A at IMEM `0x200`. This is external install generation 1 / writer generation 1.
2. The fixture fetches from the installed IMEM and records selected RSP execution state, then saves synchronized snapshot S0.
3. A later real SP-DMA replaces the same IMEM span with distinct image B, creating install/writer generation 2, and the selected RSP execution state is changed.
4. Loading S0 restores image A and the captured execution state. The external install/writer counters remain 2 and receive no replay event.
5. A post-load RSP fetch returns image A instruction `0x24010001`.

This is the easy case: state values visibly roll back while provenance-sidecar generations do not.

### Phase 2: equal-state adversary

The stronger case tries to make a value-based verifier succeed incorrectly:

1. After the first restore, another real SP-DMA installs byte-identical image A from a different later source event, minting install/writer generation 3.
2. A direct CPU-visible same-value IMEM write of the first word mints writer generation 4 without changing the word bits.
3. Selected IMEM/execution state is intentionally made value-identical to S0 before the second load.
4. Loading S0 again increments only the fixture's restore epoch. External live histories remain `{install:3, writer:4}`.
5. The restored bytes/hash still match the later equal events, so deliberately naive matchers report installation 3 and writer 4. Both are causally false as the installer of the post-load state: synchronized deserialization installed it.

Successful result payload:

```json
{"fixture":{"external_generations":{"install":3,"restore_epoch":2,"writer":4},"naive":{"latest_matching_install":3,"latest_matching_writer":4},"state":{"distinct_rollback":true,"equal_state_before_second_restore":true,"equal_state_restore":true,"imem_sha256":"58e1f9ea2a7dea394be517fd1e6b51f58118b7ed8e54b2ac8f5746be3bf36246","imem_word0":604045313,"imem_word1":604110850,"post_restore_fetch":604045313,"s0_install_generation":1}},"model_sha256":"2dbaab4c393de7a094bc73a848a8534c4032eceed6d7b58c47efde2708a5aead"}
```

The fixture is executed twice and must produce byte-identical stdout.

## Independent adversarial model

`model.py` represents restored RSP executable state as a root `restore(snapshot, epoch, component)` with snapshot-captured ancestry nested beneath that boundary.

It rejects six explicit forged certificates:

- latest equal-payload install substituted for captured origin;
- latest same-value direct writer substituted for captured origin;
- abandoned distinct S1 install;
- wrong restore epoch;
- wrong snapshot;
- missing restore boundary.

It separately rejects CPU/RSP compositions whose snapshot or restore epoch differs.

A deterministic 50,000-history falsification sweep generates random abandoned post-S0 install futures. A naive `latest live generation` rule is wrong in all 50,000 histories after restore. A stricter `latest matching image payload` rule is still wrong in 33,131 histories because a later equal image exists. Model SHA-256: `2dbaab4c393de7a094bc73a848a8534c4032eceed6d7b58c47efde2708a5aead`.

## Receipts

Successful exact-pin Actions run before this final note:

- run: `38004153367`
- job: `114068961666`
- branch head tested: `85f4373e0fa64fc4737601112dd5ce2877d810d2`
- fixture stdout SHA-256: `330d5792e6a18ad593d0a03a8e82c44ba6be9ab439dd687fe1bb581b020b1f5e`
- canonical result SHA-256: `9b672bf3290c470f05d464f3520e21dab605aa810c67a49d419df23b6a6c7aa9`
- retained artifact: `11649989460`
- artifact ZIP digest: `sha256:dcce27dd9f88603a2b10c035f9e7496f81fb1c902c8075bbac792e3e04de1e56`

The first workflow attempt failed only because the source guard initially parsed `refs.lock.toml` using the wrong table shape; the model had already passed. The guard was corrected to read the repository's `[[repo]]` entries, after which exact source guarding and live execution both passed. No semantic assertion was weakened.

## Minimum evidence rule

For snapshot `S` loaded into exploration epoch `E`, restored RSP executable state must be represented by either:

1. trustworthy causal writer/install histories serialized inside `S` and restored under the same capture namespace, or
2. a restore root such as `restore(S, E, rsp_imem)` / `restore(S, E, rsp_exec_state)` whose captured ancestry is explicitly attached.

If a CPU-side fetch/root proof and an RSP-side proof cross the same synchronized load, their restored components must agree on snapshot/restore epoch. A live generation that happened after S was captured cannot become the post-load causal predecessor merely because its bytes, hash, address, descriptor, PC or register values match.

Same values do not imply same provenance, and load itself is an operation even when every inspected before/after value is equal.

## Closed-world impact

Checkpoint/fork exploration can otherwise manufacture an impossible RSP executable lineage. A newer abandoned-future microcode installation or direct IMEM write can remain in an external provenance ledger after load; value-based joining can then attach restored RSP fetches to that future event and falsely discharge executable-byte provenance, microcode lifetime, task/root or indirect-reachability obligations.

Therefore the restore epoch is a whole-system composition boundary, not merely a CPU cache/TLB concern. Any native-complete/closed-world certificate that relies on compiler-time savestate exploration must either restore RSP provenance histories consistently with the snapshot or fail OPEN/UNKNOWN for the affected RSP executable state.

## Remaining gap

This is bounded exact-reference evidence, not a physical N64 savestate behavior claim. The fixture covers one completed 8-byte SP-DMA IMEM installation, a distinct replacement, an equal-payload replacement, one same-value direct IMEM write, selected restored execution state and post-restore fetch. It does not dynamically validate continuation from every possible partially active DMA descriptor even though exact source shows those descriptors and clocks are serialized.

It also does not cover every RSP IMEM mutation source, every subword/vector/self-modifying path, reset/NMI semantics, debugger mutation provenance, distributed snapshot IDs, provenance sidecar persistence formats, arbitrary task scheduling, exhaustive RSP roots/indirect targets, or whole-ROM closure. Those remain separate obligations.

## Integration recommendation

**ADOPT** the restore-epoch composition rule, not the research fixture wholesale.

- Treat synchronized compiler-time load as a snapshot-qualified boundary for RSP executable bytes and execution state, just as for CPU mapping/context/cache state.
- Serialize/restore provenance histories from the same snapshot namespace or mint fresh restore-root identities for RSP IMEM/execution/DMA-relevant components.
- Preserve captured writer/install ancestry beneath the restore root when it is trustworthy; do not reconnect to newer live histories by value equality.
- Require cross-component CPU/RSP certificates after a synchronized load to agree on snapshot/restore epoch.
- Keep closure OPEN wherever required restored provenance cannot be reconstructed.

No production patch is proposed in this branch because current canonical Plaid does not yet expose one unified production whole-system snapshot/provenance sidecar model to patch safely.
