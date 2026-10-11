# Direct integration receipt: bounded RSP scalar lineage

Date: 2026-10-11

Worker: `gpt56sol-direct-rsp-scalar-20261011`

Base main: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`

Cluster: source-bound bounded RSP scalar DMEM load -> GPR generation -> scalar-store lineage

## Source research

- Branch: `research/rsp-scalar-load-store-lineage-gpt56sol`
- Final research commit: `3c89a579aef404dba01aab2353ac2f8723750907`
- Research note: `research/rsp-scalar-load-store-lineage.md`
- Spike: `spikes/043-ares-rsp-scalar-load-store-lineage/`
- Exact-pin GitHub Actions run: `37921606242` (success)
- Issue #4 research closeout: `6079693307`
- Exact pinned ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Exact pinned Gopher64 revision from `refs.lock.toml`: `e96debac941a26ba4961e5145056c0821d3a56f7`

The research run's exact-pin RSP scalar load/store lineage step passed against those pinned references. The research evidence covered 14 scenarios, 138 ordered instruction/effect events, 16 fresh load generations, 14 verified store edges, deterministic observer-disabled/enabled/repeat machine projections, and eight rejected forged histories.

## Current-main reproduction

Current main already had SP DMA/history consumers and CPU def-use/copy consumers, but no production Rust consumer for the validated RSP scalar DMEM-load -> GPR-generation -> scalar-store boundary. The production candidate was therefore built from current main rather than merged from the research branch.

The current-main candidate reproduces the important counterexamples as Rust regressions:

- equal payloads loaded from different DMEM bytes retain the later concrete source and generation;
- reloading the same source with the same payload still mints a fresh GPR generation;
- an unrelated GPR write does not destroy the tracked source register's lineage;
- same-value `ORI` and `ADDU` writes to the tracked register cut load lineage rather than inheriting it from payload equality;
- DMEM addresses use the validated 4 KiB wrap/bit-12 masking and retain exact byte-lane identities;
- missing effects, forged register-selector metadata, forged post-load values, duplicate/reordered ordinals, stale source hashes, and forged reports fail closed.

## Adopted invariant

`plaid-core::rsp_scalar` is a bounded compiler-time source replay, not a hardware-wide RSP provenance oracle.

For the accepted scalar subset:

1. The caller must supply an externally trusted SHA-256 for the complete captured source. The replay verifies the digest before consuming the source.
2. Source order is authoritative: ordinals must be contiguous; the consumer does not sort or repair histories.
3. Each accepted scalar DMEM load creates a fresh local load/GPR generation even when source bytes and values equal an earlier generation.
4. Initial DMEM bytes have local `(phase, offset)` source identities. Accepted same-width scalar stores can propagate those byte identities through a live load generation.
5. Store attribution requires exact captured byte effects in the expected order, offsets, and values.
6. Effective scalar DMEM byte lanes use the validated 4 KiB wrapping address behavior.
7. Validated whole-register writers `ORI` and `ADDU` cut the destination register's load lineage, including when the new value equals the old value.
8. Unsupported instructions, width-changing/unproved transformations, malformed contexts, and incomplete effects reject or remain unknown; they are not reconstructed from equal values or final state.
9. Phase transitions reset local register lineage. Phase identities cannot be silently reused or reordered.
10. A stored report is not trusted by itself: `verify_rsp_scalar_report` replays the bound source and checks the whole report.

The report deliberately hard-codes these closure-strengthening flags to `false`:

- `primitive_read_coverage_certified`
- `gpr_writer_coverage_certified`
- `source_storage_ancestry_certified`
- `mutation_coverage_certified`
- `executable_lifetime_certified`
- `native_complete`

## Rejected / superseded patches and interpretations

- The research branch and reference-emulator instrumentation were **not** mechanically merged. They remain evidence/oracles.
- The absence of a primitive successful-DMEM-read callback was **not** converted into a read-census claim. Scalar load effects are reconstructed only inside this bounded, source-bound replay using the validated pinned-reference semantics.
- Matching register payloads are **not** provenance. Equal-value reloads get new generations; same-value unproved writers cut lineage.
- Matching addresses are **not** ultimate storage ancestry. `(phase, offset)` is a local source identity only.
- A finite scalar trace is **not** a complete RSP GPR-writer census.
- No arithmetic/vector transform ancestry is inferred from output equality.
- No SP DMA, CPU writer, cache/TLB, scheduler, interrupt/reset/save-restore, executable-lifetime, whole-ROM closure, solver-CLOSED, or native-complete claim is introduced.

## Files changed

- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/src/rsp_scalar.rs`
- `crates/plaid-core/src/rsp_scalar/tests.rs`
- `research/integration-receipts/20261011-rsp-scalar-lineage-gpt56sol-direct-rsp-scalar-20261011.md`

`progress.json` is intentionally unchanged: this bounded consumer does not complete W012 or another project milestone.

## Validation

Research evidence:

- GitHub Actions `37921606242`: **success**.
- Exact-pin scalar lineage spike against ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` and Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`: **passed**.

Production candidate CI before this receipt:

- Pull request #8 workflow `38151709777`: **success**.
- Exact decoder dependency pin: **passed**.
- `cargo fmt --all -- --check`: **passed**.
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: **passed**.
- `cargo test --locked --workspace`: **passed**.
- Synthetic CLI checks: **passed**.
- CPU-copy, XORI history, CPU-SP producer, RSP-CPU IMEM composition, XORI cache visibility, PageMask cache remap, PI cache visibility, SP-DMA DMEM ingress, RSP store isolation, guest EntryHi/TLBR cache reactivation contract suites: **passed**.
- Independent fetch-summary assignment oracle: **passed**.

Earlier development-only PR runs exposed a formatting failure and then a `clippy::too_many_arguments` failure in a test helper. Both were corrected structurally before the green candidate; neither failure was waived or suppressed.

A final clean-head validation and canonical-main validation are required by the main-write protocol before this receipt can support an `INTEGRATED` closeout.

## Limitations and remaining proof obligations

This integration leaves the following obligations open:

- complete RSP GPR writer census, including all scalar and vector writers relevant to provenance;
- primitive successful DMEM read observation/census if a stronger read-completeness claim is needed;
- CPU/SP DMA/external DMEM mutation chronology and ultimate storage-writer ancestry;
- decompression/relocation and wider scalar/vector transform provenance;
- RSP task, scheduler, interrupt, reset/NMI, save/restore, and lifetime generations;
- RSP executable/microcode identity and executable lifetime;
- composition with CPU mapping/cache/TLB evidence when executable products cross domains;
- whole-ROM executable mutation census, complete root/indirect-target closure, and W012 executable DMA/overlay closure;
- any native-complete claim.

The production abstraction is useful because later composition can consume a concrete, falsifiable local RSP register-generation edge instead of guessing provenance from values. It is intentionally insufficient, by itself, to make any CLOSED decision easier.
