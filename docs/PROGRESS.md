# Plaid progress map

This page is generated from [`docs/progress.json`](progress.json) by [`tools/progress.py`](../tools/progress.py).

The map deliberately does **not** publish a single overall completion percentage. Plaid's subsystems have hard dependencies: a mostly green discovery pipeline is not equivalent to a mostly finished native recompiler.

Legend:

- ✅ **Verified** — verified and integrated on `main` for the stated milestone.
- 🟨 **Partial** — implemented or experimentally supported, but proof/coverage is incomplete.
- ⬜ **Open** — not implemented or not yet demonstrated.

Last progress-data update: **2026-10-09**.

## Discovery & ProgramMap

| Milestone | State |
| --- | --- |
| ROM normalization & identity | ✅ verified |
| ProgramMap schema & validation | ✅ verified |
| Dynamic trace import | ✅ verified |
| Direct CFG recovery | ✅ verified |
| Evidence merge & conflicts | ✅ verified |
| Local indirect certificates | ✅ verified |
| Cross-block indirect proofs | 🟨 partial |
| Jump/pointer-table recovery | 🟨 partial |
| Known-library/signature evidence | ⬜ open |
| Commercial-ROM map validation | ⬜ open |

## Executable Provenance

| Milestone | State |
| --- | --- |
| Physical/cache fetch context | ✅ verified |
| I-cache snapshots/fill outcomes | ✅ verified |
| PI request/queue/source history | ✅ verified |
| SP/PIF backing witnesses | ✅ verified |
| CPU executable-store sensing | 🟨 partial |
| CPU copy/transform lineage | 🟨 partial |
| RSP writer/dataflow lineage | 🟨 partial |
| Cache writeback/restore lineage | 🟨 partial |
| Decompression/relocation lineage | ⬜ open |
| Complete mutation census | ⬜ open |

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
| Overlay/executable lifetimes | ⬜ open |
| RSP executable-universe proof | ⬜ open |
| First ROM reaches CLOSED | ⬜ open |

## Native AOT Compiler

| Milestone | State |
| --- | --- |
| Architecture-neutral IR | ⬜ open |
| Integer MIPS lowering | ⬜ open |
| x86-64 object emission | ⬜ open |
| ARM64 object emission | ⬜ open |
| Native direct calls | ⬜ open |
| Finite native indirect dispatch | ⬜ open |
| Native differential verifier | ⬜ open |
| Link/package model | ⬜ open |

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

## Compatibility

| Milestone | State |
| --- | --- |
| Synthetic discovery corpus | ✅ verified |
| Mupen/ares differential oracles | ✅ verified |
| n64-systemtest research corpus | 🟨 partial |
| First commercial ROM mapped | ⬜ open |
| First commercial ROM CLOSED | ⬜ open |
| First native synthetic executable | ⬜ open |
| First native commercial boot | ⬜ open |
| First native gameplay | ⬜ open |
| Representative 25-game set | ⬜ open |
| 100-game campaign | ⬜ open |

## Interpretation

The status cells describe the maturity of explicitly named milestones, not title compatibility or the probability that an arbitrary ROM will work. A `partial` milestone stays partial until its remaining proof obligations are closed. Research branches do not turn a cell green until the relevant result is integrated and verified on `main`.

The authoritative detailed engineering state remains [`docs/STATUS.md`](STATUS.md) and [`docs/NEXT.md`](NEXT.md).
