# Solver RSP microcode closure deletion attack

Worker: `gpt56sol-solver-rsp-microcode-closure-20261010`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Result: **REJECTED**. Current `main` already fails closed when typed RSP microcode facts are retained, even if derived `unresolved` diagnostics are deleted.

## Question

Can `Scope::DeclaredStaticImages` report `CLOSED` when an otherwise closed CPU static CFG retains an RSP `Microcode` fact but no independently verified RSP byte-provenance/lifetime certificate, especially after importer-produced unresolved diagnostics are removed?

The attack matters because Plaid's RSP research has repeatedly shown that content identity is not executable lifetime identity. If the solver relied only on a derived diagnostic, deleting that diagnostic could launder an RSP executable-universe obligation.

## Current-main behavior

`ProgramMap` retains RSP facts as `rsp_microcodes: BTreeSet<Microcode>`. The current `Microcode` shape is deliberately only a content/range description: SHA-256, IMEM start, size, and evidence. `ProgramMap::validate()` checks the digest shape, evidence references, and that the declared nonempty IMEM range stays within 4 KiB.

`solver::solve()` does not rely on `map.unresolved` to rediscover the RSP exclusion. Under `Scope::DeclaredStaticImages`, a nonempty `map.rsp_microcodes` participates directly in the typed dynamic-effect guard and emits `dynamic_effect_outside_scope`. The declared assumptions explicitly exclude RSP execution. Under `Scope::WholeRom`, the solver independently emits `unproven_rsp_policy` because required RSP microcode identities and coverage have no verifier.

Therefore the hypothesized false-CLOSED deletion path is not present on the canonical base.

## Prior evidence composed

This result is about solver consumption of already-retained facts, not primitive RSP semantics. It composes rather than reopens the following validated research:

- `research/rsp-imem-provenance.md`: equal-byte IMEM reloads can have distinct latest-writer origins; direct CPU IMEM writes can supersede DMA provenance; address + payload/hash is not an executable lifetime identity.
- `research/rsp-microcode-installation-lifetime.md`: a promoted SP-DMA transfer can support a complete installation certificate only after all expected causal fragments exist; byte-identical transfers remain distinct causal generations; an overlapping mutation terminates the exact installed-image lifetime.
- `research/rsp-imem-dma-direct-write-interleave.md`: transfer completion is not an atomic retag of all touched IMEM bytes; final installed state can contain a mixed per-byte writer set after CPU/DMA interleavings.
- the completed RSP savestate/microcode-epoch work in issue #4: synchronized restore can resurrect older RSP executable state without replaying external writer/installation histories, so latest-token or equal-content repair is unsound.

Those findings explain why the current fail-closed solver boundary is appropriate. They do **not** turn today's `Microcode` content fact into a positive provenance/lifetime certificate.

## Executable adversarial regression

`crates/plaid-core/tests/solver_rsp_microcode_closure.rs` exercises three bounded attacks against the real current solver:

1. Start with a two-word direct self-loop that genuinely returns `CLOSED` under `DeclaredStaticImages`. Add one valid typed RSP microcode fact, clear `map.unresolved`, and require `OPEN` plus `dynamic_effect_outside_scope`.
2. Add a second microcode fact with the **same SHA-256 payload identity** at a different IMEM span, clear diagnostics again, and require the solver to remain `OPEN`. Equal content therefore cannot erase the typed RSP exclusion.
3. Solve a retained microcode under `WholeRom` and require `unproven_rsp_policy`. Separately, forge an IMEM range `4092 + 8`; `solve()` must reject the map at validation with `invalid RSP IMEM range` rather than reaching a closure decision.

The test deliberately does not manufacture an RSP generation from the SHA-256. Its purpose is only to verify that retained typed RSP evidence cannot disappear from the closure gate.

## Receipts

Branch: `research/solver-rsp-microcode-closure-gpt56sol`

Branch workflow: `.github/workflows/research-solver-rsp-microcode-closure.yml`

Final code-bearing commit before this note: `7f6cf9ace7c64ca90d9655a9d9c58594d585d974`.

Authoritative green run on that commit:

- Actions run: `38046161071`
- job: `114196010938`
- focused `cargo test -p plaid-core --test solver_rsp_microcode_closure -- --nocapture`: **3 passed**
- complete `cargo test -p plaid-core`: **PASS**
- `cargo fmt --all -- --check`: **PASS**
- `cargo clippy -p plaid-core --all-targets -- -D warnings`: **PASS**

The preceding run `38046107504` also passed the focused regression and complete `plaid-core` suite; it failed only because rustfmt wanted one chained insertion collapsed onto one line. No semantic assertion changed in the formatting-only commit.

## Reproduction

```sh
cargo test -p plaid-core --test solver_rsp_microcode_closure -- --nocapture
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --all-targets -- -D warnings
```

## Closed-world impact

This removes one suspected deletion-resistance hole: a retained `rsp_microcodes` fact cannot be made compatible with finite static closure merely by deleting `unresolved` diagnostics. The static scope explicitly excludes RSP, and whole-ROM closure independently retains an RSP policy obligation.

It does **not** solve the real RSP closed-world problem. Production still lacks a positive certificate model that can prove complete RSP executable roots, exact IMEM writer/provenance histories, mixed-byte residency, save/restore epochs, installation lifetimes, all future RSP mutations, and exhaustive microcode/task reachability. Until those exist, the correct behavior is to remain OPEN rather than infer identity from SHA-256 equality.

## Integration recommendation

**KEEP THE EXISTING PRODUCTION GUARD; no production patch is justified.** The focused regression is useful as deletion-resistance coverage and can be adopted if the primary integrator wants a permanent test. Do not reinterpret `Microcode { sha256, imem_start, size, evidence }` as a verified lifetime identity, and do not weaken `dynamic_effect_outside_scope` or `unproven_rsp_policy` based on equal payloads or importer diagnostics.
