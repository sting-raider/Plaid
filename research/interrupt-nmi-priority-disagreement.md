# Interrupt/NMI collision: VR4300 hardware priority vs exact ares

Status: **VALIDATED** (the initial ares-derived hardware-ordering hypothesis is **REJECTED**)

Date: 2026-10-10

Worker branch: `research/interrupt-nmi-order-gpt56sol`

Base `main`: `211176e7a489fecf8331d02915ee982cd279cb62`

## Question

When a maskable interrupt is eligible at the same acceptance boundary as an NMI, which root wins, and may a root transfer be counted as handler execution for closed-world proof purposes?

This composes the already-validated maskable-interrupt root contract, NMI root contract, and NMI root-fetch provenance work. The missing composition mattered because an unordered union of known roots can silently overclaim execution, and because one emulator's scheduling order is not hardware truth.

## Result

The VR4300 hardware contract and exact pinned ares disagree on the simultaneous case.

The NEC VR4300 User's Manual U10504EJ7V0UM00, section 6.4.3 Table 6-5, places Nonmaskable Interrupt above ordinary Interrupt in the exception priority order. Section 13.1 further specifies that NMI exception recognition is edge-triggered rather than level-sensitive. Therefore a simultaneous hardware NMI event has priority over an otherwise eligible ordinary interrupt, and a stable numeric NMI level must not be reinterpreted as a fresh NMI generation on every CPU boundary.

Exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` does the opposite for its internal state representation: `CPU::instruction()` tests an eligible maskable interrupt before `scc.nmiPending`. If both are asserted in the controlled fixture, ares first transfers to the interrupt root. The interrupt entry sets EXL, so on the next `CPU::instruction()` boundary the still-asserted ares `nmiPending` level wins and transfers to `0xffffffffbfc00000` before any instruction at the interrupt root is fetched.

This is a reference disagreement, not permission to choose whichever chronology is convenient. Plaid must use the VR4300 priority/edge contract for hardware closure and may use the exact ares chronology only as explicitly tagged reference behavior.

Manual source used for the hardware contract: NEC VR4300 User's Manual U10504EJ7V0UM00, sections 6.4.3 and 13.1, mirrored at `https://n64dev.org/p/U10504EJ7V0UMJ1.pdf`.

## Exact ares executable evidence

`experiments/interrupt-nmi-order-gpt56sol/driver.cpp` is a headless interpreter fixture. It plants an ordinary instruction at the initial KSEG1 PC and an `ADDIU $s1,$zero,0x5678` marker at the BEV=0 interrupt root. It executes exactly two `CPU::instruction()` boundaries. A project-owned fetch-boundary observer derived from the existing ares oracle recipe counts completed CPU fetches without changing the CPU object layout.

`experiments/interrupt-nmi-order-gpt56sol/run.py` builds both an observer-free baseline and an observer-capable exact-pin binary, executes each scenario twice, and requires baseline, sensor-disabled, and sensor-enabled machine-state projections to match. Ten scenarios cover BEV=0/1, persistent NMI, explicit NMI clear, explicit IP clear, IRQ-only, masked IRQ plus NMI, IE=0, EXL=1, ERL=1, and no-event positive fetch control.

The successful exact-ares Actions run at head `2f49048865ad0dd1c7ead097a6e9c61f42fbff35` reported:

- 10/10 scenarios repeated deterministically;
- observer-neutral machine state;
- `collision_persist_bev0`: first boundary `0xffffffff80000180`, second boundary `0xffffffffbfc00000`, with zero completed fetches at both boundaries and NMI ErrorEPC equal to the interrupt vector;
- `collision_persist_bev1`: first boundary `0xffffffffbfc00380`, second boundary `0xffffffffbfc00000`, likewise with zero completed fetches;
- positive control `collision_clear_nmi_bev0`: after explicitly clearing ares `nmiPending` between boundaries, the second boundary completes exactly one fetch and executes the planted interrupt-root marker (`$s1 = 0x5678`);
- no-event control completes one fetch per boundary in the traced build;
- `results.json` SHA-256 `22785597f5bb2dada3f3fc12c2da50043a748bb240a150d7bd8068926d190ee8`.

The runtime evidence proves a narrow fact about exact ares: root transfer is not handler fetch, and a later higher-priority condition in that model can supersede the transferred root before any handler instruction executes.

## Source guards and independent references

