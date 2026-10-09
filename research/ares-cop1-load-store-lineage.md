# ares COP1 load-to-store byte lineage

Status: **RUNNING**. This note is an early durable checkpoint for worker `gpt56sol-cop1-load-store-lineage-20261009`; final verdict will be updated from exact-pin execution.

Plaid base: `main` at `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.

Research branch: `research/cop1-load-store-lineage-gpt56sol`.

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Experiment: `spikes/043-ares-cop1-load-store-lineage/`.

## Bounded question

Can a completed uncached identity-RDRAM `LWC1`/`LDC1` read be carried through the exact physical FPR lane(s) written by the instruction and later exported by `SWC1`/`SDC1`, without using matching payload values as provenance? In particular, do FR=0 pairing, FR=1 independent registers, FR flips, mixed 32/64-bit widths, same-value FPR overwrites, and load failures force lineage to be represented per byte rather than per FPR number or payload?

## Starting hypothesis

Pinned ares writes successful loads through `FT(u32/u64)`. Therefore the exact loaded bytes should enter:

- FR=0 `LWC1` even `ft`: low 32-bit lane of the paired even physical FPR;
- FR=0 `LWC1` odd `ft`: high 32-bit lane of that even physical FPR;
- FR=0 `LDC1` even/odd: the same full 64-bit even physical FPR;
- FR=1 `LWC1`: low 32-bit lane of the named FPR;
- FR=1 `LDC1`: the full named FPR.

A later store may inherit only the byte generations selected under the *store-time* FR mode. An FR flip itself need not erase physical bytes, but it can redirect a later architectural `ft` to different physical storage. Equal values, repeated FPR numbers, or same-value `MTC1`/`DMTC1` overwrites are therefore insufficient lineage evidence. CU1, alignment, and translation failures should mint no backing-read/FPR source generation.

## Exact source surface already guarded

`source_guard.py` checks the exact pinned revision and the `LWC1`, `LDC1`, `MTC1`, `DMTC1`, `SWC1`, `SDC1`, FR-sensitive `fgr_t`, and ordinary RDRAM scalar-read source shapes. The actual fixture executes decoded guest instructions with both CPU/RSP recompilers disabled. A project-owned research callback records only completed identity-mapped RDRAM scalar effects; plain mode leaves the callback null.

The independent `lineage.py` model stores an origin token on every byte of every 64-bit physical FPR cell. Its local pre-push self-test passes 67 cases with:

```text
PASS: 67 COP1 lineage-model cases
model_sha256=7fa9d29438288fcfc890ce5dfbb92ec717f841f18df8939ffac24012d1b0f080
```

Two deliberate decoys make a loaded word numerically equal to untouched bytes in a different FR interpretation. The model rejects those value-equality joins. A same-value `MTC1` overwrite likewise replaces origin tokens even when no numeric bit changes.

## Exact-pin matrix queued

`run.py` builds the existing Plaid headless pinned-ares oracle with the already established completed scalar-RDRAM callback, then checks:

- 64 load/store combinations across `LWC1`/`LDC1`, FR=0/1, even/odd `ft`, `SWC1`/`SDC1`, and independent store-time FR/`ft`;
- eight same-value `MTC1`/`DMTC1` overwrite cases;
- 24 CU1-disabled, misaligned, and unmapped-TLB load failures;
- plain versus callback-enabled semantic equality plus repeated callback-enabled output;
- exact read-before-write event ordering, physical addresses, widths, values, and uncached CPU device identity;
- per-byte origin replay, including mixed-origin 64-bit stores after 32-bit loads;
- adversarial equal-value cases where a value matcher would claim a false load→store edge.

No production Plaid file is modified. The workflow and experiment are branch-only research artifacts.

## Limits even if validated

This scope will not establish FPR arithmetic/conversion lineage, cached-load D-cache provenance, translated/TLB-backed successful loads, reverse-endian behavior, physical N64 bus transaction atomicity, asynchronous DMA/RSP producers, or whole-ROM closure. It is intended to settle only whether exact FPR byte generations are necessary and sufficient for this bounded decoded load→store chain in the pinned ares interpreter.
