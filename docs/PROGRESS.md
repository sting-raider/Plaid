# Plaid progress map

This page is generated from [`docs/progress.json`](progress.json) by [`tools/progress.py`](../tools/progress.py).

The map deliberately does **not** publish a single overall completion percentage. Plaid's subsystems have hard dependencies: a mostly green discovery pipeline is not equivalent to a mostly finished native recompiler.

Legend:

- ✅ **Verified** — verified and integrated on `main` for the stated milestone.
- 🟨 **Partial** — implemented or experimentally supported, but proof/coverage is incomplete.
- ⬜ **Open** — not implemented or not yet demonstrated.

Last progress-data update: **2026-10-15**.

## Retained evidence

| Evidence | Observed scope | Source |
| --- | --- | --- |
| **20,000,000** Observed CPU fetches | Retained commercial-ROM prefix | [Receipt / status](../research/integration-receipts/20261014-storage-writer-fetch-primary.md) |
| **62** OoT whole-ROM blockers | Local OoT baseline; 44 indirect sites | [Receipt / status](../research/integration-receipts/20261012-discovery-solve-primary-composition.md) |
| **2,472,203** Full PI-byte fetch chains | Canonical + independent replay agree | [Receipt / status](STATUS-LOG.md) |
| **0** Commercial ROMs CLOSED | Whole-ROM and native gates remain open | [Receipt / status](STATUS.md) |

These are finite observations, not exhaustive execution coverage or a CLOSED certificate.

## Discovery & ProgramMap

| Milestone | State |
| --- | --- |
| ROM normalization & identity | ✅ verified |
| ProgramMap schema & validation | ✅ verified |
| Dynamic trace import | ✅ verified |
| Direct CFG recovery | ✅ verified |
| Evidence merge & conflicts | ✅ verified |
| Local indirect certificates | ✅ verified |
| Bounded cross-block indirect proofs | ✅ verified |
| Jump/pointer-table recovery | 🟨 partial |
| Known-library/signature evidence | ⬜ open |
| Commercial-ROM map validation | ⬜ open |

**Remaining:** Broader indirect targets and a complete commercial-ROM map.

## Executable Provenance

| Milestone | State |
| --- | --- |
| Physical/cache fetch context | ✅ verified |
| I-cache snapshots/fill outcomes | ✅ verified |
| PI request/queue/source history | ✅ verified |
| SP/PIF backing witnesses | ✅ verified |
| Bounded original-clock RAM mutation cuts | ✅ verified |
| Bounded PI primitive-to-writer composition | ✅ verified |
| Bounded PI / SP DMA / CPU consumption chain | ✅ verified |
| Bounded lower-DMEM ancestry revocation | ✅ verified |
| Bounded lower-IMEM ancestry revocation | ✅ verified |
| Exact IMEM-read / performed-RSP receipts | ✅ verified |
| Bounded scalar producer / executable-read join | ✅ verified |
| Bounded scalar store / executable backing | ✅ verified |
| Bounded reverse-SP-DMA / RAM executable chain | ✅ verified |
| Controlled D-cache export / executable chain | ✅ verified |
| Controlled mapping / cache / exception chain | ✅ verified |
| CPU executable-store sensing | 🟨 partial |
| CPU copy/transform lineage | 🟨 partial |
| RSP writer/dataflow lineage | 🟨 partial |
| Cache writeback/restore lineage | 🟨 partial |
| Decompression/relocation lineage | 🟨 partial |
| Complete mutation census | ⬜ open |

**Remaining:** Complete writer census, producer ancestry and continuous lifetimes.

## Closed-World Proof

| Milestone | State |
| --- | --- |
| Fail-closed solver & diagnostics | ✅ verified |
| Source/certificate rechecking | ✅ verified |
| Direct-control-flow closure | ✅ verified |
| Finite indirect-target closure | 🟨 partial |
| Execution-root completeness | 🟨 partial |
| TLB/context/cache composition | 🟨 partial |
| Pointer-table immutability proof | 🟨 partial |
| Overlay/executable lifetimes | 🟨 partial |
| RSP executable-universe proof | 🟨 partial |
| First ROM reaches CLOSED | ⬜ open |

**Remaining:** Compose exhaustive roots, targets and lifetimes into a CLOSED scope.

## Native AOT Compiler

| Milestone | State |
| --- | --- |
| MIPS -> C lowering (ADR-0126) | 🟨 partial |
| Integer MIPS lowering | 🟨 partial |
| x86-64 host build via C | 🟨 partial |
| ARM64 host build via C | ⬜ open |
| Return closure / function-level lowering | ⬜ open |
| Finite native indirect dispatch | 🟨 partial |
| Synthetic native differential verifier | ✅ verified |
| Link with N64ModernRuntime | ⬜ open |

**Remaining:** Return closure, function-level C, wider ISA, runtime link.

## Native Runtime

| Milestone | State |
| --- | --- |
| Guest memory/MMIO runtime | ⬜ open |
| Interrupt/timing/event runtime | ⬜ open |
| Controller input | ⬜ open |
| Save devices | ⬜ open |
| Audio path | ⬜ open |
| RSP runtime/native path | ⬜ open |
| Renderer integration | ⬜ open |
| Native launch/cache packaging | ⬜ open |

**Remaining:** Reuse N64ModernRuntime + RT64 (ADR-0126) and link lowered code.

## Compatibility

| Milestone | State |
| --- | --- |
| Synthetic discovery corpus | ✅ verified |
| Mupen/ares differential oracles | ✅ verified |
| 20M-fetch commercial-prefix replay | ✅ verified |
| n64-systemtest research corpus | 🟨 partial |
| First commercial ROM mapped | ⬜ open |
| First commercial ROM CLOSED | ⬜ open |
| First native synthetic executable | ✅ verified |
| First native commercial boot | ⬜ open |
| First native gameplay | ⬜ open |
| Representative 25-game set | ⬜ open |
| 100-game campaign | ⬜ open |

**Remaining:** First CLOSED ROM, native boot and reproducible gameplay.

## Interpretation

The status cells describe the maturity of explicitly named milestones, not title compatibility or the probability that an arbitrary ROM will work. A `partial` milestone stays partial until its remaining proof obligations are closed. Research branches do not turn a cell green until the relevant result is integrated and verified on `main`.

The current engineering state is [`docs/STATUS.md`](STATUS.md) (history in [`STATUS-LOG.md`](STATUS-LOG.md)) and [`docs/NEXT.md`](NEXT.md).
