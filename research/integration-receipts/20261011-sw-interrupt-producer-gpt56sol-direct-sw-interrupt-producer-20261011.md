# Direct integration receipt: guest Cause software-interrupt producer history

Date: 2026-10-11

Worker: `gpt56sol-direct-sw-interrupt-producer-20261011`

Cluster: source-bound guest CP0 Cause software-interrupt producer generations and pending-bit writer ownership

## Source research

- `research/sw-interrupt-producer-gpt56sol` at `93483c33832069680d31f969cfb599d631e45dbf`.
- `research/sw-interrupt-producer.md`.
- Original exact-pin Actions run `37999241841`, job `114052989074`.
- Fresh exact-pin rerun during integration: run `37999241841`, rerun job `114512559014`, PASS.
- Locked behavioral references: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`, Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`.

Research branches were evidence, not merge authority. No research workflow, emulator or experiment harness is a production dependency.

## Reproduced evidence

The bounded ownership relation is:

`new_ip = (old_ip & 0xfc) | ((raw_cause >> 8) & 0x03)`.

The production regression exhaustively enumerates all 256 prior pending-byte states against all 65,536 low Cause operand patterns: 16,777,216 cases. It reproduces exactly 4,194,304 same-pending-value writes. Within this bounded operation, guest Cause writes replace only IP0/IP1 while retaining IP2..IP7 values.

The fresh exact-pin reference rerun independently reproduced 21 ares cases, 12 interrupt entries and 9 suppressions, with byte-identical hashes:

- model report SHA-256 `8dead0768d59baa6c53e868de9c37ccfeed379fd2320b6fed9fba8ef8aa0e999`
- exact ares results SHA-256 `589eb9d5795106753e5de3f055dd14977702bb136c68793e3c4dc464ebaa3bda`

Gopher64 and Mupen exact-source behavior agree on the bounded Cause software-pending write mask. This is executable/reference evidence, not hardware truth. No dedicated hardware/system-test result for this exact mask is claimed here.

## Adopted invariant

Production accepts only a source-hash-bound, strictly ordered begin/write/end history for decoded guest `MTC0 Cause` operations.

For every authenticated successful write:

- IP0/IP1 are replaced by Cause bits 8..9 according to the relation above.
- IP2..IP7 are retained by this operation and are explicitly **not** assigned guest-Cause producer ownership.
- a fresh operation generation is minted even for same-value writes;
- PC, source GPR, epoch, raw operand, pre-state, effect boundary and completion are bound to one instruction context.

Faulting attempts without a write boundary mint no writer. Successful completion without an effect boundary, faulting completion with an effect, missing/duplicate/reordered/truncated records, context or operand mismatch, forged effects, hostile hardware-pending mutation and source/report tampering all fail closed.

No whole-pending-byte continuity is required between separate guest Cause writes because independent device/timer/hardware producers may alter IP2..IP7 between them. Their ancestry remains separate and UNKNOWN unless independently established.

## Rejected or superseded work

- The research branch was not mechanically merged.
- Research-only reference fixtures/workflows were not promoted into production.
- Equal values are not collapsed into one generation and never establish common provenance.
- Final register state, matching addresses or numeric pending values are not producer identity.
- This cluster does not implement Status.IM/IE/EXL/ERL gating, BEV/vector selection, interrupt-root admission, device/timer producer ancestry, handler provenance, cache/mapping lifetime, mutation-census closure, solver closure or native lowering.

## Production files

- `crates/plaid-core/src/software_interrupt.rs`
- `crates/plaid-core/src/lib.rs`
- this receipt

`docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md`, and `progress.json` are intentionally unchanged because this bounded producer primitive does not promote a canonical milestone.

## Validation

Adversarial regressions cover exact instruction decoding, exhaustive pending ownership, fresh same-value generations, preservation of hardware-pending bits, hostile Cause operands, fault/no-write attempts, missing effect boundaries, fabricated hardware-pending mutation, operand/context mismatch, deleted/reordered/truncated events, source-hash tampering and derived-report tampering.

Validation history:

- Historical canonical PR workflow `38153667923` / job `114512106256`: PASS.
- Fresh exact-pin reference rerun `37999241841` / rerun job `114512559014`: PASS.
- First later-main reconciliation `38154620749` / job `114514924233`: FAIL at strict Clippy because the synthesized `lib.rs` accidentally dropped the newly landed `sp_dma_egress` export. No main write occurred. The integration was rebuilt from the actual canonical `lib.rs` rather than patched around the error.
- Corrected reconciliation `38154689657` / job `114515129824`: PASS full canonical command set.
- Final current-main composition based on `0e0e999b626dbda3f47cfd6aa89673618ae20350`, validation head `597ab623e9e0bd9ae2dab977b8694fb0b0ab8570`, run `38155125329` / job `114516412101`: PASS exact decoder pin, `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, synthetic CLI, every retained 044-054 history/cache/TLB/RSP contract, and independent fetch-summary oracle.

The execution sandbox available to this worker had neither a Rust toolchain nor outbound DNS, while canonical `.github/workflows/rust.yml` had been changed to manual-only. Therefore the reconciliation runs used a branch-only temporary workflow containing the canonical validation commands. That helper is excluded from the production tree and must not land on `main`.

## Limitations and remaining proof obligations

This integration does **not** certify complete sensing of reachable Cause writes; device/timer/hardware ancestry for IP2..IP7; interrupt eligibility/gate chronology; BEV/vector selection or handler provenance; reset/NMI/save/restore chronology; executable cache/mapping/backing/lifetime composition; a complete mutation census; whole-ROM root completeness or CLOSED solver status; or native completeness.

All corresponding certification fields remain hard-false. UNKNOWN producer chronology remains UNKNOWN.