`experiments/interrupt-nmi-order-gpt56sol/source_guard.py` pins and hashes the exact sources. The successful run recorded:

- ares `cpu.cpp`: `65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1`
- ares `exceptions.cpp`: `e24b2877fb5d629ca3f10f64dba9a612babb879c53ed142b42557920f216ffa7`
- Gopher64 `exceptions.rs`: `935c2b7645830b9bc972fc834b7ce9c13e2e7a85ef2bdc2dec12bd6df6aaa829`
- Mupen64Plus `device.c`: `8b931f8e3419ca5088b2212fc86e191afd52c86c24b9cf379c1235b5c2ad0302`
- Mupen64Plus `interrupt.c`: `549263cd4cc11d9df2363acd4b41374a15b7d45aacea6383388f5847d896269f`

Gopher64's pinned implementation uses separate interrupt checking and reset-event paths. Mupen64Plus's pinned soft-reset path schedules HW2 immediately and NMI 50,000,000 Count units later. Neither independently adjudicates the same simultaneous NMI-edge versus eligible-interrupt collision, so neither is promoted to hardware oracle for this question.

## Adversarial model

`experiments/interrupt-nmi-order-gpt56sol/model.py` keeps two deliberately separate semantics:

1. exact-ares level/order behavior: eligible maskable interrupt before `nmiPending`;
2. VR4300 manual behavior: an NMI event edge before ordinary interrupt, with no second NMI manufactured from an unchanged numeric level.

A deterministic 100,000-state sweep with seed `0x4e4d4951` actively searches IE/EXL/ERL/BEV/IP/IM/NMI combinations. Every state with both an eligible ordinary interrupt and an NMI event is required to disagree in first choice: ares chooses IRQ, the manual model chooses NMI. All non-collision first choices must agree. The model also rejects policies that collapse root transfer into fetch, collapse EPC and ErrorEPC histories, or equate a stable pending value with a fresh event generation.

An earlier checkpoint model treated ares ordering as the candidate contract and therefore labelled NMI-first as a forged history. That checkpoint is superseded by this note and the final model after consulting the vendor manual. It must not be used as the hardware conclusion.

## Closed-world impact

A closure certificate cannot represent asynchronous roots as a set of addresses alone. For each accepted asynchronous event it needs, at minimum, event/source identity, event generation or edge identity, acceptance boundary, priority class, root-transfer receipt, and subsequent fetch receipt. Those facts must remain separate from ordinary pending-bit content identity.

For the simultaneous hardware case specifically, a certificate that records both the NMI root and interrupt root as 'executed' is unsound. NMI wins the priority decision first. The ordinary interrupt may remain pending and become acceptable later after software changes the exception state, but that is a distinct future acceptance event and needs its own chronology and fetch evidence.

Likewise, same-value state is not same event provenance. A stable numeric NMI indication cannot prove a second NMI edge, just as a root PC value cannot prove an instruction fetch from that root.

## Reproduction

With the exact refs from `refs.lock.toml` checked out under `.refs/`:

```sh
python3 experiments/interrupt-nmi-order-gpt56sol/model.py
python3 experiments/interrupt-nmi-order-gpt56sol/source_guard.py
python3 experiments/interrupt-nmi-order-gpt56sol/run.py
```

The branch-only workflow `.github/workflows/research-interrupt-nmi-order.yml` performs the same exact-pin source guards, model run, baseline/sensed ares builds, repeated 10-case matrix, hashes, and evidence upload on Ubuntu 24.04.

## Remaining gap

The vendor manual resolves architectural priority and NMI edge semantics, and the fixture resolves exact-ares behavior. This work does not measure the N64 console's system-level reset/NMI producer timing, the precise external pin/Interrupt-register generation chronology around PCycle acceptance, or a real-hardware collision fixture. Those producer/timing facts remain separate obligations if a ROM can depend on them.

Whole-ROM closure therefore remains OPEN unless those event-generation and acceptance histories are represented; no flag should waive them.

## Integration recommendation

Do not merge an ares-specific priority rule into production. Instead, encode asynchronous execution roots as generation-bearing events and use the VR4300 priority order for the hardware proof model. Keep root transfer and instruction fetch as distinct evidence objects. Tag the exact-ares simultaneous IRQ/NMI chronology as a known reference disagreement so differential testing does not accidentally promote it to hardware truth.
