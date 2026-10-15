# Plaid progress map

This page is generated from [`docs/progress.json`](progress.json) by [`tools/progress.py`](../tools/progress.py).

The map deliberately does **not** publish a single overall completion percentage. Plaid's subsystems have hard dependencies: a mostly green discovery pipeline is not equivalent to a mostly finished native recompiler.

Legend:

- ✅ **Verified** — verified and integrated on `main` for the stated milestone.
- 🟨 **Partial** — implemented or experimentally supported, but proof/coverage is incomplete.
- ⬜ **Open** — not implemented or not yet demonstrated.

Last progress-data update: **2026-10-15**. Day-by-day numbers: [progress history](HISTORY.md).

## Retained evidence

| Evidence | Observed scope | Source |
| --- | --- | --- |
| **45,419** SM64 blocks CLOSED | Under declared assumptions | [Receipt / status](STATUS.md) |
| **99.03%** SM64 discovery recall | Against a local decomp map | [Receipt / status](STATUS.md) |
| **59.9 VI/s** SM64 native, full speed | RT64 graphics, native RSP audio | [Receipt / status](../research/sm64-first-measurement.md) |
| **0** Commercial ROMs CLOSED | Whole-ROM, with no assumptions | [Receipt / status](STATUS.md) |

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
| Known-library/signature evidence | ✅ verified |
| Commercial-ROM map validation | ✅ verified |
| Declared executable loads (ADR-0136) | ✅ verified |

**Remaining:** General jump tables, automatic load discovery, overlays.

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
| First ROM reaches CLOSED | 🟨 partial |
| Assumption-scoped CLOSED: SM64 (ADR-0153) | ✅ verified |

**Remaining:** Retire the declared assumptions: whole-ROM CLOSED with none.

## Native AOT Compiler

| Milestone | State |
| --- | --- |
| MIPS -> C lowering (ADR-0126) | ✅ verified |
| Integer MIPS lowering | ✅ verified |
| x86-64 host build via C | ✅ verified |
| ARM64 host build via C | ⬜ open |
| Return closure / function-level lowering | ✅ verified |
| Finite native indirect dispatch | ✅ verified |
| Synthetic native differential verifier | ✅ verified |
| Link with the Plaid runtime (ADR-0158) | ✅ verified |
| COP1/FPU lowering (FR = 0 and 1) | ✅ verified |
| RSP scalar + vector lowering (ADR-0167/0168) | ✅ verified |

**Remaining:** ARM64 host build; COP0/TLB/system forms stay behind the runtime.

## Native Runtime

| Milestone | State |
| --- | --- |
| Declared runtime-function boundary (ADR-0129) | ✅ verified |
| Guest memory/MMIO runtime | ✅ verified |
| Interrupt/timing/event runtime | ✅ verified |
| Controller input | 🟨 partial |
| Save devices | 🟨 partial |
| Audio path | 🟨 partial |
| RSP runtime/native path | ✅ verified |
| Renderer integration | ✅ verified |
| Native launch/cache packaging | ⬜ open |

**Remaining:** Live audio, other saves and controllers, packaging, non-Windows hosts.

## Compatibility

| Milestone | State |
| --- | --- |
| Synthetic discovery corpus | ✅ verified |
| Mupen/ares differential oracles | ✅ verified |
| 20M-fetch commercial-prefix replay | ✅ verified |
| n64-systemtest research corpus | 🟨 partial |
| First commercial ROM mapped | ✅ verified |
| First commercial ROM CLOSED | 🟨 partial |
| First native synthetic executable | ✅ verified |
| First native commercial boot | ✅ verified |
| First native gameplay | ✅ verified |
| Representative 25-game set | ⬜ open |
| 100-game campaign | ⬜ open |

**Remaining:** Whole-ROM CLOSED, then Ocarina of Time and a wider game set.

## Interpretation

The status cells describe the maturity of explicitly named milestones, not title compatibility or the probability that an arbitrary ROM will work. A `partial` milestone stays partial until its remaining proof obligations are closed. Research branches do not turn a cell green until the relevant result is integrated and verified on `main`.

The current engineering state is [`docs/STATUS.md`](STATUS.md) (history in [`STATUS-LOG.md`](STATUS-LOG.md)) and [`docs/NEXT.md`](NEXT.md).
